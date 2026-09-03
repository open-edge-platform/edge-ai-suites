"""Hardware vblank clock — ported from the BU reference ``vsync_loop``.

Publishes a monotonically increasing vblank counter (plus the perf-clock time of
each tick) using ``GLX_OML_sync_control`` (``glXWaitForMscOML``). The capture
loop waits on this clock and software-triggers the camera in lock-step with the
monitor refresh, so a frame is exposed just-in-time for the next present — this
is the core photon-to-pixel latency reduction the reference was built around.

X11/GLX only. If GLFW/GLX is unavailable (Wayland, headless, missing runtime)
``start()`` returns ``False`` and the caller falls back to free-running capture.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time

log = logging.getLogger("vsync")


class VSyncClock:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._counter = 0
        self._tick_perf_ns = 0
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._ok = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Start the vblank thread. Returns True once GLX sync is live."""
        self._thread = threading.Thread(target=self._run, name="vsync", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        return self._ok

    def stop(self) -> None:
        self._stop.set()

    def wait(self, last_seen: int, timeout: float = 0.5) -> tuple[int, int] | None:
        """Block until the vblank counter advances past ``last_seen``.

        Returns ``(counter, tick_perf_ns)`` or ``None`` on timeout/shutdown.
        """
        with self._cv:
            while self._counter == last_seen and not self._stop.is_set():
                if not self._cv.wait(timeout=timeout):
                    return None
            if self._stop.is_set():
                return None
            return self._counter, self._tick_perf_ns

    def _run(self) -> None:  # noqa: C901 - mirrors the reference loop structure
        try:
            import glfw
        except Exception as exc:  # noqa: BLE001
            log.warning("vsync: glfw unavailable (%s) — clock disabled", exc)
            self._ready.set()
            return

        if not glfw.init():
            log.warning("vsync: glfwInit() failed — clock disabled")
            self._ready.set()
            return

        # The window MUST be visible/mapped: an unmapped (VISIBLE=FALSE) drawable
        # receives no vblank events, so glXWaitForMscOML would block forever after
        # the primed value. Keep it tiny and parked in a corner instead.
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
        glfw.window_hint(glfw.FOCUSED, glfw.FALSE)
        glfw.window_hint(glfw.FLOATING, glfw.TRUE)
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 2)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 0)
        glfw.window_hint(glfw.DOUBLEBUFFER, glfw.TRUE)

        # Prefer the highest-refresh monitor (the reference targeted a 119Hz panel).
        target = None
        best_hz = 0
        for m in glfw.get_monitors():
            mode = glfw.get_video_mode(m)
            if mode.refresh_rate > best_hz:
                best_hz, target = mode.refresh_rate, m

        window = glfw.create_window(100, 100, "vsync", None, None)
        if not window:
            log.warning("vsync: window creation failed — clock disabled")
            glfw.terminate()
            self._ready.set()
            return

        if target is not None:
            mx, my = glfw.get_monitor_pos(target)
            glfw.set_window_pos(window, mx + 10, my + 10)
            log.info("vsync: locked to %dHz monitor", best_hz)

        glfw.make_context_current(window)
        glfw.swap_interval(0)

        try:
            libGL = ctypes.CDLL("libGL.so.1")

            glXGetCurrentDisplay = libGL.glXGetCurrentDisplay
            glXGetCurrentDisplay.restype = ctypes.c_void_p
            glXGetCurrentDrawable = libGL.glXGetCurrentDrawable
            glXGetCurrentDrawable.restype = ctypes.c_ulong

            glXGetSyncValuesOML = libGL.glXGetSyncValuesOML
            glXGetSyncValuesOML.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_int64),
                ctypes.POINTER(ctypes.c_int64),
                ctypes.POINTER(ctypes.c_int64),
            ]
            glXGetSyncValuesOML.restype = ctypes.c_int

            glXWaitForMscOML = libGL.glXWaitForMscOML
            glXWaitForMscOML.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong,
                ctypes.c_int64, ctypes.c_int64, ctypes.c_int64,
                ctypes.POINTER(ctypes.c_int64),
                ctypes.POINTER(ctypes.c_int64),
                ctypes.POINTER(ctypes.c_int64),
            ]
            glXWaitForMscOML.restype = ctypes.c_int
        except (OSError, AttributeError) as exc:
            log.warning("vsync: GLX_OML_sync_control unavailable (%s) — clock disabled", exc)
            glfw.destroy_window(window)
            glfw.terminate()
            self._ready.set()
            return

        dpy = glXGetCurrentDisplay()
        drawable = glXGetCurrentDrawable()
        if not dpy or drawable == 0:
            log.warning("vsync: no GLX display/drawable (not X11/GLX?) — clock disabled")
            glfw.destroy_window(window)
            glfw.terminate()
            self._ready.set()
            return

        ust = ctypes.c_int64(0)
        msc = ctypes.c_int64(0)
        sbc = ctypes.c_int64(0)
        if glXGetSyncValuesOML(dpy, drawable, ctypes.byref(ust), ctypes.byref(msc), ctypes.byref(sbc)) == 0:
            log.warning("vsync: glXGetSyncValuesOML failed — clock disabled")
            glfw.destroy_window(window)
            glfw.terminate()
            self._ready.set()
            return

        last_msc = int(msc.value)
        self._ok = True
        self._ready.set()
        log.info("vsync: GLX_OML clock live")

        while not self._stop.is_set() and not glfw.window_should_close(window):
            target_msc = last_msc + 1
            ust = ctypes.c_int64(0)
            msc = ctypes.c_int64(0)
            sbc = ctypes.c_int64(0)
            ok = glXWaitForMscOML(
                dpy, drawable,
                ctypes.c_int64(target_msc), ctypes.c_int64(0), ctypes.c_int64(0),
                ctypes.byref(ust), ctypes.byref(msc), ctypes.byref(sbc),
            )
            if ok == 0:
                continue
            tick_perf_ns = time.perf_counter_ns()
            new_msc = int(msc.value)
            with self._cv:
                self._counter = new_msc
                self._tick_perf_ns = tick_perf_ns
                self._cv.notify_all()
            last_msc = new_msc
            try:
                glfw.poll_events()  # keep the window responsive (no WM "not responding")
            except Exception:  # noqa: BLE001
                pass

        glfw.destroy_window(window)
        glfw.terminate()
        log.info("vsync: clock stopped")
