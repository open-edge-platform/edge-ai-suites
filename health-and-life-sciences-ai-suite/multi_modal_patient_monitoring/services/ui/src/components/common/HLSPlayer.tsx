import React from 'react';
 
interface HLSPlayerProps {
  streamUrl: string;
}
 
const HLSPlayer: React.FC<HLSPlayerProps> = ({ streamUrl }) => {
  // Check if the URL is a webpage or an HLS stream
  const isWebpage = !streamUrl.endsWith('.m3u8');
 
  return isWebpage ? (
    <iframe
      src={streamUrl}
      scrolling="no"
      width="100%"
      height="100%"
      style={{ border: 'none' }}
    />
  ) : (
    <video controls width="100%" height="100%">
      <source src={streamUrl} type="application/vnd.apple.mpegurl" />
      Your browser does not support the video tag.
    </video>
  );
};
 
export default HLSPlayer;