import React, { useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import fullScreenIcon from "../../assets/images/fullScreenIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream } from "../../redux/slices/uiSlice";
import HLSPlayer from "../common/HLSPlayer";
import { useTranslation } from "react-i18next";
interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}
 
const VideoStream: React.FC<VideoStreamProps> = ({ isFullScreen, onToggleFullScreen }) => {
  const [isRoomView, setIsRoomView] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const activeStream = useAppSelector((state) => state.ui.activeStream);
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const videoAnalyticsLoading = useAppSelector((state) => state.ui.videoAnalyticsLoading);
  const videoAnalyticsActive = useAppSelector((state) => state.ui.videoAnalyticsActive);
  const isRecording = useAppSelector((state) => state.ui.aiProcessing);
  const uploadedAudioPath = useAppSelector((state) => state.ui.uploadedAudioPath);
  const transcriptStatus = useAppSelector((state) => state.transcript.status);
  const videoStatus = useAppSelector((state) => state.ui.videoStatus);
  const streams = useAppSelector((state) => ({
    front: state.ui.frontCameraStream,
    back: state.ui.backCameraStream,
    content: state.ui.boardCameraStream,
  }));
  const streamTypes = [
  { pipeline: "front", label: t("accordion.frontCamera") },
  { pipeline: "back", label: t("accordion.backCamera") },
  { pipeline: "content", label: t("accordion.boardCamera") },
  { pipeline: "all", label: t("accordion.allCameras") }
  ];
  const isValidStream = (stream: string | null): boolean => {
    const isValid = stream && stream.trim() !== '' && (
      stream.startsWith("http://") ||
      stream.startsWith("https://") ||
      stream.startsWith("rtsp://") ||
      stream.includes("/stream") ||
      stream.includes(".m3u8")
    );
    return !!isValid;
  };
 
  const hasValidStreams = (): boolean => {
    return isValidStream(streams.front) || isValidStream(streams.back) || isValidStream(streams.content);
  };

  const getAvailableStreams = () => {
    const available = [];
    if (isValidStream(streams.front)) available.push('front');
    if (isValidStream(streams.back)) available.push('back');
    if (isValidStream(streams.content)) available.push('content');
    return available;
  };

  const isCurrentlyRecording = () => {
    return isRecording || 
           uploadedAudioPath === 'MICROPHONE' || 
           transcriptStatus === 'streaming' ||
           videoAnalyticsActive;
  };

  const getStreamStatus = () => {
    if (videoAnalyticsLoading) {
      return "loading";
    }
    
    if (videoAnalyticsActive && hasValidStreams()) {
      return "active";
    }
    
    const currentlyRecording = isCurrentlyRecording();
    if (videoStatus === 'starting' || videoStatus === 'streaming') {
      return "loading";
    }
    if (videoStatus === 'failed' && currentlyRecording) {
      return "video_failed";
    }
    if (currentlyRecording && hasValidStreams() && !videoAnalyticsActive && !videoAnalyticsLoading) {
      return "video_failed";
    } 
    if (currentlyRecording && !hasValidStreams() && !videoAnalyticsActive && !videoAnalyticsLoading) {
      return "audio_only";
    }
    return "inactive";
  };

  React.useEffect(() => {
    const availableStreams = getAvailableStreams();
    if (availableStreams.length > 0 && videoAnalyticsActive) {
      if (availableStreams.length > 1) {
        dispatch(setActiveStream('all'));
      } else {
        dispatch(setActiveStream(availableStreams[0] as "front" | "back" | "content"));
      }
    } else if (!videoAnalyticsActive) {
      dispatch(setActiveStream(null));
    }
  }, [streams.front, streams.back, streams.content, videoAnalyticsActive, dispatch]);
 
  const handleToggleRoomView = () => {
    setIsRoomView(!isRoomView);
    console.log("Room View Toggled:", !isRoomView);
  };
 
  const handleFullScreenToggle = () => {
    onToggleFullScreen();
    const container = document.querySelector(".container");
    if (container) {
      container.classList.toggle("fullscreen", !isFullScreen);
    }
  };
 
  const handleStreamClick = (pipeline: "front" | "back" | "content" | "all") => {
    console.log(`Switching to ${pipeline} stream view`);
    if (pipeline === "all") {
      if (!hasValidStreams()) {
        console.warn("No valid streams available to display");
        return;
      }
    } else {
      const streamUrl = streams[pipeline];
      if (!isValidStream(streamUrl)) {
        console.warn(`${pipeline} stream is not available:`, streamUrl);
        return;
      }
    }
    dispatch(setActiveStream(pipeline));
  };
 
  const Spinner = () => (
    <div className="video-analytics-spinner">
      <div className="spinner-circle"></div>
      <p>Loading video streams...</p>
    </div>
  );

  const streamStatus = getStreamStatus();
 
  return (
    <div className={`video-stream ${isRoomView ? "room-view" : "collapsed"} ${isFullScreen ? "full-screen" : ""}`}>
      <div className="video-stream-header">
        <div className="room-view-toggle-wrapper">
          <label className="room-view-toggle">
            <input
              type="checkbox"
              checked={isRoomView}
              onChange={handleToggleRoomView}
            />
            <span className="toggle-slider"></span>
            <span className="toggle-label">{t('accordion.roomView')}</span>
          </label>
        </div>
        {isRoomView && (
          <div className="stream-controls">
          {streamTypes.map(({ pipeline, label }) => {
            const isAvailable = pipeline === "all"
              ? hasValidStreams()
              : isValidStream(streams[pipeline as keyof typeof streams]);
        
            return (
              <span
                key={pipeline}
                className={`stream-control-label ${activeStream === pipeline ? "active" : ""} ${!isAvailable || videoAnalyticsLoading ? "disabled" : ""}`}
                onClick={() => !videoAnalyticsLoading && isAvailable && handleStreamClick(pipeline as "front" | "back" | "content" | "all")}
                style={{
                  opacity: isAvailable && !videoAnalyticsLoading ? 1 : 0.5,
                  cursor: isAvailable && !videoAnalyticsLoading ? "pointer" : "not-allowed"
                }}
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
          {streamStatus === "loading" ? (
            <div className="stream-placeholder">
              <Spinner />
              <p>
                {videoAnalyticsActive 
                  ? "Stopping video analytics..." 
                  : "Initializing video analytics..."
                }
              </p>
            </div>
          ) : streamStatus === "audio_only" ? (
            <div className="stream-placeholder">
              <img
                src={streamingIcon}
                alt="Audio Recording Icon"
                className="streaming-icon"
              />
              <p>Video analytics service may not be available or cameras not configured.</p>
              <small>Configure cameras in settings to enable video analytics.</small>
            </div>
          ) : streamStatus === "video_failed" ? (
            <div className="stream-placeholder">
              <img
                src={streamingIcon}
                alt="Video Failed Icon"
                className="streaming-icon"
              />
              <h3>Audio Recording Active</h3>
              <p>Video analytics attempted but failed to start.</p>
              <p>Continuing with audio-only recording.</p>
              <small>Check camera configurations or backend video service.</small>
            </div>
          ) : streamStatus === "inactive" ? (
            <div className="stream-placeholder">
              <img
                src={streamingIcon}
                alt="Streaming Icon"
                className="streaming-icon"
              />
<p>{t('videoStream.configureCameras')}</p>
            <p>{t('videoStream.uploadFilesToStart')}</p>
              <button
                className="upload-file-button"
                onClick={() => setIsUploadModalOpen(true)}
              >
                {t('videoStream.uploadFileButton')}
              </button>
            </div>
          ) : streamStatus === "active" && hasValidStreams() ? (
            <div className="streams-layout">
              {activeStream === "all" && (
                <div className="multi-stream-container">
                  {streams.front && isValidStream(streams.front) && (
                    <div className="main-stream">
                      <HLSPlayer streamUrl={streams.front} />
                      <div className="stream-overlay-label">Front Camera</div>
                    </div>
                  )}
                 
                  <div className="side-streams-container">
                    {streams.back && isValidStream(streams.back) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.back} />
                        <div className="stream-overlay-label">Back Camera</div>
                      </div>
                    )}
                    {streams.content && isValidStream(streams.content) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.content} />
                        <div className="stream-overlay-label">Board Camera</div>
                      </div>
                    )}
                  </div>
                </div>
              )}
             
              {activeStream === "front" && streams.front && isValidStream(streams.front) && (
                <div className="single-stream">
                  <HLSPlayer streamUrl={streams.front} />
                  <div className="stream-overlay-label">Front Camera</div>
                </div>
              )}
             
              {activeStream === "back" && streams.back && isValidStream(streams.back) && (
                <div className="single-stream">
                  <HLSPlayer streamUrl={streams.back} />
                  <div className="stream-overlay-label">Back Camera</div>
                </div>
              )}
             
              {activeStream === "content" && streams.content && isValidStream(streams.content) && (
                <div className="single-stream">
                  <HLSPlayer streamUrl={streams.content} />
                  <div className="stream-overlay-label">Board Camera</div>
                </div>
              )}
            </div>
          ) : (
            <div className="stream-placeholder">
              <img
                src={streamingIcon}
                alt="Streaming Icon"
                className="streaming-icon"
              />
              <p>Configure cameras in settings to enable video analytics</p>
              <p>Or upload audio/video files to get started</p>
              <button
                className="upload-file-button"
                onClick={() => setIsUploadModalOpen(true)}
              >
                Upload File
              </button>
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