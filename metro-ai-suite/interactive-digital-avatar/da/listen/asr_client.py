from typing import Union

import numpy as np
from funasr_onnx import Paraformer

from da.util.log import logger


class AsrClient:
    def __init__(self):
        self.model_dir = "resource/funasr_models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
        self.model = Paraformer(self.model_dir)
        logger.info(f"ASR model loaded from {self.model_dir}.")

    def recognize(self, audio: Union[np.ndarray, str]) -> str:
        """
        :param audio: Normalized audio chunks or path to audio file.
        """
        res = self.model(audio)
        return res[0]["preds"][0]
