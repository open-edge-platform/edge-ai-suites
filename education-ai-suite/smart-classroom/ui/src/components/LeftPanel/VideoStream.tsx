import React, { useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import fullScreenIcon from "../../assets/images/fullScreenIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream } from "../../redux/slices/uiSlice";

interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}

const VideoStream: React.FC<VideoStreamProps> = ({ isFullScreen, onToggleFullScreen }) => {
  const [isRoomView, setIsRoomView] = useState(true);
  const activeStream = useAppSelector((state) => state.ui.activeStream);
  const streams = useAppSelector((state) => ({
    front: state.ui.frontCamera,
    back: state.ui.backCamera,
    content: state.ui.boardCamera,
  }));
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const dispatch = useAppDispatch();

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
    dispatch(setActiveStream(pipeline));
  };
  const isValidStream = (stream: string | null) => {
    // Check if the stream is a valid URL
    return stream && stream.startsWith("http");
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
                onClick={() => handleStreamClick(pipeline as "front" | "back" | "content" | "all")}
              >
                {pipeline.charAt(0).toUpperCase() + pipeline.slice(1)}
              </span>
            ))}
          </div>
        )}
        <img
          src={fullScreenIcon}
          alt="Fullscreen Icon"
          className="fullscreen-icon"
        />
      </div>
        {/* <button className="fullscreen-toggle" onClick={handleFullScreenToggle}>
          {isFullScreen ? "Exit Fullscreen" : "Fullscreen"}
        </button> */}
      /
      {isRoomView && (
        <div className="video-stream-body">
          {
          activeStream === null ? (
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
          ) : Object.values(streams).every((stream) => !isValidStream(stream)) ? ( // Check if all streams are invalid
            <div className="stream-placeholder">
              <p>No video streams available. Please upload files to start streaming.</p>
            </div>
        ) :  (
          <div className={`stream-container ${activeStream === "all" ? "split-screen" : ""}`}>
            {activeStream === "all" && (
              <>
                {streams.front && <iframe src={streams.front} scrolling="no" width="100%" height="auto" />}
                {streams.back && <iframe src={streams.back} scrolling="no" width="100%" height="auto" />}
                {streams.content && <iframe src={streams.content} scrolling="no" width="100%" height="auto" />}
              </>
            )}
            {activeStream === "front" && streams.front && <iframe src={streams.front} scrolling="no" width="100%" height="auto" />}
            {activeStream === "back" && streams.back && <iframe src={streams.back} scrolling="no" width="100%" height="auto" />}
            {activeStream === "content" && streams.content && <iframe src={streams.content} scrolling="no" width="100%" height="auto" />}
          </div>
        )}
      </div>
        // <div className="video-stream-body">
        //   {activeStream === null ? ( // Show placeholder by default
        //     <div className="stream-placeholder">
        //       <img
        //       src={streamingIcon}
        //       alt="Streaming Icon"
        //       className="streaming-icon"
        //     />
        //       <p>Go to settings to configure your recorders or upload audio/video files</p>
        //       <button
        //         className="upload-file-button"
        //         onClick={() => setIsUploadModalOpen(true)}
        //       >
        //         Upload File
        //       </button>
        //     </div>
        //   ) :(
        //   // {Object.keys(streams).length > 0 ? (
        //     <div className={`stream-container ${activeStream === "all" ? "split-screen" : ""}`}>
        //       {/* Render all streams in split-screen layout when "All" is selected */}
        //       {activeStream === "all" && (
        //         <>
        //           {streams.front && (
        //             <iframe
        //               src={streams.front}
        //               scrolling="no"
        //               width="100%"
        //               height="auto"
        //               style={{ border: "none" }}
        //             />
        //           )}
        //           {streams.back && (
        //             <iframe
        //               src={streams.back}
        //               scrolling="no"
        //               width="100%"
        //               height="auto"
        //               style={{ border: "none" }}
        //             />
        //           )}
        //           {streams.content && (
        //             <iframe
        //               src={streams.content}
        //               scrolling="no"
        //               width="100%"
        //               height="auto"
        //               style={{ border: "none" }}
        //             />
        //           )}
        //         </>
        //       )}

        //       {/* Render individual streams when a specific stream is selected */}
        //       {activeStream === "front" && streams.front && (
        //         <iframe
        //           src={streams.front}
        //           scrolling="no"
        //           width="100%"
        //           height="auto"
        //           style={{ border: "none" }}
        //         />
        //       )}
        //       {activeStream === "back" && streams.back && (
        //         <iframe
        //           src={streams.back}
        //           scrolling="no"
        //           width="100%"
        //           height="auto"
        //           style={{ border: "none" }}
        //         />
        //       )}
        //       {activeStream === "content" && streams.content && (
        //         <iframe
        //           src={streams.content}
        //           scrolling="no"
        //           width="100%"
        //           height="auto"
        //           style={{ border: "none" }}
        //         />
        //       )}
        //     </div>
        //   ) }
        //</div>
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