from components.asr.base_asr import BaseASR
from utils import ensure_model
from utils.model_download_helper import get_or_download_model_dir
from funasr import AutoModel

import os
import re
import logging
logger = logging.getLogger(__name__)

_SENTENCE_END_RE = re.compile(r'[。！？\.!?]\s*$')

FUNASR_MODEL_MAP = {
    "paraformer-zh": "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "paraformer-en": "iic/speech_paraformer-large-vad-punc_asr_nat-en-16k-common-vocab10020",
    "paraformer-online": "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online",
}

# use same vad and punc model for different ASR models
VAD_MODEL = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
PUNC_MODEL = "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"

def merge_vad(vad_result, max_length=20.0, turn_threshold=0.8, sentence_end_penalty=0.5):
    """Merge VAD segments to reduce fragmentation.

    Without diarization labels, silence gap is the best proxy for a speaker turn:
    within-speaker pauses are short, while turns usually have longer gaps and
    often follow sentence-final punctuation. Each adjacent boundary gets a cost:

        cost = gap + (sentence_end_penalty if previous segment ends a sentence else 0)

    Boundaries are merged in ascending cost order, skipping any merge that would
    exceed `max_length` or whose cost is >= `turn_threshold` (a likely turn).

    Args:
        vad_result (list): Segments [{"start": s, "end": s, "text": str}, ...] in seconds.
        max_length (float): Hard cap on merged segment length in seconds.
        turn_threshold (float): Boundaries with cost >= this are treated as speaker turns.
        sentence_end_penalty (float): Cost added when the prior segment ends with . ! ? 。！？.

    Returns:
        list: Merged segments [{"start": s, "end": s, "text": str}, ...].
    """
    if len(vad_result) <= 1:
        return [dict(s) for s in vad_result]

    segs = [dict(s) for s in vad_result]

    def boundary_cost(left, right):
        gap = right["start"] - left["end"]
        penalty = sentence_end_penalty if _SENTENCE_END_RE.search(left["text"]) else 0.0
        return gap + penalty

    while len(segs) > 1:
        best_i = -1
        best_cost = turn_threshold
        for i in range(len(segs) - 1):
            if segs[i + 1]["end"] - segs[i]["start"] > max_length:
                continue
            cost = boundary_cost(segs[i], segs[i + 1])
            if cost < best_cost:
                best_cost = cost
                best_i = i
        if best_i < 0:
            break

        left, right = segs[best_i], segs[best_i + 1]
        left["end"] = right["end"]
        left["text"] = (left["text"] + " " + right["text"]).strip()
        segs.pop(best_i + 1)

    return segs


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

            # temperature controls merge intensity: 0.0 = default merging, 1.0 = minimal
            # turn_threshold = max(0.1, 0.8 - 0.7 * float(temperature))
            # segments = merge_vad(segments, turn_threshold=turn_threshold)


            return {
                "text": out["text"].strip(),
                "segments": segments
            }

        except Exception as e:
            logger.error(f"[ASR] Paraformer transcription error: {e}")
            return {"text": "", "segments": []}