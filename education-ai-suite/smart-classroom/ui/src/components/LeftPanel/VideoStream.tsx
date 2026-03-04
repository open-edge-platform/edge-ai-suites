import React, { useEffect, useState } from "react";
import "../../assets/css/VideoStream.css";
import UploadFilesModal from "../Modals/UploadFilesModal";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import { useAppSelector, useAppDispatch } from "../../redux/hooks";
import { setActiveStream, setVideoPlaybackMode } from "../../redux/slices/uiSlice";
import HLSPlayer from "../common/HLSPlayer";
import { useTranslation } from "react-i18next";
import { getRecordedVideoUrl } from "../../services/api";

interface VideoStreamProps {
  isFullScreen: boolean;
  onToggleFullScreen: () => void;
}

const VideoStream: React.FC<VideoStreamProps> = ({
  isFullScreen,
}) => {
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
    uploadedVideoFiles,
    sessionId,
    recordedVideoType,
  } = useAppSelector((s) => s.ui);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const mindmapState = useAppSelector((s) => s.mindmap);
  const hasUploadedVideoFiles = useAppSelector((s) => s.ui.hasUploadedVideoFiles);
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
  
  const hasAudio = Boolean(uploadedAudioPath);

  const isMindmapDone =
    audioStatus === "complete" ||
    audioStatus === "error";

  const areStreamsStopped =
    videoStatus === "completed" ||
    videoStatus === "ready" ||
    videoStatus === "no-config" ||
    videoStatus === "failed";

  const audioReady = !hasAudio || isMindmapDone;
  const videoReady = !hasUploadedVideoFiles || areStreamsStopped;

  const isUploadEnabled = audioReady && videoReady;

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

  const isPlaybackMode = Boolean(
    videoStatus === "completed" &&
    (uploadedVideoFiles.front ||
     uploadedVideoFiles.back ||
     uploadedVideoFiles.board ||
     recordedVideoType)
  );

  const getAvailableVideoFiles = () => {
    const available: Array<{
      type: "front" | "back" | "content";
      file: File;
      label: string;
    }> = [];

    if (uploadedVideoFiles.front)
      available.push({
        type: "front",
        file: uploadedVideoFiles.front,
        label: t("accordion.frontCamera"),
      });

    if (uploadedVideoFiles.back)
      available.push({
        type: "back",
        file: uploadedVideoFiles.back,
        label: t("accordion.backCamera"),
      });

    if (uploadedVideoFiles.board)
      available.push({
        type: "content",
        file: uploadedVideoFiles.board,
        label: t("accordion.boardCamera"),
      });

    return available;
  };

  const getStreamStatus = () => {

    if (isPlaybackMode) return "playback";
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
    console.log('🎬 VideoStream state:', {
      isPlaybackMode,
      recordedVideoType,
      videoStatus,
      videoAnalyticsActive,
      activeStream,
      streamStatus: getStreamStatus()
    });
  }, [isPlaybackMode, recordedVideoType, videoStatus, videoAnalyticsActive, activeStream]);

  useEffect(() => {
    if (isPlaybackMode) return;

    const available = getAvailableStreams();
    
    console.log('🎥 Checking streams:', {
      videoAnalyticsActive,
      available,
      frontCameraStream,
      backCameraStream,
      boardCameraStream,
      hasValidStreams: hasValidStreams(),
    });

    if (videoAnalyticsActive && available.length) {
      const streamToSet = available.length > 1 ? "all" : available[0];
      console.log('🎥 Setting activeStream to:', streamToSet);
      dispatch(setActiveStream(streamToSet));
    } else {
      console.log('🎥 No valid streams, setting activeStream to null');
      dispatch(setActiveStream(null));
    }
  }, [
    frontCameraStream,
    backCameraStream,
    boardCameraStream,
    videoAnalyticsActive,
    isPlaybackMode,
    dispatch,
  ]);


  useEffect(() => {
    if (!isPlaybackMode) return;

    // If it's a recorded video, set active stream to the recorded video type
    if (recordedVideoType) {
      const activeStreamValue = recordedVideoType === 'board' ? 'content' : recordedVideoType;
      dispatch(setActiveStream(activeStreamValue as 'front' | 'back' | 'content'));
      return;
    }

    // Otherwise, handle uploaded video files
    const availableFiles = getAvailableVideoFiles();
    if (availableFiles.length > 0) {
      const priority = availableFiles.find(f => f.type === "back") ||
                      availableFiles.find(f => f.type === "content") ||
                      availableFiles[0];
      
      dispatch(setActiveStream(priority.type));
    }
  }, [isPlaybackMode, uploadedVideoFiles, recordedVideoType, dispatch]);

  const handleStreamClick = (pipeline: "front" | "back" | "content" | "all") => {
    if (isPlaybackMode) {
      dispatch(setActiveStream(pipeline));
      return;
    }

    if (pipeline === "all" && !hasValidStreams()) return;
    if (pipeline !== "all" && !isValidStream(streams[pipeline])) return;

    dispatch(setActiveStream(pipeline));
  };

  const streamStatus = getStreamStatus();
  const Spinner = () => (
    <div className="video-analytics-spinner">
      <div className="spinner-circle"></div>
      <p>{t("videoStream.loadingvideo")}</p>
    </div>
  );

  return (
    <div
      className={`video-stream ${isRoomView ? "room-view" : "collapsed"} ${isFullScreen ? "full-screen" : ""}`}
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
            {(isPlaybackMode && recordedVideoType
              ? [{ 
                  pipeline: recordedVideoType === 'board' ? 'content' : recordedVideoType, 
                  label: {
                    back: t("accordion.backCamera"),
                    board: t("accordion.boardCamera"),
                    front: t("accordion.frontCamera"),
                  }[recordedVideoType] as string 
                }]
              : isPlaybackMode && !recordedVideoType
              ? getAvailableVideoFiles().map(({ type, label }) => ({
                  pipeline: type,
                  label,
                }))
              : streamTypes
            ).map(({ pipeline, label }) => {
              const isAvailable = isPlaybackMode
                ? true 
                : pipeline === "all"
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
              <p>{t("videoStream.noStream")}</p>
            </div>
          )}

          {streamStatus === "video_failed" && (
            <div className="stream-placeholder">
              <img src={streamingIcon} className="streaming-icon" />
              <h3>{t("videoStream.videoFailed")}</h3>
              <p>{t("videoStream.continuingAudioOnly")}</p>
            </div>
          )}

          {streamStatus === "inactive" && (
            <div className="stream-placeholder">
              <img src={streamingIcon} className="streaming-icon" />
              <p>{t("videoStream.configureCameras")}</p>
                <button
                  className="upload-file-button"
                  disabled={!isUploadEnabled}
                  onClick={isUploadEnabled ? () => setIsUploadModalOpen(true) : undefined}
                  style={{
                    opacity: isUploadEnabled ? 1 : 0.6,
                    cursor: isUploadEnabled ? "pointer" : "not-allowed",
                  }}
                >
                  {t("videoStream.uploadFileButton")}
              </button>
            </div>
          )}

          {streamStatus === "playback" && (
            <div className="streams-layout">
              {recordedVideoType ? (
                // Playback for recorded RTSP videos - simple MP4 playback
                (() => {
                  if (!sessionId) {
                    console.error('🎬 ERROR: sessionId is missing!', { sessionId, recordedVideoType });
                    return (
                      <div className="stream-placeholder">
                        <p>Error: Session ID not found. Cannot play recorded video.</p>
                      </div>
                    );
                  }
                  
                  const videoUrl = getRecordedVideoUrl(sessionId, recordedVideoType);
                  
                  console.log('🎬 Rendering recorded video playback:', {
                    recordedVideoType,
                    sessionId,
                    videoUrl,
                    isPlaybackMode,
                    streamStatus
                  });
                  
                  const videoLabel = {
                    back: t("accordion.backCamera"),
                    board: t("accordion.boardCamera"),
                    front: t("accordion.frontCamera"),
                  }[recordedVideoType];
                  
                  return (
                    <div className="single-stream">
                      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#000' }}>
                        <video
                          key={videoUrl}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                          controls
                          autoPlay
                          onLoadStart={() => console.log('🎬 Video loadStart:', videoUrl)}
                          onCanPlay={() => console.log('🎬 Video canPlay')}
                          onError={(e) => {
                            console.error('🎬 Video error:', {
                              error: e.currentTarget.error,
                              errorMessage: e.currentTarget.error?.message,
                              networkState: e.currentTarget.networkState,
                              readyState: e.currentTarget.readyState,
                              src: videoUrl
                            });
                          }}
                          onLoadedMetadata={() => console.log('🎬 Video loadedMetadata')}
                        >
                          <source src={videoUrl} type="video/mp4" />
                          {t("videoStream.browserNotSupported")}
                        </video>
                      </div>
                      <div className="stream-overlay-label">{videoLabel}</div>
                    </div>
                  );
                })()
              ) : activeStream === "all" && !recordedVideoType ? (
                // Multi-view for uploaded files
                <div className="multi-stream-container">
                  {getAvailableVideoFiles().map(({ type, file, label }) => (
                    <div key={type} className="main-stream">
                      <HLSPlayer videoFile={file} mode="playback" camera={type} />
                      <div className="stream-overlay-label">{label}</div>
                    </div>
                  ))}
                </div>
              ) : (
                // Single view for uploaded files
                (() => {
                  let file: File | null = null;

                  if (activeStream === "back")
                    file = uploadedVideoFiles.back;
                  else if (activeStream === "content")
                    file = uploadedVideoFiles.board;
                  else if (activeStream === "front")
                    file = uploadedVideoFiles.front;

                  if (!file) {
                    return (
                      <div className="stream-placeholder">
                        <p>{t("videoStream.noVideoConfigured")}</p>
                      </div>
                    );
                  }

                  return (
                    <div className="single-stream">
                      <HLSPlayer videoFile={file} mode="playback" camera={activeStream as "front" | "back" | "content"} />
                      <div className="stream-overlay-label">
                        {streamTypes.find(s => s.pipeline === activeStream)?.label || activeStream}
                      </div>
                    </div>
                  );
                })()
              )}
            </div>
          )}

          {streamStatus === "active" && (
            <div className="streams-layout">
              {activeStream === "all" && (
                <div className="multi-stream-container">
                  {isValidStream(streams.front) && (
                    <div className="main-stream">
                      <HLSPlayer streamUrl={streams.front!} mode="stream" camera="front" />
                      <div className="stream-overlay-label">{t("accordion.frontCamera")}</div>
                    </div>
                  )}

                  <div className="side-streams-container">
                    {isValidStream(streams.back) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.back!} mode="stream" camera="back" />
                        <div className="stream-overlay-label">{t("accordion.backCamera")}</div>
                      </div>
                    )}

                    {isValidStream(streams.content) && (
                      <div className="side-stream">
                        <HLSPlayer streamUrl={streams.content!} mode="stream" camera="content" />
                        <div className="stream-overlay-label">{t("accordion.boardCamera")}</div>
                      </div>
                    )}
                  </div>
                </div>
              )} 

              {activeStream !== "all" &&
                activeStream &&
                isValidStream(streams[activeStream]) && (
                  <div className="single-stream">
                    <HLSPlayer streamUrl={streams[activeStream]!} mode="stream" camera={activeStream as "front" | "back" | "content"} />
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