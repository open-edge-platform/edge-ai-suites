import logging
import os

import numpy as np
from pyannote.audio import Pipeline
import torch
import torchaudio
from torch.serialization import safe_globals

# Import all task-related globals used in pyannote checkpoints
import torch.torch_version
from pyannote.audio.core.task import Specifications, Problem, Resolution, Task
from utils.config_loader import config
from utils.ensure_model import get_diarization_model_path

logger = logging.getLogger(__name__)


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
                token=hf_token
            )

        self.device = torch.device(device)
        self.pipeline.to(self.device)

        threshold = getattr(
            config.models.diarization,
            "global_speaker_similarity_threshold",
            0.65,
        )
        self.similarity_threshold = float(threshold)
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(
                "models.diarization.global_speaker_similarity_threshold "
                "must be between 0.0 and 1.0"
            )

        # A new diarizer is created for every transcription request. This state
        # is therefore shared by that request's chunks, but not by later audio.
        self.global_speakers = {}
        self.next_global_speaker_id = 0

    @staticmethod
    def _normalize_embedding(embedding):
        embedding = np.asarray(embedding, dtype=np.float32)
        if embedding.ndim != 1 or not np.all(np.isfinite(embedding)):
            return None
        norm = np.linalg.norm(embedding)
        if norm <= 1e-12:
            return None
        return embedding / norm

    @staticmethod
    def _speaker_durations(diarization):
        durations = {speaker: 0.0 for speaker in diarization.labels()}
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            durations[speaker] += turn.duration
        return durations

    def _new_global_speaker(self, embedding, duration):
        speaker = f"SPEAKER_{self.next_global_speaker_id:02d}"
        self.next_global_speaker_id += 1
        self.global_speakers[speaker] = {
            "centroid": embedding.copy() if embedding is not None else None,
            "duration": duration if embedding is not None else 0.0,
        }
        return speaker

    def _update_global_speaker(self, speaker, embedding, duration):
        state = self.global_speakers[speaker]
        previous_duration = state["duration"]
        total_duration = previous_duration + duration
        if total_duration <= 0.0:
            return
        centroid = self._normalize_embedding(
            state["centroid"] * previous_duration + embedding * duration
        )
        state["centroid"] = centroid
        state["duration"] = total_duration

    def _match_global_speakers(self, local_speakers):
        mapping = {}
        assigned_local = set()
        assigned_global = set()
        candidates = []

        for local_speaker, local_state in local_speakers.items():
            embedding = local_state["embedding"]
            if embedding is None:
                continue
            for global_speaker, global_state in self.global_speakers.items():
                centroid = global_state["centroid"]
                if centroid is None:
                    continue
                similarity = float(np.dot(embedding, centroid))
                if similarity >= self.similarity_threshold:
                    candidates.append(
                        (similarity, local_speaker, global_speaker)
                    )

        # Enforce one-to-one matching within each chunk so two simultaneous
        # local speakers cannot collapse into the same global identity.
        for similarity, local_speaker, global_speaker in sorted(
            candidates,
            key=lambda item: (-item[0], item[1], item[2]),
        ):
            if local_speaker in assigned_local:
                continue
            if global_speaker in assigned_global:
                continue
            local_state = local_speakers[local_speaker]
            mapping[local_speaker] = global_speaker
            assigned_local.add(local_speaker)
            assigned_global.add(global_speaker)
            self._update_global_speaker(
                global_speaker,
                local_state["embedding"],
                local_state["duration"],
            )
            logger.info(
                "Mapped local %s to global %s (cosine similarity %.3f)",
                local_speaker,
                global_speaker,
                similarity,
            )

        for local_speaker in sorted(local_speakers):
            if local_speaker in mapping:
                continue
            local_state = local_speakers[local_speaker]
            global_speaker = self._new_global_speaker(
                local_state["embedding"],
                local_state["duration"],
            )
            mapping[local_speaker] = global_speaker
            logger.info(
                "Registered local %s as new global %s",
                local_speaker,
                global_speaker,
            )

        return mapping

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
