import React, { useState } from "react";
import "../../assets/css/VideoStream.css";
import HLSPlayer from "../common/HLSPlayer";
import UploadFilesModal from "../Modals/UploadFilesModal";
import fullScreenIcon from "../../assets/images/fullScreenIcon.svg";
import streamingIcon from "../../assets/images/streamingIcon.svg";
interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}


const VideoStream: React.FC<VideoStreamProps> = ({ isFullScreen, onToggleFullScreen }) => {
  const [isRoomView, setIsRoomView] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [streams, setStreams] = useState<{ front?: string; back?: string; content?: string }>({});
  const [activeStream, setActiveStream] = useState<'front' | 'back' | 'content' | 'all' | null>(null);
  //const [isFullScreen, setIsFullScreen] = useState(false);

  const handleToggleRoomView = () => {
    setIsRoomView(!isRoomView);
  };

  // const handleFullScreenToggle = () => {
  //   setIsFullScreen(!isFullScreen);
  //   document.querySelector(".container")?.classList.toggle("fullscreen", !isFullScreen);
  // };
  const handleFullScreenToggle = () => {
    onToggleFullScreen();
    const container = document.querySelector(".container");
    if (container) {
      container.classList.toggle("fullscreen", !isFullScreen);
    }
  };
  const handleApplyFiles = (paths: { frontCameraPath?: string; rearCameraPath?: string; boardCameraPath?: string }) => {
    // Update streams only if paths are provided
    setStreams((prevStreams) => ({
      front: paths.frontCameraPath || prevStreams.front,
      back: paths.rearCameraPath || prevStreams.back,
      content: paths.boardCameraPath || prevStreams.content,
    }));
    setIsUploadModalOpen(false);
  };

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
            {["front", "back", "content", "all"].map((pipeline) => (
              <span
                key={pipeline}
                className={`stream-label ${activeStream === pipeline ? "active" : ""}`}
                onClick={() => setActiveStream(pipeline as 'front' | 'back' | 'content' | 'all')}
              >
                {pipeline.charAt(0).toUpperCase() + pipeline.slice(1)}
              </span>
            ))}
            <img
              src={fullScreenIcon}
              alt="Full Screen Disabled"
              className="full-screen-icon"
              style={{ cursor: 'not-allowed', opacity: 0.5 }} // Disable the icon
            />
          </div>
        )}
      </div>

      {isRoomView && (
        <div className="video-stream-body">
          {Object.keys(streams).length > 0 ? (
            <div className={`stream-container ${Object.keys(streams).length === 3 ? "split-screen" : ""}`}>
              {activeStream === null || activeStream === "all" ? (
                <>
                  {streams.front && <HLSPlayer streamUrl={streams.front} />}
                  {streams.back && <HLSPlayer streamUrl={streams.back} />}
                  {streams.content && <HLSPlayer streamUrl={streams.content} />}
                </>
              ) : (
                <>
                  {activeStream === "front" && streams.front && <HLSPlayer streamUrl={streams.front} />}
                  {activeStream === "back" && streams.back && <HLSPlayer streamUrl={streams.back} />}
                  {activeStream === "content" && streams.content && <HLSPlayer streamUrl={streams.content} />}
                </>
              )}
            </div>
          ) : (
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
          )}
        </div>
      )}
      {isUploadModalOpen && (
        <UploadFilesModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
         /// onApply={handleApplyFiles}
        />
      )}
    </div>
  );
};

export default VideoStream;