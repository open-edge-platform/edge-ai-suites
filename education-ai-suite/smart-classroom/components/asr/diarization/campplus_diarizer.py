"""FunASR CAM++ speaker diarization.

VAD -> fixed-length windows over speech only -> CAM++ embeddings -> spectral clustering.
Unlike ``AutoModel(spk_model=...)`` this never runs ASR, which is what makes it cheap
enough to run on every chunk or over a whole lecture.
"""
import logging
import os

import numpy as np
import soundfile as sf
import torch
from funasr import AutoModel
from funasr.models.campplus.cluster_backend import ClusterBackend
from funasr.models.campplus.utils import correct_labels, postprocess

from components.asr.diarization.base_diarizer import GlobalSpeakerDiarizer
from utils.ensure_model import get_asr_model_path
from utils.model_download_helper import get_or_download_model_dir

logger = logging.getLogger(__name__)

CAMPPLUS_MODEL = "iic/speech_campplus_sv_zh-cn_16k-common"
CAMPPLUS_REVISION = "v2.0.2"
# Same snapshot the FunASR ASR pipeline downloads, reused instead of fetched twice.
VAD_MODEL = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
VAD_REVISION = "v2.0.4"

SAMPLE_RATE = 16000
SEG_DUR = 1.5       # embedding window length in seconds
SEG_SHIFT = 0.75    # embedding window hop in seconds
MERGE_THR = 0.78    # cosine threshold used to merge similar speaker clusters
EMBEDDING_BATCH = 64


class CamPlusPlusDiarizer(GlobalSpeakerDiarizer):
    def __init__(self, device="cpu"):
        super().__init__()
        models_dir = os.path.dirname(get_asr_model_path())
        spk_dir = get_or_download_model_dir(
            model=CAMPPLUS_MODEL,
            revision=CAMPPLUS_REVISION,
            local_dir=os.path.join(models_dir, CAMPPLUS_MODEL),
        )
        vad_dir = get_or_download_model_dir(
            model=VAD_MODEL,
            revision=VAD_REVISION,
            local_dir=os.path.join(models_dir, VAD_MODEL),
        )

        self.device = device
        self.vad_model = AutoModel(model=vad_dir, device=device, disable_update=True)
        self.spk_model = AutoModel(model=spk_dir, device=device, disable_update=True)
        # AutoModel leaves the module in training mode, where BatchNorm uses batch
        # statistics: the embeddings degenerate into noise and everything clusters as a
        # single speaker (or a one-item batch raises outright).
        self.spk_model.model.eval()
        self.cluster = ClusterBackend(merge_thr=MERGE_THR)

    def _read_audio(self, audio_path):
        audio, sample_rate = sf.read(audio_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sample_rate != SAMPLE_RATE:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
        return audio

    def _speech_windows(self, audio_path, audio):
        """Split VAD speech into [start_s, end_s, samples] windows of SEG_DUR each."""
        result = self.vad_model.generate(input=audio_path)
        if not result:
            return []

        window_len = int(SEG_DUR * SAMPLE_RATE)
        window_shift = int(SEG_SHIFT * SAMPLE_RATE)
        windows = []
        for start_ms, end_ms in result[0].get("value") or []:
            speech = audio[int(start_ms / 1000.0 * SAMPLE_RATE): int(end_ms / 1000.0 * SAMPLE_RATE)]
            offset = start_ms / 1000.0
            last_end = 0
            for start in range(0, speech.shape[0], window_shift):
                end = min(start + window_len, speech.shape[0])
                if end <= last_end:
                    break
                last_end = end
                start = max(0, end - window_len)
                samples = speech[start:end]
                if samples.shape[0] < window_len:
                    samples = np.pad(samples, (0, window_len - samples.shape[0]), "constant")
                windows.append([start / SAMPLE_RATE + offset, end / SAMPLE_RATE + offset, samples])
        return windows

    def _embed(self, windows):
        batches = []
        with torch.no_grad():
            for i in range(0, len(windows), EMBEDDING_BATCH):
                samples = [w[2] for w in windows[i: i + EMBEDDING_BATCH]]
                result, _ = self.spk_model.model.inference(
                    samples, device=self.device, fs=SAMPLE_RATE
                )
                batches.append(result[0]["spk_embedding"].detach().cpu())
        return torch.cat(batches).numpy()

    def _local_speakers(self, windows, labels, embeddings):
        local = {}
        for label in set(labels):
            selected = labels == label
            local[int(label)] = {
                "embedding": self._normalize_embedding(embeddings[selected].mean(axis=0)),
                "duration": float(sum(w[1] - w[0] for w, keep in zip(windows, selected) if keep)),
            }
        return local

    def diarize(self, audio_path):
        try:
            audio = self._read_audio(audio_path)
            windows = self._speech_windows(audio_path, audio)
            if not windows:
                return []

            embeddings = self._embed(windows)
            # correct_labels() before clustering results are used, so the labels below
            # match the ones postprocess() emits.
            labels = correct_labels(self.cluster(torch.from_numpy(embeddings)))
            global_mapping = self._match_global_speakers(
                self._local_speakers(windows, labels, embeddings)
            )

            return [
                {
                    "start": float(start),
                    "end": float(end),
                    "speaker": global_mapping[int(label)],
                }
                for start, end, label in postprocess(windows, None, labels, embeddings)
            ]
        except Exception as e:
            logger.error(f"[Diarization] CAM++ diarization error: {e}", exc_info=True)
            return []
