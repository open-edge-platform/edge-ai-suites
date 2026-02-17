import React, { useEffect, useRef, useState } from "react";
import Hls from "hls.js";

interface Props {
  streamUrl?: string;
  videoFile?: File;
  mode: "stream" | "playback";
}

const HLSPlayer: React.FC<Props> = ({
  streamUrl,
  videoFile,
  mode
}) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;

    if (!video) return;

    video.pause();
    video.removeAttribute("src");
    video.load();

    if (mode === "playback" && videoFile) {
      const fileUrl = URL.createObjectURL(videoFile);
      video.src = fileUrl;
      video.onloadedmetadata = () => {
        video.play().catch(console.error);
      };
      return () => URL.revokeObjectURL(fileUrl);
    }

    if (mode === "stream" && streamUrl && streamUrl.endsWith('.m3u8')) {
      if (Hls.isSupported()) {
        const hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
        });

        hls.loadSource(streamUrl);
        hls.attachMedia(video);

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          console.log("Manifest parsed, playing");
          video.play().catch(console.error);
        });

        hls.on(Hls.Events.ERROR, (_, data) => {
          console.error("HLS error:", data);
        });

        return () => {
          hls.destroy();
        };
      } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = streamUrl;
        video.onloadedmetadata = () => {
          video.play().catch(console.error);
        };
      }
    }

  }, [streamUrl, videoFile, mode]);

  if (mode === "stream" && streamUrl) {
    const isHLSStream = streamUrl.endsWith('.m3u8');
    
    if (!isHLSStream) {
      return (
        <iframe
          src={streamUrl}
          scrolling="no"
          width="100%"
          height="100%"
          style={{ border: 'none' }}
        />
      );
    }
  }

  return (
    <video
      ref={videoRef}
      controls
      muted
      autoPlay
      playsInline
      style={{
        width: "100%",
        height: "100%",
        background: "black"
      }}
    />
  );
};

export default HLSPlayer;