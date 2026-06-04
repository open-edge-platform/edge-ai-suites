from components.asr.base_asr import BaseASR
from utils import ensure_model
from utils.model_download_helper import get_or_download_model_dir
from funasr import AutoModel

import os
import logging
logger = logging.getLogger(__name__)

FUNASR_MODEL_MAP = {
    "paraformer-zh": "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "paraformer-en": "iic/speech_paraformer-large-vad-punc_asr_nat-en-16k-common-vocab10020",
    "paraformer-online": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
}

# use same vad and punc model for different ASR models
VAD_MODEL = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
PUNC_MODEL = "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"

def merge_vad(vad_result, max_length=15.0, min_length=0):
    """Merge short VAD segments to reduce fragmentation.

    Args:
        vad_result (list): VAD segments [{"start": s, "end": s, "text": str}, ...] in seconds.
        max_length (float): Maximum merged segment length in seconds (default 15.0).
        min_length (float): Minimum merged segment length; shorter ones get dropped (default 0).

    Returns:
        list: Merged segments [{"start": s, "end": s, "text": str}, ...].
    """
    if len(vad_result) <= 1:
        return vad_result

    new_result = []
    cur = {
        "start": vad_result[0]["start"],
        "end": vad_result[0]["end"],
        "text": vad_result[0]["text"],
    }

    for seg in vad_result[1:]:
        if seg["end"] - cur["start"] < max_length:
            cur["end"] = seg["end"]
            cur["text"] = (cur["text"] + " " + seg["text"]).strip()
        else:
            if cur["end"] - cur["start"] > min_length:
                new_result.append(cur)
            cur = {
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            }

    new_result.append(cur)
    return new_result


class Paraformer(BaseASR):
    def __init__(self, model_name, device="cpu", revision="v2.0.4"):
        if model_name not in FUNASR_MODEL_MAP:
            raise ValueError(f"Invalid ASR model name {model_name}. Supported models are: {list(FUNASR_MODEL_MAP.keys())}")
        
        model_name = FUNASR_MODEL_MAP[model_name]
        model_dir = ensure_model.get_asr_model_path()
        model_dir = get_or_download_model_dir(model=model_name, revision=revision, local_dir=model_dir)

        model_dir_parent = os.path.dirname(model_dir) 
        # download vad model if not exist
        vad_model_dir = os.path.join(model_dir_parent, VAD_MODEL)
        vad_model_dir = get_or_download_model_dir(model=VAD_MODEL, revision="v2.0.4", local_dir=vad_model_dir)
        # download punc model if not exist
        punc_model_dir = os.path.join(model_dir_parent, PUNC_MODEL)
        punc_model_dir = get_or_download_model_dir(model=PUNC_MODEL, revision="v2.0.4", local_dir=punc_model_dir)

        self.model_name = model_name
        self.model = AutoModel(model=model_dir, model_revision=revision,
                        vad_model=vad_model_dir, vad_model_revision="v2.0.4",
                        punc_model=punc_model_dir, punc_model_revision="v2.0.4",
                        #   spk_model="cam++", spk_model_revision="v2.0.2",
                        device=device, disable_update=True
                        )

    def transcribe(self, audio_path: str, temperature=0.0) -> str:
        try:
            res = self.model.generate(
                input=audio_path,
                sentence_timestamp=True,
                batch_size_s=300
            )

            if not res:
                return {"text": "", "segments": []}

            out = res[0]

            segments = []
            if "sentence_info" in out:
                for s in out["sentence_info"]:
                    segments.append({
                        "start": s["start"] / 1000.0,  # ms → seconds
                        "end": s["end"] / 1000.0,
                        "text": s["text"].strip()
                    })

            segments = merge_vad(segments)

            return {
                "text": out["text"].strip(),
                "segments": segments
            }

        except Exception as e:
            logger.error(f"[ASR] Paraformer transcription error: {e}")
            return {"text": "", "segments": []}