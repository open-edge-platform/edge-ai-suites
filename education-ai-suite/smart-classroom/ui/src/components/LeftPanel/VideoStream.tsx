import React, { useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import fullScreenIcon from "../../assets/images/fullScreenIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream } from "../../redux/slices/uiSlice";
import HLSPlayer from "../common/HLSPlayer";
 
interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}
 
const VideoStream: React.FC<VideoStreamProps> = ({ isFullScreen, onToggleFullScreen }) => {
  const [isRoomView, setIsRoomView] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
 
  const dispatch = useAppDispatch();
  const activeStream = useAppSelector((state) => state.ui.activeStream);
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const videoAnalyticsLoading = useAppSelector((state) => state.ui.videoAnalyticsLoading);
  const streams = useAppSelector((state) => ({
    front: state.ui.frontCameraStream,
    back: state.ui.backCameraStream,
    content: state.ui.boardCameraStream,
  }));
 
  const isValidStream = (stream: string | null): boolean => {
    const isValid = stream && (
      stream.startsWith("http://") ||
      stream.startsWith("https://") ||
      stream.startsWith("rtsp://")
    );
    return !!isValid;
  };
 
  const hasValidStreams = (): boolean => {
    return isValidStream(streams.front) || isValidStream(streams.back) || isValidStream(streams.content);
  };
 
  console.log('VideoStream Debug:', {
    activeStream,
    streams,
    isValidStreams: {
      front: isValidStream(streams.front),
      back: isValidStream(streams.back),
      content: isValidStream(streams.content)
    }
  });
 
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
            <span className="toggle-label">Room View</span>
          </label>
        </div>
        {isRoomView && (
          <div className="stream-controls">
            {["front", "back", "content", "all"].map((pipeline) => {
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
                    cursor: isAvailable && !videoAnalyticsLoading ? 'pointer' : 'not-allowed'
                  }}
                >
                  {pipeline.charAt(0).toUpperCase() + pipeline.slice(1)}
                  {videoAnalyticsLoading && <span className="control-spinner" />}
                </span>
              );
            })}
          </div>
        )}
        <img
          src={fullScreenIcon}
          alt="Fullscreen Icon"
          className="fullscreen-icon"
          onClick={handleFullScreenToggle}
        />
      </div>
       
      {isRoomView && (
        <div className="video-stream-body">
          {videoAnalyticsLoading ? (
            <div className="stream-placeholder">
              <Spinner />
              <p>Initializing video analytics...</p>
            </div>
          ) : activeStream === null ? (
            <div className="stream-placeholder">
              <img
                src={streamingIcon}
                alt="Streaming Icon"
                className="streaming-icon"
              />
              <p>Go to settings to configure your recorders or upload audio/video files</p>
              <button
                className="upload-file-button"
                onClick={() => setIsUploadModalOpen(true)}
              >
                Upload File
              </button>
            </div>
          ) : !hasValidStreams() ? (
            <div className="stream-placeholder">
              <p>No video streams available. Please upload files to start streaming.</p>
              <button
                className="upload-file-button"
                onClick={() => setIsUploadModalOpen(true)}
              >
                Upload File
              </button>
            </div>
          ) : (
            <div className="streams-layout">
              {activeStream === "all" && (
                <div className="multi-stream-container">
                  {/* Main front camera stream */}
                  {streams.front && isValidStream(streams.front) && (
                    <div className="main-stream">
                      <HLSPlayer streamUrl={streams.front} />
                      <div className="stream-overlay-label">Front Camera</div>
                    </div>
                  )}
                 
                  {/* Side streams */}
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