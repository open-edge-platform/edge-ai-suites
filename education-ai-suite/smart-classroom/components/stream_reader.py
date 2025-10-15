from .base_component import PipelineComponent
from components.ffmpeg.audio_preprocessing import chunk_audio_by_silence


class AudioStreamReader(PipelineComponent):
    def __init__(self, session_id):
        self.session_id = session_id
        pass

    def process(self, input_generator):
        for input_data in input_generator:
            audio_path = input_data["audio_path"]
            for chunk in chunk_audio_by_silence(audio_path):
                yield chunk  # contains chunk_path, start_time, end_time, etc.
