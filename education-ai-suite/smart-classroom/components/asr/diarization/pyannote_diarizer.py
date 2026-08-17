import logging
import os

from pyannote.audio import Pipeline
import torch
import torchaudio
from torch.serialization import safe_globals

# Import all task-related globals used in pyannote checkpoints
import torch.torch_version
from pyannote.audio.core.task import Specifications, Problem, Resolution, Task
from components.asr.diarization.base_diarizer import GlobalSpeakerDiarizer
from utils.config_loader import config
from utils.ensure_model import get_diarization_model_path

logger = logging.getLogger(__name__)


class PyannoteDiarizer(GlobalSpeakerDiarizer):
    def __init__(self, device="cpu", hf_token=None):
        super().__init__()
        pipeline_source = config.models.diarization.name
        local_model_path = get_diarization_model_path()
        local_config_path = os.path.join(local_model_path, "config.yaml")

        if os.path.exists(local_config_path):
            pipeline_source = local_config_path

        # Allow all needed globals for torch ≥2.6 checkpoint loading
        with safe_globals([
            torch.torch_version.TorchVersion,
            Specifications,
            Problem,
            Resolution,
            Task
        ]):
            self.pipeline = Pipeline.from_pretrained(
                pipeline_source,
                token=hf_token
            )

        self.device = torch.device(device)
        self.pipeline.to(self.device)

    @staticmethod
    def _speaker_durations(diarization):
        durations = {speaker: 0.0 for speaker in diarization.labels()}
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            durations[speaker] += turn.duration
        return durations

    def diarize(self, audio_path):
        waveform, sample_rate = torchaudio.load(audio_path)
        audio_input = {"waveform": waveform, "sample_rate": sample_rate}
        output = self.pipeline(audio_input)
        diarization = output.exclusive_speaker_diarization
        local_labels = diarization.labels()
        durations = self._speaker_durations(diarization)
        speaker_embeddings = output.speaker_embeddings
        embeddings_by_speaker = {}
        if speaker_embeddings is not None:
            embedding_labels = output.speaker_diarization.labels()
            embeddings_by_speaker = {
                speaker: speaker_embeddings[index]
                for index, speaker in enumerate(embedding_labels)
                if index < len(speaker_embeddings)
            }

        local_speakers = {}
        for speaker in local_labels:
            embedding = self._normalize_embedding(
                embeddings_by_speaker[speaker]
            ) if speaker in embeddings_by_speaker else None
            local_speakers[speaker] = {
                "embedding": embedding,
                "duration": durations[speaker],
            }

        global_mapping = self._match_global_speakers(local_speakers)
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": global_mapping[speaker]
            })
        return segments
