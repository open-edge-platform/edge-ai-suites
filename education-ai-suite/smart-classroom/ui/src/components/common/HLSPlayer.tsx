import React, { useEffect, useRef, useState } from "react";
import videojs from "video.js";
import Hls from "hls.js";
import "video.js/dist/video-js.css";
import { useTranslation } from 'react-i18next';

interface Props {
  streamUrl?: string;
  videoFile?: File;
  mode: "stream" | "playback";
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
  detail: TimelineHighlight;
}

/* ---------------- TIMELINE HIGHLIGHT COMPONENT ---------------- */
const { t } = useTranslation();
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
      const width = ((h.endTime - h.startTime) / duration) * 100;

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

const HLSPlayer: React.FC<Props> = ({ streamUrl, videoFile, mode }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<any>(null);
  const highlightComponentRef = useRef<TimelineHighlights | null>(null);

  const [duration, setDuration] = useState(0);
  const [highlights, setHighlights] = useState<TimelineHighlight[]>([]);

  // Determine if streamUrl is a webpage or HLS stream
  const isWebpage = streamUrl && !streamUrl.endsWith('.m3u8');
  const isHLSStream = streamUrl && streamUrl.endsWith('.m3u8');

  console.log("Stream Analysis:", { 
    streamUrl, 
    isWebpage, 
    isHLSStream, 
    mode 
  });

  /* ---------- PLAYER INITIALIZATION ---------- */

  useEffect(() => {
    if (!containerRef.current) return;

    cleanup();

    if (mode === "playback") {
      initVideoJS();
    } else if (mode === "stream") {
      if (isWebpage) {
        initIframe();
      } else if (isHLSStream) {
        initNativeHLS();
      }
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

  /* ---------- IFRAME STREAMING (for webpage URLs) ---------- */

  const initIframe = () => {
    if (!containerRef.current || !streamUrl) return;

    console.log("Initializing iframe for webpage:", streamUrl);

    const iframe = document.createElement("iframe");
    iframe.src = streamUrl;
    iframe.scrolling = "no";
    iframe.style.width = "100%";
    iframe.style.height = "100%";
    iframe.style.border = "none";

    containerRef.current.appendChild(iframe);
  };

  /* ---------- NATIVE HLS STREAMING (for .m3u8 URLs) ---------- */

  const initNativeHLS = () => {
    if (!containerRef.current || !streamUrl) return;

    console.log("Initializing native HLS for stream:", streamUrl);

    const video = document.createElement("video");
    video.controls = true;
    video.autoplay = true;
    video.muted = true;
    video.playsInline = true;
    video.style.width = "100%";
    video.style.height = "100%";
    video.style.background = "black";

    // Add source element (like your original code)
    const source = document.createElement("source");
    source.src = streamUrl;
    source.type = "application/vnd.apple.mpegurl";
    video.appendChild(source);

    containerRef.current.appendChild(video);

    // Add event listeners for debugging
    video.addEventListener("loadedmetadata", () => {
      console.log("HLS metadata loaded");
    });

    video.addEventListener("canplay", () => {
      console.log("HLS can play");
      video.play().catch(console.error);
    });

    video.addEventListener("error", (e) => {
      console.error("HLS video error:", e);
      console.error("Video error details:", video.error);
    });

    // If native HLS fails, try HLS.js as fallback
    video.addEventListener("error", () => {
      if (Hls.isSupported()) {
        console.log("Native HLS failed, trying HLS.js");
        initHLSJSFallback(video);
      }
    });
  };

  /* ---------- HLS.JS FALLBACK ---------- */

  const initHLSJSFallback = (video: HTMLVideoElement) => {
    if (!streamUrl) return;

    const hls = new Hls({
      lowLatencyMode: false,
      debug: true,
    });

    hls.on(Hls.Events.ERROR, (event, data) => {
      console.error("HLS.js Error:", data);
    });

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      console.log("HLS.js manifest parsed");
      video.play().catch(console.error);
    });

    hls.loadSource(streamUrl);
    hls.attachMedia(video);
  };

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
      setHighlights((p) => [...p, ev.detail]);
    };

    window.addEventListener("seekVideoToTimestamp", seekHandler);
    window.addEventListener("highlightTimeline", highlightHandler);

    return () => {
      window.removeEventListener("seekVideoToTimestamp", seekHandler);
      window.removeEventListener("highlightTimeline", highlightHandler);
    };
  }, [mode]);

  /* ---------- RENDER ---------- */

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        background: "black",
        transform: "scale(0.8)",
        transformOrigin: "center",
      }}
    >
      {/* Show info about what's being loaded */}
      {mode === "stream" && !streamUrl && (
        <div style={{ 
          color: "white", 
          textAlign: "center", 
          padding: "20px" 
        }}>
          {t("notifications.noVideoConfigured")}
        </div>
      )}
      
      {mode === "playback" && !videoFile && (
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