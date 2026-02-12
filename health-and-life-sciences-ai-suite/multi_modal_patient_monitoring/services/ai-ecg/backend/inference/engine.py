import os
import time
import numpy as np
import scipy.stats as sst
from openvino import Core
import load
from inference.preprocess import ECGPreprocessor

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = "/models/ai-ecg"

MODEL_MAP = {
    8960: os.path.join(MODEL_DIR, "ecg_8960_ir10_fp16.xml"),
    17920: os.path.join(MODEL_DIR, "ecg_17920_ir10_fp16.xml"),
}

LABEL_MAP = {
    "N": "Normal sinus rhythm",
    "A": "Atrial Fibrillation (AF)",
    "O": "Other rhythm",
    "~": "Too noisy to classify"
}


class ECGInferenceEngine:
    def __init__(self):
        self.device = os.getenv("ECG_DEVICE", "GPU")
        self.core = Core()
        self.compiled_models = {}
        self.preproc = ECGPreprocessor()
        self._warmup_models()

    def _warmup_models(self):
        """
        Warm up each model once to remove first-inference overhead
        """
        for length in MODEL_MAP:
            dummy_ecg = [0.0] * length
            tensor = self.preproc.preproc.process_x([dummy_ecg])
            model = self.load_model(length)
            model([tensor])

    def load_model(self, length):
        """
        Load and cache OpenVINO model for given ECG length
        """
        if length not in MODEL_MAP:
            raise RuntimeError(f"Unsupported ECG length: {length}")

        if length not in self.compiled_models:
            model = self.core.read_model(MODEL_MAP[length])
            self.compiled_models[length] = self.core.compile_model(model, self.device)

        return self.compiled_models[length]

    def predict(self, filename):
        file_path = os.path.join(DATA_DIR, filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ECG file not found: {filename}")

        ecg = load.load_ecg(file_path)

        # Preprocess into windows
        windows = self.preproc.process(ecg)

        all_preds = []
        infer_start = time.time()

        for tensor, win_len in windows:
            compiled = self.load_model(win_len)
            output_tensor = compiled.output(0)

            result = compiled([tensor])[output_tensor]
            preds = np.argmax(result, axis=2).squeeze()
            all_preds.extend(preds.tolist())

        infer_time_ms = (time.time() - infer_start) * 1000

        final_class = sst.mode(all_preds, keepdims=True).mode[0]
        short_label = self.preproc.int_to_class[int(final_class)]
        full_label = LABEL_MAP.get(short_label, short_label)

        first_window_len = windows[0][1]

        return {
            "signal": ecg[:first_window_len].tolist(),
            "result": full_label,        
            "inference_ms": round(infer_time_ms, 2),
            "length": len(ecg),
        }
