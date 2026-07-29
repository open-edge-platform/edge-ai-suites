import os
import time
from typing import Dict, Any

import numpy as np
from openvino import Core, PartialShape, Type, save_model
from openvino import opset13 as opset

import load
from inference.signal_classifier import classify_ecg


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

            # NPU SDPA requires all inputs to be the same float type.
            # Convert attention mask (input[3]) from char/i8 to f32 to match other inputs.
            try:
                fixed_count = 0
                for node in ov_model.get_ordered_ops():
                    if node.get_type_name() == "ScaledDotProductAttention":
                        mask_input = node.input(3)
                        mask_type = mask_input.get_element_type()
                        if mask_type != Type.f32:
                            source_output = mask_input.get_source_output()
                            convert = opset.convert(source_output, Type.f32)
                            mask_input.replace_source_output(convert.output(0))
                            fixed_count += 1
                if fixed_count > 0:
                    # Serialize and reload to materialize graph changes
                    tmp_xml = "/tmp/ecg_npu_fixed.xml"
                    save_model(ov_model, tmp_xml)
                    ov_model = self.core.read_model(tmp_xml)
                    print(f"[INFO] Converted {fixed_count} SDPA attention masks to f32 for NPU")
                else:
                    print("[INFO] No SDPA attention mask conversion needed")
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

        # Signal-based rhythm classification
        try:
            classification = classify_ecg(ecg)
        except Exception:
            classification = "Unknown"

        return {
            "signal": ecg.tolist(),
            "embedding": embedding.tolist(),
            "inference_ms": round(infer_ms, 2),
            "length": int(ecg.size),
            "classification": classification,
        }
