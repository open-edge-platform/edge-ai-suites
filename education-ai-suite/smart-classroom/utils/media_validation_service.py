import logging
from typing import Tuple, Optional
from utils.session_state_manager import SessionState

logger = logging.getLogger(__name__)

class MediaValidationService:
    """Validates media files for consistency"""
    
    DURATION_TOLERANCE = 0.1  # 10% tolerance
    
    @staticmethod
    def validate_duration_match(
        session_id: str,
        audio_duration: Optional[float] = None,
        video_duration: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if audio and video durations match.
    
        """
        # Use provided durations or get from session state
        audio_dur = audio_duration or SessionState.get_audio_duration(session_id)
        video_dur = video_duration or SessionState.get_video_duration(session_id)
        
        # If only one media type, validation passes
        if not audio_dur or not video_dur:
            logger.debug(f"Session {session_id}: Single media type detected, skipping validation")
            return True, None
        
        # Both exist - check match
        max_duration = max(audio_dur, video_dur)
        duration_diff = abs(audio_dur - video_dur) / max_duration
        
        if duration_diff > MediaValidationService.DURATION_TOLERANCE:
            error_msg = (
                f"Media duration mismatch detected. "
                f"Audio: {audio_dur:.2f}s, Video: {video_dur:.2f}s. "
                f"Difference: {duration_diff*100:.1f}%. "
                f"Maximum allowed: {MediaValidationService.DURATION_TOLERANCE*100}%"
            )
            logger.warning(f"Session {session_id}: {error_msg}")
            return False, error_msg
        
        logger.debug(f"Session {session_id}: Duration validation passed. Audio: {audio_dur:.2f}s, Video: {video_dur:.2f}s")
        return True, None
