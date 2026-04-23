from pyannote.audio import Pipeline
import torch
from torch.serialization import safe_globals
import os

# Import all task-related globals used in pyannote checkpoints
import torch.torch_version
from pyannote.audio.core.task import Specifications, Problem, Resolution, Task
from utils.config_loader import config
from utils.ensure_model import get_diarization_model_path


class PyannoteDiarizer:
    def __init__(self, device="cpu", hf_token=None):
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
                use_auth_token=hf_token
            )

        self.device = torch.device(device)
        self.pipeline.to(self.device)

    def diarize(self, audio_path):
        diarization = self.pipeline(audio_path)
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": speaker
            })
        return segments
