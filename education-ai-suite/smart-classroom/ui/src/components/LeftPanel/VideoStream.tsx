import React, { useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import fullScreenIcon from "../../assets/images/fullScreenIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream } from "../../redux/slices/uiSlice";
import { startVideoAnalyticsPipeline } from "../../services/api"; 
import { setFrontCamera, setBackCamera, setBoardCamera, setBackCameraStream, setFrontCameraStream, setBoardCameraStream } from "../../redux/slices/uiSlice";
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
  const sessionId = useAppSelector((state) => state.ui.sessionId); // Move this to top level
  const streams = useAppSelector((state) => ({
    front: state.ui.frontCameraStream,
    back: state.ui.backCameraStream,
    content: state.ui.boardCameraStream,
  }));

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

  const handleStreamClick = async (pipeline: "front" | "back" | "content" | "all") => {
    const currentSessionId = sessionId; // Use the sessionId from state
  
    if (!currentSessionId) {
      console.error("Session ID is null. Cannot start video analytics pipeline.");
      return;
    }
  
    try {
      if (pipeline === "all") {
        // Start all three pipelines
        const pipelines = [
          { pipeline_name: "front", source: streams.front },
          { pipeline_name: "back", source: streams.back },
          { pipeline_name: "content", source: streams.content },
        ];
  
        // Validate all streams before starting
        const invalidPipelines = pipelines.filter((p) => !isValidStream(p.source));
        if (invalidPipelines.length > 0) {
          console.error("Invalid streams detected:", invalidPipelines);
          return;
        }
  
        const response = await startVideoAnalyticsPipeline(pipelines, currentSessionId);
  
        // Process each result
        response.results.forEach((result: any) => {
          if (result.status === "success" && result.hls_stream) {
            switch (result.pipeline_name) {
              case "front":
                dispatch(setFrontCamera(result.hls_stream));
                break;
              case "back":
                dispatch(setBackCamera(result.hls_stream));
                break;
              case "content":
                dispatch(setBoardCamera(result.hls_stream));
                break;
            }
          } else if (result.status === "error") {
            console.error(`Error with ${result.pipeline_name}:`, result.error);
          }
        });
  
        dispatch(setActiveStream("all"));
      } else {
        // Start individual pipeline
        let source = "";
        switch (pipeline) {
          case "front":
            source = streams.front;
            break;
          case "back":
            source = streams.back;
            break;
          case "content":
            source = streams.content;
            break;
        }
  
        // Validate the stream before starting
        if (!isValidStream(source)) {
          console.error(`Invalid stream for ${pipeline}:`, source);
          return;
        }
  
        // Prevent duplicate requests
        if (activeStream === pipeline) {
          console.log(`Pipeline ${pipeline} is already running.`);
          return;
        }
  
        const pipelines = [{ pipeline_name: pipeline, source }];
        const response = await startVideoAnalyticsPipeline(pipelines, currentSessionId);
        const result = response.results[0];
  
        if (result.status === "success" && result.hls_stream) {
          // Update the appropriate camera stream based on pipeline_name from response
          switch (result.pipeline_name) {
            case "front":
              dispatch(setFrontCameraStream(result.hls_stream));
              break;
            case "back":
              dispatch(setBackCameraStream(result.hls_stream));
              break;
            case "content":
              dispatch(setBoardCameraStream(result.hls_stream));
              break;
          }
          dispatch(setActiveStream(result.pipeline_name as "front" | "back" | "content"));
        } else if (result.status === "error") {
          console.error(`Error starting ${pipeline}:`, result.error);
        }
      }
    } catch (error) {
      console.error("Failed to start video analytics pipeline:", error);
    }
  };
  
  const isValidStream = (stream: string | null) => {
    // Check if the stream is a valid URL
    return stream && (stream.startsWith("http://") || stream.startsWith("https://") || stream.startsWith("rtsp://"));
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
          onClick={handleFullScreenToggle}
        />
      </div>
        
      {isRoomView && (
        <div className="video-stream-body">
          {activeStream === null ? (
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
          ) : Object.values(streams).every((stream) => !isValidStream(stream)) ? (
            <div className="stream-placeholder">
              <p>No video streams available. Please upload files to start streaming.</p>
            </div>
          ) : (
            <div className={`stream-container ${activeStream === "all" ? "split-screen" : ""}`}>
            {activeStream === "all" && (
              <>
                {streams.front && <HLSPlayer streamUrl={streams.front} />}
                {streams.back && <HLSPlayer streamUrl={streams.back} />}
                {streams.content&& <HLSPlayer streamUrl={streams.content} />}
              </>
            )}
            {activeStream === "front" && streams.front && <HLSPlayer streamUrl={streams.front} />}
            {activeStream === "back" && streams.back && <HLSPlayer streamUrl={streams.back} />}
            {activeStream === "content" && streams.content && <HLSPlayer streamUrl={streams.content} />}
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