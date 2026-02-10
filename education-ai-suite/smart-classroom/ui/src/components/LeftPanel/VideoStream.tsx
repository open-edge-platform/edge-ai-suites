import React, { useEffect, useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream } from "../../redux/slices/uiSlice";
import HLSPlayer from "../common/HLSPlayer";
import { useTranslation } from "react-i18next";

interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}

const VideoStream: React.FC<VideoStreamProps> = ({ isFullScreen, onToggleFullScreen }) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();

  const [isRoomView, setIsRoomView] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const {
    frontCameraStream,
    backCameraStream,
    boardCameraStream,
    activeStream,
    videoAnalyticsActive,
    videoAnalyticsLoading,
    videoStatus,
    uploadedAudioPath,
    aiProcessing,
  } = useAppSelector((s) => s.ui);

  const transcriptStatus = useAppSelector((s) => s.transcript.status);

  const streams = {
    front: frontCameraStream,
    back: backCameraStream,
    content: boardCameraStream,
  };

  const streamTypes = [
    { pipeline: "front", label: t("accordion.frontCamera") },
    { pipeline: "back", label: t("accordion.backCamera") },
    { pipeline: "content", label: t("accordion.boardCamera") },
    { pipeline: "all", label: t("accordion.allCameras") },
  ];

  const isValidStream = (url?: string | null) =>
    !!url &&
    url.trim() !== "" &&
    (url.startsWith("http") ||
      url.startsWith("rtsp://") ||
      url.includes("/stream") ||
      url.includes(".m3u8"));

  const hasValidStreams = () =>
    isValidStream(streams.front) ||
    isValidStream(streams.back) ||
    isValidStream(streams.content);

  const getAvailableStreams = () => {
    const arr: ("front" | "back" | "content")[] = [];
    if (isValidStream(streams.front)) arr.push("front");
    if (isValidStream(streams.back)) arr.push("back");
    if (isValidStream(streams.content)) arr.push("content");
    return arr;
  };

  const isCurrentlyRecording = () =>
    aiProcessing ||
    uploadedAudioPath === "MICROPHONE" ||
    transcriptStatus === "streaming" ||
    videoAnalyticsActive;

  const getStreamStatus = () => {
    if (videoAnalyticsLoading) return "loading";

    if (videoAnalyticsActive && hasValidStreams()) return "active";

    if (
      (videoStatus === "starting" || videoStatus === "streaming") &&
      !hasValidStreams()
    )
      return "loading";

    if (videoStatus === "failed" && isCurrentlyRecording()) return "video_failed";

    if (isCurrentlyRecording() && !hasValidStreams()) return "audio_only";

    return "inactive";
  };

  useEffect(() => {
    const available = getAvailableStreams();

    if (videoAnalyticsActive && available.length) {
      dispatch(setActiveStream(available.length > 1 ? "all" : available[0]));
    } else {
      dispatch(setActiveStream(null));
    }
  }, [
    frontCameraStream,
    backCameraStream,
    boardCameraStream,
    videoAnalyticsActive,
    dispatch,
  ]);

  const handleStreamClick = (pipeline: "front" | "back" | "content" | "all") => {
    if (pipeline === "all" && !hasValidStreams()) return;

    if (pipeline !== "all" && !isValidStream(streams[pipeline])) return;

    dispatch(setActiveStream(pipeline));
  };

  const streamStatus = getStreamStatus();

  const Spinner = () => (
    <div className="video-analytics-spinner">
      <div className="spinner-circle"></div>
      <p>Loading video streams...</p>
    </div>
  );

  return (
    <div
      className={`video-stream ${isRoomView ? "room-view" : "collapsed"} ${
        isFullScreen ? "full-screen" : ""
      }`}
    >
      <div className="video-stream-header">
        <label className="room-view-toggle">
          <input
            type="checkbox"
            checked={isRoomView}
            onChange={() => setIsRoomView((v) => !v)}
          />
          <span className="toggle-slider"></span>
          <span className="toggle-label">{t("accordion.roomView")}</span>
        </label>

        {isRoomView && (
          <div className="stream-controls">
            {streamTypes.map(({ pipeline, label }) => {
              const isAvailable =
                pipeline === "all"
                  ? hasValidStreams()
                  : isValidStream(streams[pipeline as keyof typeof streams]);

              return (
                <span
                  key={pipeline}
                  className={`stream-control-label ${
                    activeStream === pipeline ? "active" : ""
                  } ${!isAvailable ? "disabled" : ""}`}
                  onClick={() =>
                    isAvailable &&
                    handleStreamClick(
                      pipeline as "front" | "back" | "content" | "all"
                    )
                  }
                >
                  {label}
                </span>
              );
            })}
          </div>
        )}
      </div>

      {isRoomView && (
        <div className="video-stream-body">
          {streamStatus === "loading" && (
            <div className="stream-placeholder">
              <Spinner />
            </div>
          )}

          {streamStatus === "audio_only" && (
            <div className="stream-placeholder">
              <img src={streamingIcon} className="streaming-icon" />
              <h3>Audio Recording Active</h3>
              <p>No video streams detected.</p>
            </div>
          )}

          {streamStatus === "video_failed" && (
            <div className="stream-placeholder">
              <img src={streamingIcon} className="streaming-icon" />
              <h3>Video Failed</h3>
              <p>Continuing with audio-only processing.</p>
            </div>
          )}

          {streamStatus === "inactive" && (
            <div className="stream-placeholder">
              <img src={streamingIcon} className="streaming-icon" />
              <p>{t("videoStream.configureCameras")}</p>
              <button
                className="upload-file-button"
                onClick={() => setIsUploadModalOpen(true)}
              >
                {t("videoStream.uploadFileButton")}
              </button>
            </div>
          )}

          {streamStatus === "active" && (
            <div className="streams-layout">
              {activeStream === "all" && (
                <div className="multi-stream-container">
                  {isValidStream(streams.front) && (
                    <div className="main-stream">
                      <HLSPlayer streamUrl={streams.front!} />
                      <div className="stream-overlay-label">Front</div>
                    </div>
                  )}

                  <div className="side-streams-container">
                    {isValidStream(streams.back) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.back!} />
                        <div className="stream-overlay-label">Back</div>
                      </div>
                    )}

                    {isValidStream(streams.content) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.content!} />
                        <div className="stream-overlay-label">Board</div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeStream !== "all" &&
                activeStream &&
                isValidStream(streams[activeStream]) && (
                  <div className="single-stream">
                    <HLSPlayer streamUrl={streams[activeStream]!} />
                    <div className="stream-overlay-label">
                      {activeStream.toUpperCase()}
                    </div>
                  </div>
                )}
            </div>
          )}
        </div>
      )}

      {isUploadModalOpen && (
        <UploadFilesModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
        />
      )}
    </div>
  );
};

export default VideoStream;
