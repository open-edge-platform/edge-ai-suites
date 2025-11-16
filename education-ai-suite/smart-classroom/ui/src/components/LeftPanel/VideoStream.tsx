import React, { useState } from 'react';
import streamingIcon from '../../assets/images/streaming-icon.png'; // Adjust the path as needed
import '../../assets/css/VideoStream.css';
import HLSPlayer from '../common/HLSPlayer';
import UploadFilesModal from '../Modals/UploadFilesModal';
import { startVideoAnalyticsPipeline, getClassStatistics  } from '../../services/api';
import { useAppSelector, useAppDispatch } from '../../redux/hooks';
import { setClassStatistics } from '../../redux/slices/fetchClassStatistics';

const VideoStream: React.FC = () => {
  const [isRoomView, setIsRoomView] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [streams, setStreams] = useState<{ front?: string; back?: string; content?: string }>({});
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const dispatch = useAppDispatch();
  const handleToggleRoomView = () => {
    setIsRoomView(!isRoomView);
  };

  const handleStreamClick = async (pipelineName: 'front' | 'rear' | 'board' | 'all') => {
    try {
      if (pipelineName === 'all') {
        // Start all pipelines and fetch their streams
        const frontStream = await startVideoAnalyticsPipeline('front', 'source-path', sessionId!);
        const backStream = await startVideoAnalyticsPipeline('back', 'source-path', sessionId!);
        const contentStream = await startVideoAnalyticsPipeline('content', 'source-path', sessionId!);

        // Update the streams state
        setStreams({
          front: frontStream.hls_stream,
          back: backStream.hls_stream,
          content: contentStream.hls_stream,
        });

        // Fetch class statistics after all streams are set
        const classStats = await getClassStatistics(sessionId!);
        dispatch(setClassStatistics(classStats));
      } else {
        // Start a specific pipeline and fetch its stream
        const apiPipelineName: 'front' | 'back' | 'content' =
          pipelineName === 'rear' ? 'back' : pipelineName === 'board' ? 'content' : pipelineName;

        const stream = await startVideoAnalyticsPipeline(apiPipelineName, 'source-path', sessionId!);
        setStreams({ [apiPipelineName]: stream.hls_stream });
      }
    } catch (error) {
      console.error('Error starting video analytics pipeline or fetching class statistics:', error);
    }
  };

  return (
    <div className={`video-stream ${isRoomView ? 'room-view' : ''}`}>
      <div className="video-stream-header">
        <button className="toggle-room-view" onClick={handleToggleRoomView}>
          {isRoomView ? 'Default View' : 'Room View'}
        </button>
        <div className="stream-controls">
          <button onClick={() => handleStreamClick('front')}>Front</button>
          <button onClick={() => handleStreamClick('rear')}>Rear</button>
          <button onClick={() => handleStreamClick('board')}>Board</button>
          <button onClick={() => handleStreamClick('all')}>All</button>
        </div>
      </div>
      <div className="video-stream-body">
        {Object.keys(streams).length > 0 ? (
          <div className={`stream-container ${Object.keys(streams).length === 3 ? 'split-screen' : ''}`}>
            {streams.front && <HLSPlayer streamUrl={streams.front} />}
            {streams.back && <HLSPlayer streamUrl={streams.back} />}
            {streams.content && <HLSPlayer streamUrl={streams.content} />}
          </div>
        ) : (
          <div className="stream-placeholder">
            <img src={streamingIcon} alt="Streaming Icon" className="streaming-icon-placeholder" />
            <p>Go to settings to configure your recorders or upload audio/video files</p>
            <button className="upload-file-button" onClick={() => setIsUploadModalOpen(true)}>
              Upload File
            </button>
          </div>
        )}
      </div>
      {isUploadModalOpen && (
        <UploadFilesModal
          isOpen={isUploadModalOpen}
          onClose={() => setIsUploadModalOpen(false)}
          onApply={(paths) => {
            console.log('Uploaded file paths:', paths);
            setIsUploadModalOpen(false);
          }}
        />
      )}
    </div>
  );
};

export default VideoStream;

