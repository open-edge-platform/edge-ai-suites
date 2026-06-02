import os
import time
from typing import Dict, Any

import numpy as np
from openvino import Core, PartialShape, Type, opset13 as opset

import load


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_DIR = "/models/ai-ecg"


class HubertECGInferenceEngine:
    """Inference helper for the backbone ECG encoder IR.

    Currently this wraps the HuBERT-ECG encoder converted to
    OpenVINO IR (hubert_ecg_small_fp16.xml) and returns a pooled
    feature vector for a single ECG file. It does *not* perform
    AF/arrhythmia classification by itself; a downstream classifier
    would be needed for that.
    """

    def __init__(self) -> None:
        self.device = os.getenv("ECG_DEVICE", "GPU")
        self.core = Core()
        self.model_path = os.path.join(MODEL_DIR, "hubert_ecg_small_fp16.xml")

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"ECG encoder IR not found at {self.model_path}. "
                "Ensure patient-monitoring-assets has generated it into /models/ai-ecg."
            )

        ov_model = self.core.read_model(self.model_path)

        # NPU requires static shapes — reshape dynamic dims to fixed input size
        if self.device.upper() == "NPU":
            try:
                ov_model.reshape({ov_model.input(0): PartialShape([1, 5000])})
                print("[INFO] ECG model reshaped to static [1, 5000] for NPU")
            except Exception as e:
                print(f"[WARNING] Failed to reshape ECG model for NPU: {e}")

            # NPU SDPA requires attention mask as float, not int8.
            # Walk the graph and insert Convert(i8 -> f16) before SDPA inputs.
            try:
                for op in ov_model.get_ordered_ops():
                    if op.get_type_name() == "ScaledDotProductAttention":
                        for i in range(op.get_input_size()):
                            input_type = op.input(i).get_element_type()
                            if input_type == Type.i8:
                                source_output = op.input(i).get_source_output()
                                convert = opset.convert(source_output, Type.f16)
                                op.input(i).replace_source_output(convert.output(0))
                                print(f"[INFO] Converted SDPA input {i} from i8 to f16 for NPU")
                print("[INFO] ECG model SDPA attention mask fixed for NPU")
            except Exception as e:
                print(f"[WARNING] Failed to fix SDPA attention mask: {e}")

        self.compiled = self.core.compile_model(ov_model, self.device)
        self.output_port = self.compiled.output(0)

    def _prepare_input(self, ecg: np.ndarray, target_len: int = 5000) -> np.ndarray:
        """Prepare 1D ECG signal for encoder input.

        The current IR was converted with example input [1, 5000], so
        we truncate or zero-pad the signal to 5000 samples and cast to
        float32.
        """

        ecg = np.asarray(ecg, dtype=np.float32)
        if ecg.size >= target_len:
            seq = ecg[:target_len]
        else:
            seq = np.zeros(target_len, dtype=np.float32)
            seq[: ecg.size] = ecg

        return seq[None, :]  # shape (1, target_len)

    def predict(self, filename: str) -> Dict[str, Any]:
        file_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"ECG file not found: {filename}")

        ecg = load.load_ecg(file_path)
        input_tensor = self._prepare_input(ecg)

        start = time.time()
        outputs = self.compiled([input_tensor])
        infer_ms = (time.time() - start) * 1000.0

        hidden = outputs[self.output_port]  # expected shape (1, T, D)
        # Mean-pool over time dimension to obtain a single embedding vector
        embedding = hidden.mean(axis=1).squeeze(0)  # (D,)

        return {
            "signal": ecg.tolist(),
            "embedding": embedding.tolist(),
            "inference_ms": round(infer_ms, 2),
            "length": int(ecg.size),
        }
