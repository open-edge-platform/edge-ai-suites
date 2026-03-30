#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for anomaly detection in weld sensor data. """
import os
import logging
import time
import warnings
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


log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
enable_benchmarking = os.getenv('ENABLE_BENCHMARKING', 'false').upper() == 'TRUE'
total_no_pts = int(os.getenv('BENCHMARK_TOTAL_PTS', "0"))
logging_level = getattr(logging, log_level, logging.INFO)

# Primary weld current threshold
WELD_CURRENT_THRESHOLD = 50
GOOD_WELD_LABEL = "Good Weld"
FEATURES = [
    "Pressure",
    "CO2 Weld Flow",
    "Feed",
    "Primary Weld Current",
    "Secondary Weld Voltage",
]

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)

logger = logging.getLogger()

# Anomaly detection on the weld sensor data
class AnomalyDetectorHandler(Handler):
    """ Handler for the anomaly detection UDF. It processes incoming points
    and detects anomalies based on the weld sensor data.
    """
    def __init__(self, agent):
        self._agent = agent
        # Need to enable after model training
        model_name = (os.path.basename(__file__)).replace('.py', '.pkl')
        label_name = (os.path.basename(__file__)).replace('.py', '_labels.pkl')
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../models/" + model_name)
        model_path = os.path.abspath(model_path)
        label_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../models/" + label_name)
        label_path = os.path.abspath(label_path)
        with config_context(target_offload=self.device, allow_fallback_to_host=False):
            self.pipeline = joblib.load(model_path)
            self.le       = joblib.load(label_path)
        self.device = os.getenv('DEVICE', 'gpu').lower()



        self.points_received = {}
        global total_no_pts
        self.max_points = int(total_no_pts)

    def info(self):
        """ Return the InfoResponse. Describing the properties of this Handler
        """
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.STREAM
        response.info.provides = udf_pb2.STREAM
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
        raise Exception("not supported")

    def point(self, point):
        """ A point has arrived.
        """
        stream_src = None
        start_time = time.time_ns()
        if "source" in point.tags:
            stream_src = point.tags["source"]
        elif "source" in point.fieldsString:
            stream_src = point.fieldsString["source"]

        global enable_benchmarking
        if enable_benchmarking:
            if stream_src not in self.points_received:
                self.points_received[stream_src] = 0
            if self.points_received[stream_src] >= self.max_points:
                logger.info(f"Benchmarking: Reached max points {self.max_points} for source {stream_src}. Skipping further processing.")
                return
            self.points_received[stream_src] += 1
        fields = {}
        for key, value in point.fieldsDouble.items():
            fields[key] = value
            
        for key, value in point.fieldsInt.items():
            fields[key] = value


        
        if "Primary Weld Current" in fields and fields["Primary Weld Current"] > WELD_CURRENT_THRESHOLD:
            missing_features = [f for f in FEATURES if f not in fields]
            if missing_features:
                logger.warning("Missing required features for inference: %s", missing_features)
            else:
                x = np.array(
                    [[
                        fields["Pressure"],
                        fields["CO2 Weld Flow"],
                        fields["Feed"],
                        fields["Primary Weld Current"],
                        fields["Secondary Weld Voltage"],
                    ]],
                    dtype=np.float32,
                )
                with config_context(target_offload=self.device, allow_fallback_to_host=False):
                    pred_idx   = self.pipeline.predict(x)[0]
                    pred_proba = self.pipeline.predict_proba(x)[0]
                    classes = list(self.le.classes_)
                    prob_map = {cls: float(p) for cls, p in zip(classes, pred_proba)}

                    predicted_category = self.le.inverse_transform([pred_idx])[0]
                    good_weld_prob = prob_map.get(GOOD_WELD_LABEL, 0.0)
                    good_defect = good_weld_prob * 100.0
                    bad_defect = (1.0 - good_weld_prob) * 100.0
                    confidence = round(float(np.max(pred_proba)), 6)

                    logger.info(
                        "Prediction details: %s",
                        {
                            "predicted_category": predicted_category,
                            "is_defect": predicted_category != GOOD_WELD_LABEL,
                            "defect_probability": round(1.0 - good_weld_prob, 6),
                            "good_weld_probability": round(good_weld_prob, 6),
                            "confidence": confidence,
                            "probabilities": prob_map,
                        },
                    )


                    if bad_defect > 50:
                        point.fieldsDouble["anomaly_status"] = 1.0
                    logger.info("Good Weld: %.2f%%, Defective Weld: %.2f%%", good_defect, bad_defect)
        else:
            logger.debug("Primary Weld Current below threshold (%d). Skipping anomaly detection.", WELD_CURRENT_THRESHOLD)

        point.fieldsDouble["Good Weld"] = round(good_defect, 2) if "good_defect" in locals() else 0.0
        point.fieldsDouble["Defective Weld"] = round(bad_defect, 2) if "bad_defect" in locals() else 0.0
        
        time_now = time.time_ns()
        processing_time = time_now - start_time
        end_end_time = time_now - point.time
        point.fieldsDouble["processing_time"] = processing_time
        point.fieldsDouble["end_end_time"] = end_end_time

        logger.info("Processing point %s %s for source %s", point.time, time.time(), stream_src)

        response = udf_pb2.Response()
        if "anomaly_status" not in point.fieldsDouble:
            point.fieldsDouble["anomaly_status"] = 0.0
        response.point.CopyFrom(point)
        self._agent.write_response(response, True)

        end_time = time.time_ns()
        process_time = (end_time - start_time)/1000
        logger.debug("Function point took %.4f milliseconds to complete.", process_time)


    def end_batch(self, end_req):
        """ The batch is complete.
        """
        raise Exception("not supported")


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
