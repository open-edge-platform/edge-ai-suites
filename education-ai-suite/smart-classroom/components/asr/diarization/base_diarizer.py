"""Shared speaker identity registry for the diarization backends.

A backend clusters speakers only within the audio it is handed, so in chunked mode the
local labels restart on every chunk. The registry maps them onto session-wide
``SPEAKER_NN`` identities by matching speaker embeddings against the centroids seen so far.
"""
import logging

import numpy as np

from utils.config_loader import config

logger = logging.getLogger(__name__)


class GlobalSpeakerDiarizer:
    def __init__(self):
        self.similarity_threshold = float(
            config.models.diarization.global_speaker_similarity_threshold
        )
        if not 0.0 <= self.similarity_threshold <= 1.0:
            raise ValueError(
                "models.diarization.global_speaker_similarity_threshold "
                "must be between 0.0 and 1.0"
            )

        # A new diarizer is created for every transcription request. This state
        # is therefore shared by that request's chunks, but not by later audio.
        self.global_speakers = {}
        self.next_global_speaker_id = 0

    def diarize(self, audio_path):
        """Return [{'start': sec, 'end': sec, 'speaker': 'SPEAKER_NN'}] for audio_path."""
        raise NotImplementedError("Must implement in subclass.")

    @staticmethod
    def _normalize_embedding(embedding):
        embedding = np.asarray(embedding, dtype=np.float32)
        if embedding.ndim != 1 or not np.all(np.isfinite(embedding)):
            return None
        norm = np.linalg.norm(embedding)
        if norm <= 1e-12:
            return None
        return embedding / norm

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
        """Map {local_label: {'embedding', 'duration'}} onto global speaker labels."""
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
