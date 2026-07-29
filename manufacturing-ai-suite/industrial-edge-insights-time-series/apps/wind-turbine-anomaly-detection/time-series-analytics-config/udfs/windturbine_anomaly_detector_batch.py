#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for anomaly detection on 
the windturbine speed and generated power data. """

import os
import logging
import pickle
import time
import math
import warnings
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import numpy as np
from sklearnex import patch_sklearn, config_context
patch_sklearn()

warnings.filterwarnings(
    "ignore",
    message=".*Threading.*parallel backend is not supported by Extension for Scikit-learn.*"
)

warnings.filterwarnings(
    "ignore",
    message=".*X does not have valid feature names, but RandomForestRegressor was fitted with feature names*"
)




log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
enable_benchmarking = os.getenv('ENABLE_BENCHMARKING', 'false').upper() == 'TRUE'
total_no_pts = int(os.getenv('BENCHMARK_TOTAL_PTS', "0"))
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)

logger = logging.getLogger()

logging.getLogger("sklearnex").setLevel(logging.INFO)

# Anomaly detection on the windturbine speed and generated power data
class AnomalyDetectorHandler(Handler):
    """ Handler for the anomaly detection UDF. It processes incoming points
    and detects anomalies based on the wind speed and generated power data.
    """
    def __init__(self, agent):
        self._agent = agent
        # read the saved model and load it
        def load_model(filename):
            with open(filename, 'rb') as f:
                model = pickle.load(f)
            return model
        model_path = os.getenv('MODEL_PATH')
        model_path = os.path.abspath(model_path)
        self.rf = load_model(model_path)

        self.device = os.getenv('DEVICE', 'auto').lower()

        # wind speed and active power field name in the influxdb measurements
        self.x_name = "wind_speed"
        self.y_name = "grid_active_power"

        # hyper-params for anomaly classification
        self.error_threshold = 0.1
        self.anomalies = []
        self.cut_in_speed = 3
        self.cut_out_speed = 14
        self.min_power_th = 50

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

    def _should_check_anomaly(self, x, y):
        """Check if point is within valid operating range for anomaly detection."""
        if math.isnan(x) or math.isnan(y):
            return False

        if ((x <= self.cut_in_speed) or (x > self.cut_in_speed and y < self.min_power_th)
                or (x > self.cut_out_speed)):
            return False

        return True

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
        points_info = []
        x_values_for_batch = []

        for i, point in enumerate(self._batch_points):
            x = None
            y = None

            stream_src = point.tags.get("source") or point.fieldsString.get("source")

            global enable_benchmarking
            if enable_benchmarking:
                if stream_src not in self.points_received:
                    self.points_received[stream_src] = 0
                if self.points_received[stream_src] >= self.max_points:
                    logger.info(f"Max points per source for benchmarking reached. Skipping further processing.")
                    break
                self.points_received[stream_src] += 1

            if self.x_name in point.fieldsDouble:
                x = np.float32(point.fieldsDouble[self.x_name])
            if self.y_name in point.fieldsDouble:
                y = np.float32(point.fieldsDouble[self.y_name])

            if x is None or y is None:
                logger.error(
                    "Point %d: no input received for %s %s, %s %s. Skipping anomaly detection.",
                    i,
                    self.x_name,
                    x,
                    self.y_name,
                    y,
                )
                point.fieldsDouble["analytic"] = False
                points_info.append((point, x, y, False))
                continue

            point.fieldsDouble["analytic"] = True
            should_check = self._should_check_anomaly(x, y)
            if should_check:
                x_values_for_batch.append([x])
                points_info.append((point, x, y, True))
            else:
                points_info.append((point, x, y, False))

        batch_inference_start_time = time.time_ns()
        y_pred_batch = None
        if x_values_for_batch:
            x_array = np.array(x_values_for_batch, dtype=np.float32)
            with config_context(target_offload=self.device, allow_fallback_to_host=True):
                y_pred_batch = self.rf.predict(x_array)
        batch_inference_end_time = time.time_ns()
        inference_processing_time = (batch_inference_end_time - batch_inference_start_time)/len(x_values_for_batch) if x_values_for_batch else 0
        pred_idx = 0
        for point, x, y, has_prediction in points_info:
            start_time = time.time_ns()

            if has_prediction:
                pred = np.float32(y_pred_batch[pred_idx])
                pred_idx += 1

                # Relative error vs predicted (stable when actual power is near zero)
                if pred > np.float32(0.0):
                    error = np.float32((pred - y) / pred)
                    if error > np.float32(self.error_threshold):
                        self.anomalies.append((x, y))
                        if error < np.float32(0.3):
                            point.fieldsDouble["anomaly_status"] = 0.3  # LOW
                        elif error < np.float32(0.6):
                            point.fieldsDouble["anomaly_status"] = 0.6  # MEDIUM
                        else:
                            point.fieldsDouble["anomaly_status"] = 1.0  # HIGH

            if "anomaly_status" not in point.fieldsDouble:
                point.fieldsDouble["anomaly_status"] = 0.0

            time_now = time.time_ns()
            point.fieldsDouble["processing_time"] = (time_now - start_time) + inference_processing_time
            point.fieldsDouble["end_end_time"] = time_now - point.time

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

        if batch_size > 0:
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
