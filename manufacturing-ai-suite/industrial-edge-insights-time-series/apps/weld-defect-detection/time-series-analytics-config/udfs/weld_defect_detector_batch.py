#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for anomaly detection in weld sensor data. """
import json
import os
import logging
import time
import warnings

log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
enable_benchmarking = os.getenv('ENABLE_BENCHMARKING', 'false').upper() == 'TRUE'
total_no_pts = int(os.getenv('BENCHMARK_TOTAL_PTS', "0"))
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging before importing sklearnex so basicConfig takes effect
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logging.getLogger("sklearnex").setLevel(logging.INFO)

from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import numpy as np
import joblib
from sklearnex import patch_sklearn, config_context
patch_sklearn()

warnings.filterwarnings(
    "ignore",
    message=".*Threading.*parallel backend is not supported by Extension for Scikit-learn.*"
)

# Primary weld current threshold
WELD_CURRENT_THRESHOLD = 50
GOOD_WELD_LABEL = "Good Weld"
NO_WELD_LABEL = "No Weld"
FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]
MODEL_WITH_EXPLANATION = True
logger = logging.getLogger()

# Anomaly detection on the weld sensor data
class AnomalyDetectorHandler(Handler):
    """ Handler for the anomaly detection UDF. It processes incoming points
    and detects anomalies based on the weld sensor data.
    """
    def __init__(self, agent):
        self._agent = agent
        # Need to enable after model training
        self.info_data = {}
        model_name = os.getenv('MODEL_PATH')
        model_path = os.path.abspath(model_name)
        label_name = model_name.replace('.pkl', '_labels.pkl')
        label_path = os.path.abspath(label_name)
        self.pipeline = joblib.load(model_path)
        self.le       = joblib.load(label_path)
        self.device = os.getenv('DEVICE', 'auto').strip().lower() or 'auto'
        logger.info(f"on device: {self.device}")
        global MODEL_WITH_EXPLANATION
        if MODEL_WITH_EXPLANATION:
            logger.info("Model explanations are enabled for this UDF.")
            model_json_info = model_name.replace('.pkl', '.json')
            info_path = os.path.abspath(model_json_info)

            with open(info_path, "r", encoding="utf-8") as f:
                self.info_data = json.load(f)
            logger.info(f"Model           : {self.info_data.get('algorithm', 'unknown')}")
            logger.info(f"Classes         : {len(self.info_data.get('classes', []))}")
            logger.info(f"Trained w/ Intel: {self.info_data.get('intel_patched', 'unknown')}")

        self.points_received = {}
        global total_no_pts
        self.max_points = int(total_no_pts)

        # Batch processing state.
        self._batch_points = []
        self._begin_response = None

    def info(self):
        """ Return the InfoResponse. Describing the properties of this Handler
        """
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.BATCH
        response.info.provides = udf_pb2.BATCH
        return response

    def init(self, init_req):
        """ Initialize the Handler with the provided options.
        """
        response = udf_pb2.Response()
        response.init.success = True
        return response

    def snapshot(self):
        """ Create a snapshot of the running state of the process.
        """
        response = udf_pb2.Response()
        response.snapshot.snapshot = b''
        return response

    def restore(self, restore_req):
        """ Restore a previous snapshot.
        """
        response = udf_pb2.Response()
        response.restore.success = False
        response.restore.error = 'not implemented'
        return response

    def begin_batch(self, begin_req):
        """ A batch has begun.
        """
        self._batch_points = []
        self._begin_response = udf_pb2.Response()
        self._begin_response.begin.CopyFrom(begin_req)

    def _extract_fields_from_point(self, point):
        """Extract point fields into a plain dict."""
        fields = {}
        for key, value in point.fieldsDouble.items():
            fields[key] = value
        for key, value in point.fieldsInt.items():
            fields[key] = value
        for key, value in point.fieldsString.items():
            fields[key] = value
        return fields
    
    def _build_explanation(self, input_row: dict, predicted_category: str, prob_map: dict, model_info: dict) -> dict:
        """Create a human-readable reason block for why a row was classified as a category."""
        stats = model_info.get("class_feature_stats", {}) if model_info else {}
        pred_stats = stats.get(predicted_category, {})
        good_stats = stats.get(GOOD_WELD_LABEL, {})

        # Sort probabilities and include top alternatives for context.
        ranked = sorted(prob_map.items(), key=lambda kv: kv[1], reverse=True)
        top_probs = [{"category": k, "probability": round(float(v), 6)} for k, v in ranked[:3]]

        signal_features = []
        for feat in FEATURES:
            if feat not in pred_stats or feat not in good_stats:
                continue
            value = float(input_row[feat])
            pred_mean = float(pred_stats[feat].get("mean", 0.0))
            pred_std = max(float(pred_stats[feat].get("std", 0.0)), 1e-6)
            good_mean = float(good_stats[feat].get("mean", 0.0))
            good_std = max(float(good_stats[feat].get("std", 0.0)), 1e-6)

            # Positive score means closer to predicted class profile than Good Weld profile.
            z_to_pred = abs(value - pred_mean) / pred_std
            z_to_good = abs(value - good_mean) / good_std
            evidence = z_to_good - z_to_pred

            signal_features.append(
                {
                    "feature": feat,
                    "value": round(value, 6),
                    "predicted_mean": round(pred_mean, 6),
                    "good_weld_mean": round(good_mean, 6),
                    "evidence_score": round(float(evidence), 6),
                }
            )

        signal_features.sort(key=lambda x: x["evidence_score"], reverse=True)
        top_signals = signal_features[:3]

        if top_signals:
            reason = (
                f"Classified as {predicted_category} because key signals "
                f"({', '.join(s['feature'] for s in top_signals)}) align more with "
                f"{predicted_category} profile than Good Weld profile."
            )
        else:
            reason = (
                f"Classified as {predicted_category} based on model probability ranking; "
                "class profile statistics were not available."
            )

        return {
            "reason": reason,
            "top_probabilities": top_probs,
            "top_signal_features": top_signals,
        }


    def point(self, point):
        """ A point has arrived.
        """
        if "anomaly_status" not in point.fieldsDouble:
            point.fieldsDouble["anomaly_status"] = 0.0
        self._batch_points.append(point)

    def process_batch(self):
        """Process all points accumulated in the current batch."""
        if not self._batch_points:
            return

        try:
            valid_points_info = []
            x_values_for_batch = []

            for i, point in enumerate(self._batch_points):
                if "anomaly_status" not in point.fieldsDouble:
                    point.fieldsDouble["anomaly_status"] = 0.0

                fields = self._extract_fields_from_point(point)
                stream_src = point.tags.get("source") or fields.get("source")

                global enable_benchmarking
                if enable_benchmarking:
                    if stream_src not in self.points_received:
                        self.points_received[stream_src] = 0
                    if self.points_received[stream_src] >= self.max_points:
                        logger.info(f"Max points per source for benchmarking reached. Skipping further processing.")
                        break
                    self.points_received[stream_src] += 1

                weld_current = fields.get("Primary Weld Current", 0.0)
                if weld_current >= WELD_CURRENT_THRESHOLD:
                    missing_features = [f for f in FEATURES if f not in fields]
                    if not missing_features:
                        x_values_for_batch.append([
                            fields["Pressure"],
                            fields["CO2 Weld Flow"],
                            fields["Feed"],
                            fields["Primary Weld Current"],
                            fields["Secondary Weld Voltage"],
                        ])
                        valid_points_info.append((i, point, fields, True))
                    else:
                        logger.warning("Point %d: missing required features for inference: %s", i, missing_features)
                        valid_points_info.append((i, point, fields, False))
                else:
                    valid_points_info.append((i, point, fields, False))

            batch_inference_start_time = time.time_ns()
            predictions = None
            predictions_proba = None
            if x_values_for_batch:
                x_array = np.array(x_values_for_batch, dtype=np.float32)
                with config_context(target_offload=self.device, allow_fallback_to_host=True):
                    predictions = self.pipeline.predict(x_array)
                    predictions_proba = self.pipeline.predict_proba(x_array)
            batch_inference_end_time = time.time_ns()
            inference_processing_time = (batch_inference_end_time - batch_inference_start_time)/len(x_values_for_batch) if x_values_for_batch else 0

            pred_idx = 0
            for i, point, fields, is_valid in valid_points_info:
                point_start_time = time.time_ns()

                if is_valid:
                    pred_label_idx = predictions[pred_idx]
                    pred_proba = predictions_proba[pred_idx]
                    pred_idx += 1

                    classes = list(self.le.classes_)
                    prob_map = {cls: float(p) for cls, p in zip(classes, pred_proba)}
                    predicted_category = self.le.inverse_transform([pred_label_idx])[0]

                    point.fieldsString["predicted_category"] = str(predicted_category)
                    good_weld_prob = float(prob_map.get(GOOD_WELD_LABEL, 0.0))
                    good_defect = good_weld_prob * 100.0
                    bad_defect = (1.0 - good_weld_prob) * 100.0
                    confidence = round(float(np.max(pred_proba)), 6)

                    if MODEL_WITH_EXPLANATION:
                        explanation = self._build_explanation(fields, predicted_category, prob_map, self.info_data)
                    else:
                        explanation = "N/A"

                    data_prediction = {
                        "predicted_category": predicted_category,
                        "is_defect": predicted_category != GOOD_WELD_LABEL,
                        "defect_probability": round(float(1.0 - good_weld_prob), 6),
                        "good_weld_probability": round(float(good_weld_prob), 6),
                        "confidence": confidence,
                        "probabilities": prob_map,
                        "explanation": explanation,
                    }
                    point.fieldsString["prediction_details"] = json.dumps(data_prediction)
                    point.fieldsDouble["Good Weld"] = round(float(good_defect), 2)
                    point.fieldsDouble["Defective Weld"] = round(float(bad_defect), 2)
                    point.fieldsDouble["anomaly_status"] = 1.0 if bad_defect > 50 else 0.0
                else:
                    weld_current = fields.get("Primary Weld Current", 0.0)
                    if weld_current < WELD_CURRENT_THRESHOLD:
                        point.fieldsString["predicted_category"] = NO_WELD_LABEL
                    point.fieldsDouble["Good Weld"] = 0.0
                    point.fieldsDouble["Defective Weld"] = 0.0
                    point.fieldsDouble["anomaly_status"] = 0.0

                time_now = time.time_ns()
                point.fieldsDouble["processing_time"] = (time_now - point_start_time) + inference_processing_time
                point.fieldsDouble["end_end_time"] = time_now - point.time
                response = udf_pb2.Response()
                response.point.CopyFrom(point)
                self._agent.write_response(response)

        except Exception:
            logger.exception("Error while processing batch; emitting safe defaults")
            for point in self._batch_points:
                if "anomaly_status" not in point.fieldsDouble:
                    point.fieldsDouble["anomaly_status"] = 0.0
                point.fieldsDouble["Good Weld"] = 0.0
                point.fieldsDouble["Defective Weld"] = 0.0
                response = udf_pb2.Response()
                response.point.CopyFrom(point)
                self._agent.write_response(response)


    def end_batch(self, end_req):
        """ The batch is complete.
        """
        batch_start_time = time.time_ns()
        batch_size = len(self._batch_points)

        if self._begin_response is not None:
            self._agent.write_response(self._begin_response)

        if batch_size == 0:
            response = udf_pb2.Response()
            response.end.CopyFrom(end_req)
            self._agent.write_response(response)
            return

        self.process_batch()

        response = udf_pb2.Response()
        response.end.CopyFrom(end_req)
        self._agent.write_response(response)

        batch_end_time = time.time_ns()
        batch_processing_time = (batch_end_time - batch_start_time) / 1e6
        logger.info(
            "Batch of %d points processed in %.2f ms (%.2f ms/point)",
            batch_size,
            batch_processing_time,
            batch_processing_time / batch_size if batch_size > 0 else 0,
        )


if __name__ == '__main__':
    # Create an agent
    agent = Agent()

    # Create a handler and pass it an agent so it can write points
    h = AnomalyDetectorHandler(agent)

    # Set the handler on the agent
    agent.handler = h

    # Anything printed to STDERR from a UDF process gets captured
    # into the Kapacitor logs.
    agent.start()
    agent.wait()
