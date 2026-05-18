import React, { useEffect, useRef, useState } from "react";
import videojs from "video.js";
import "video.js/dist/video-js.css";
import { useTranslation } from 'react-i18next';
import "../../assets/css/HLSPlayer.css";
interface Props {
  streamUrl?: string;
  videoFile?: File;
  mode: "stream" | "playback";
  camera?: "front" | "back" | "content"; // Identifies which camera this player represents
}

interface TimelineHighlight {
  startTime: number;
  endTime: number;
  topic: string;
}

interface SeekVideoEvent extends CustomEvent {
  detail: { timestamp: number };
}

interface HighlightTimelineEvent extends CustomEvent {
  detail: TimelineHighlight & { targetCamera?: 'back' | 'content' | 'front' | null };
}

/* ---------------- TIMELINE HIGHLIGHT COMPONENT ---------------- */

class TimelineHighlights extends videojs.getComponent("Component") {
  
  private highlights: TimelineHighlight[] = [];

  constructor(player: any, options: any) {
    super(player, options);
  }

  createEl() {
    return videojs.dom.createEl("div", {
      className: "vjs-timeline-highlights",
      style:
        "position:absolute;top:0;left:0;right:0;height:100%;pointer-events:none;z-index:1;",
    });
  }

  updateHighlights(highlights: TimelineHighlight[]) {
    this.highlights = highlights;
    const duration = this.player().duration();

    if (!duration || !highlights.length) {
      this.el().innerHTML = "";
      return;
    }

    this.el().innerHTML = "";

    highlights.forEach((h) => {
      const left = (h.startTime / duration) * 100;
      let width = ((h.endTime - h.startTime) / duration) * 100;
      
      // Clamp width to not exceed 100% - prevents overflow beyond video frame
      width = Math.min(width, 100 - left);

      const marker = videojs.dom.createEl("div", {
        title: h.topic,
        style: `
          position:absolute;
          top:0;
          height:100%;
          background:rgba(223,69,49,.85);
          border-radius:2px;
          left:${left}%;
          width:${width}%;
          box-shadow:0 0 2px rgba(241,246,255,.5);
        `,
      });

      this.el().appendChild(marker);
    });
  }
}

videojs.registerComponent("TimelineHighlights", TimelineHighlights);

/* ---------------- MAIN COMPONENT ---------------- */

const HLSPlayer: React.FC<Props> = ({ streamUrl, videoFile, mode, camera }) => {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<any>(null);
  const highlightComponentRef = useRef<TimelineHighlights | null>(null);

  const [duration, setDuration] = useState(0);
  const [highlights, setHighlights] = useState<TimelineHighlight[]>([]);

  // Determine if streamUrl is a webpage or HLS stream
  const isWebpage = streamUrl && !streamUrl.endsWith('.m3u8');

  console.log("HLSPlayer initializing:", { 
    streamUrl, 
    isWebpage, 
    mode 
  });

  /* ---------- PLAYER INITIALIZATION ---------- */

  useEffect(() => {
    if (mode !== "playback") return;
    
    cleanup();

    console.log('🎬 HLSPlayer initializing playback:', { streamUrl, videoFile });

    if (videoFile) {
      console.log('🎬 Initializing playback with File object');
      initVideoJS();
    } else if (streamUrl) {
      console.log('🎬 Initializing playback with URL:', streamUrl);
      initPlaybackFromURL();
    } else {
      console.warn('🎬 Playback mode but no videoFile or streamUrl provided');
    }

    return cleanup;
  }, [streamUrl, videoFile, mode]);

  /* ---------- CLEANUP ---------- */

  const cleanup = () => {
    if (playerRef.current) {
      try {
        if (!playerRef.current.isDisposed()) {
          playerRef.current.dispose();
        }
      } catch (e) {
        console.warn("Error disposing player:", e);
      }
      playerRef.current = null;
      highlightComponentRef.current = null;
    }

    if (containerRef.current) {
      containerRef.current.innerHTML = "";
    }
  };

  /* ---------- VIDEO.JS PLAYBACK (for video files) ---------- */

  const initVideoJS = () => {
    if (!containerRef.current || !videoFile) return;

    const videoEl = document.createElement("video-js");
    videoEl.className = "video-js vjs-default-skin";
    videoEl.style.width = "100%";
    videoEl.style.height = "100%";

    containerRef.current.appendChild(videoEl);

    playerRef.current = videojs(videoEl, {
      controls: true,
      responsive: true,
      fluid: true,
      playbackRates: [0.5, 1, 1.25, 1.5, 2],
    });

    const url = URL.createObjectURL(videoFile);
    playerRef.current.src({ src: url, type: videoFile.type });

    playerRef.current.ready(() => {
      setupHighlightComponent();
      setupPlayerEvents();
      playerRef.current.play().catch(console.error);
    });
  };

  /* ---------- PLAYBACK FROM HTTP URL (for recorded videos from backend) ---------- */

  const initPlaybackFromURL = () => {
    if (!containerRef.current || !streamUrl) return;

    console.log("Initializing playback from URL:", streamUrl);

    const videoEl = document.createElement("video-js");
    videoEl.className = "video-js vjs-default-skin";
    videoEl.style.width = "100%";
    videoEl.style.height = "100%";

    containerRef.current.appendChild(videoEl);

    playerRef.current = videojs(videoEl, {
      controls: true,
      responsive: true,
      fluid: true,
      playbackRates: [0.5, 1, 1.25, 1.5, 2],
    });

    // Use the stream URL directly for HTTP video playback
    playerRef.current.src({ src: streamUrl, type: "video/mp4" });

    playerRef.current.ready(() => {
      setupHighlightComponent();
      setupPlayerEvents();
      playerRef.current.play().catch(console.error);
    });
  };

  /* ---------- IFRAME STREAMING (for webpage URLs) ---------- */

  /* ---------- NATIVE HLS STREAMING (for .m3u8 URLs) ---------- */

  /* ---------- TIMELINE HIGHLIGHTS (only for Video.js playback) ---------- */

  const setupHighlightComponent = () => {
    if (!playerRef.current) return;

    const seekBar = playerRef.current.controlBar.progressControl.seekBar;
    const Component = videojs.getComponent("TimelineHighlights") as any;
    highlightComponentRef.current = new Component(playerRef.current, {});

    seekBar.el().style.position = "relative";
    if (highlightComponentRef.current) {
      seekBar.el().appendChild(highlightComponentRef.current.el());
    }
  };

  const setupPlayerEvents = () => {
    if (!playerRef.current) return;

    playerRef.current.on("durationchange", () => {
      const d = playerRef.current.duration();
      setDuration(d);
      highlightComponentRef.current?.updateHighlights(highlights);
    });
  };

  useEffect(() => {
    if (highlightComponentRef.current && duration > 0) {
      highlightComponentRef.current.updateHighlights(highlights);
    }
  }, [highlights, duration]);

  /* ---------- CUSTOM EVENTS ---------- */

  useEffect(() => {
    const seekHandler = (e: Event) => {
      const ev = e as SeekVideoEvent;
      // Only works for Video.js playback mode
      if (playerRef.current && mode === "playback") {
        playerRef.current.currentTime(ev.detail.timestamp);
      }
    };

    const highlightHandler = (e: Event) => {
      const ev = e as HighlightTimelineEvent;
      
      // Filter: only add highlight if targetCamera matches this player's camera
      // If no targetCamera specified, accept all (backwards compatibility)
      // If no camera specified for this player, accept all (streaming mode)
      if (ev.detail.targetCamera && camera && ev.detail.targetCamera !== camera) {
        console.log(`[HLSPlayer] Ignoring highlight for ${ev.detail.targetCamera}, this is ${camera}`);
        return;
      }

      console.log(`[HLSPlayer-${camera || 'unknown'}] Adding highlight: ${ev.detail.topic}`);
      setHighlights((p) => [...p, ev.detail]);
    };

    window.addEventListener("seekVideoToTimestamp", seekHandler);
    window.addEventListener("highlightTimeline", highlightHandler);

    return () => {
      window.removeEventListener("seekVideoToTimestamp", seekHandler);
      window.removeEventListener("highlightTimeline", highlightHandler);
    };
  }, [mode, camera]);

  /* ---------- RENDER ---------- */

  if (mode === "stream") {
    return (
      <div className="hls-player-container">
        {isWebpage && streamUrl ? (
          <iframe
            src={streamUrl}
            scrolling="no"
            width="100%"
            height="100%"
            style={{ border: 'none' }}
            title="Stream Content"
            allowFullScreen
          />
        ) : streamUrl ? (
          <video 
            controls 
            width="100%" 
            height="100%" 
            style={{ backgroundColor: 'black' }}
            autoPlay
          >
            <source src={streamUrl} type="application/vnd.apple.mpegurl" />
            {t("notifications.videoNotSupported")}
          </video>
        ) : (
          <div style={{ 
            color: "white", 
            textAlign: "center", 
            padding: "20px" 
          }}>
            {t("notifications.noVideoConfigured")}
          </div>
        )}
      </div>
    );
  }

  // Playback mode: Video.js player with highlights
  return (
    <div ref={containerRef} className="hls-player-container">
      {!videoFile && !streamUrl && (
        <div style={{ 
          color: "white", 
          textAlign: "center", 
          padding: "20px" 
        }}>
          {t("notifications.noVideoConfigured")}
        </div>
      )}
    </div>
  );
};

export default HLSPlayer;