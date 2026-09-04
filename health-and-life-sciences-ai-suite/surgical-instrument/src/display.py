"""Display presenters — how annotated frames actually reach the screen.

Two backends behind one tiny interface (``present()`` / ``close()``):

* ``GLPresenter``  — OpenGL window via GLFW with **vsync-locked** presentation
  (``swap_interval(1)``). ``swap_buffers()`` blocks until the monitor's vertical
  blank, so frames are presented in lock-step with the display refresh. This is
  the "synchronized sink" the BU reference had (their ``autovideosink sync=true``
  equivalent), but here it only synchronizes the *display* — capture stays
  free-running (newest-frame-wins) and inference stays on its own thread feeding
  only box coordinates. No GStreamer / DL Streamer involved.

* ``CV2Presenter`` — the original ``cv2.imshow`` path (NOT vsync-locked). Kept as
  a portable fallback and for ``--presenter cv2``.

Selection + graceful degradation is handled by ``create_presenter()``:

    --headless            -> None            (log / record only)
    --presenter auto      -> GL, else CV2, else headless   (default)
    --presenter gl        -> GL, else CV2 (with a loud warning)
    --presenter cv2       -> CV2, else headless

Dependencies (all OPTIONAL and lazily imported, so ``--source file`` /
``--headless`` / CI need none of them):

    Python : glfw           (pip install glfw)
             PyOpenGL       (pip install PyOpenGL)
    System : libglfw3       + an OpenGL/GLX (or EGL/Wayland) runtime.
             On Linux desktop that is typically:
               libglfw3 libgl1 libglx-mesa0 libgl1-mesa-dri
             Plus a reachable display server: X11 socket (/tmp/.X11-unix) and
             DISPLAY, or a Wayland socket. GPU render node /dev/dri is required
             for hardware GL (already passed through by the Makefile).

If any of the above is missing the app does NOT crash — it logs the reason and
falls back down the chain to cv2 and finally to headless.
"""
from __future__ import annotations

import logging
from typing import Protocol

import cv2
import numpy as np

log = logging.getLogger("display")

WINDOW_TITLE = "Endoscopy Demo"


class Presenter(Protocol):
    #: True only for a real vsync-locked backend (drives the loop off the vblank).
    vsync: bool

    def present(self, frame_bgr: np.ndarray) -> bool:
        """Show one frame. Return False to request shutdown (ESC / window close)."""
        ...

    def close(self) -> None: ...


class CV2Presenter:
    """OpenCV highgui window. Simple and portable, but NOT synchronized to the
    display refresh (kept as the fallback / ``--presenter cv2``)."""

    vsync = False

    def __init__(self, width: int, height: int, scale: float) -> None:
        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_TITLE, int(width * scale), int(height * scale))

    def present(self, frame_bgr: np.ndarray) -> bool:
        cv2.imshow(WINDOW_TITLE, frame_bgr)
        return (cv2.waitKey(1) & 0xFF) != 27  # ESC -> stop

    def close(self) -> None:
        cv2.destroyAllWindows()


class GLPresenter:
    """OpenGL window (GLFW) with vsync-locked presentation.

    ``present()`` uploads the BGR frame into a texture, draws it on a fullscreen
    quad and calls ``swap_buffers()``, which blocks until the next vertical blank
    because ``swap_interval(1)`` is set. The display loop is therefore paced by
    the monitor's refresh clock — this is what removes the capture/refresh beat
    the BU team measured.
    """

    vsync = True

    def __init__(self, width: int, height: int, scale: float, fullscreen: bool = False,
                 vsync_lock: bool = True) -> None:
        import glfw  # lazy: only needed when a GL window is actually created
        from OpenGL import GL

        self._glfw = glfw
        self._GL = GL
        self._win = None
        self._should_close = False
        self._tw = self._th = 0

        if not glfw.init():
            raise RuntimeError("glfwInit() failed (no display server / GLFW runtime?)")
        try:
            # Legacy compatibility context: the fixed-function pipeline (glBegin/
            # glTexCoord) is enough for a textured quad and avoids shader setup.
            glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
            glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)

            monitor = None
            if fullscreen:
                # A real fullscreen window is unredirected by the compositor (direct
                # scanout), which removes the 1-2 frames of compositor buffering that
                # dominate desktop photon-to-pixel latency.
                monitor = glfw.get_primary_monitor()
                mode = glfw.get_video_mode(monitor)
                win_w, win_h = mode.size.width, mode.size.height
            else:
                win_w, win_h = int(width * scale), int(height * scale)
            self._win = glfw.create_window(win_w, win_h, WINDOW_TITLE, monitor, None)
            if not self._win:
                raise RuntimeError("glfwCreateWindow() failed (no GLX/EGL surface?)")

            glfw.make_context_current(self._win)
            if vsync_lock:
                glfw.swap_interval(1)   # swap_buffers() blocks on vblank (phase-lock)
                self.vsync = True
            else:
                # Immediate present (no vblank wait) = lowest latency; the loop then
                # advances only on new frames. Trade-off: possible tearing.
                glfw.swap_interval(0)
                self.vsync = False  # instance override: don't re-present held frames
            glfw.set_key_callback(self._win, self._on_key)

            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # BGR rows aren't 4-aligned
            self._tex = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glEnable(GL.GL_TEXTURE_2D)
        except Exception:
            # Make sure a partially-initialized GLFW is torn down before we
            # propagate, so the caller can cleanly fall back to cv2.
            self.close()
            raise

    def _on_key(self, win, key, scancode, action, mods) -> None:  # noqa: ANN001
        if key == self._glfw.KEY_ESCAPE and action == self._glfw.PRESS:
            self._should_close = True

    def present(self, frame_bgr: np.ndarray) -> bool:
        GL, glfw = self._GL, self._glfw
        frame = np.ascontiguousarray(frame_bgr)
        h, w = frame.shape[:2]

        GL.glBindTexture(GL.GL_TEXTURE_2D, self._tex)
        if (w, h) != (self._tw, self._th):
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGB, w, h, 0,
                            GL.GL_BGR, GL.GL_UNSIGNED_BYTE, frame)
            self._tw, self._th = w, h
        else:
            GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, w, h,
                               GL.GL_BGR, GL.GL_UNSIGNED_BYTE, frame)

        fbw, fbh = glfw.get_framebuffer_size(self._win)
        GL.glViewport(0, 0, fbw, fbh)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        # Fullscreen quad in NDC; texcoords flipped in V (image origin is top-left,
        # GL texture origin is bottom-left) so the frame is upright.
        GL.glBegin(GL.GL_QUADS)
        GL.glTexCoord2f(0.0, 1.0); GL.glVertex2f(-1.0, -1.0)
        GL.glTexCoord2f(1.0, 1.0); GL.glVertex2f(1.0, -1.0)
        GL.glTexCoord2f(1.0, 0.0); GL.glVertex2f(1.0, 1.0)
        GL.glTexCoord2f(0.0, 0.0); GL.glVertex2f(-1.0, 1.0)
        GL.glEnd()

        glfw.swap_buffers(self._win)  # BLOCKS until the next vblank (vsync lock)
        glfw.poll_events()
        return not (self._should_close or glfw.window_should_close(self._win))

    def close(self) -> None:
        try:
            if self._win is not None:
                self._glfw.destroy_window(self._win)
                self._win = None
            self._glfw.terminate()
        except Exception:  # noqa: BLE001
            pass


def create_presenter(headless: bool, presenter: str, width: int, height: int,
                     scale: float, fullscreen: bool = False, vsync_lock: bool = True) -> Presenter | None:
    """Pick a presenter with graceful fallback. Returns None for headless / when
    no display is available at all."""
    if headless:
        return None

    choice = (presenter or "auto").lower()

    if choice in ("auto", "gl"):
        try:
            p = GLPresenter(width, height, scale, fullscreen=fullscreen, vsync_lock=vsync_lock)
            mode = "fullscreen direct-scanout" if fullscreen else "windowed"
            log.info("display: OpenGL presenter (%s, %s)",
                     mode, "vsync-locked" if vsync_lock else "immediate")
            return p
        except Exception as exc:  # noqa: BLE001
            level = log.warning if choice == "gl" else log.info
            level("display: GL presenter unavailable (%s) — falling back to cv2 imshow", exc)

    # Explicit cv2, or fallback from gl/auto.
    try:
        p = CV2Presenter(width, height, scale)
        log.info("display: OpenCV imshow presenter (NOT vsync-locked)")
        return p
    except cv2.error as exc:
        log.warning("display: no usable display (%s) — continuing headless (log/record only)", exc)
        return None
