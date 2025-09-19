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
from collections import deque
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import numpy as np
import requests
from sklearnex import patch_sklearn, config_context
patch_sklearn()
from sklearn.linear_model import LinearRegression

warnings.filterwarnings(
    "ignore",
    message=".*Threading.*parallel backend is not supported by Extension for Scikit-learn.*"
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

        # wind speed and active power field name in the influxdb measurements
        self.x_name = "wind_speed"
        self.y_name = "grid_active_power"

        # hyper-params for anomaly classification
        self.n_steps = 3
        self.last_states = deque(self.n_steps*[0], self.n_steps)
        self.last_anomalies = deque(self.n_steps*[0], self.n_steps)
        self.error_threshold = 0.15
        self.anomalies = []
        self.cut_in_speed = 3
        self.cut_out_speed = 14
        self.min_power_th = 50

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
        start_time = time.time_ns()
        check_for_anomalies = 1
        server = None
        x = None
        y = None
        for point_tag in point.tags:
            if point_tag.key == "source":
                server = point_tag.value
                break
        global enable_benchmarking
        if enable_benchmarking:
            if server not in self.points_received:
                self.points_received[server] = 0
            if self.points_received[server] >= self.max_points:
                return
            self.points_received[server] += 1

        logger.info("Processing point %s %s for source %s", point.time, time.time(), server)

        def process_the_point(x,y):
            if (math.isnan(x) or math.isnan(y)):
                self.last_states.append(0)
                return 0

            if ((x<=self.cut_in_speed) or (x>self.cut_in_speed and y<self.min_power_th)
                 or (x>self.cut_out_speed)):
                self.last_states.append(0)
                return 0

            return 1
        # extract the wind speed and power from the point
        for point_data in point.fieldsDouble:
            if point_data.key == self.x_name:
                x = point_data.value
            elif point_data.key == self.y_name:
                y = point_data.value
            else:
                continue
        # logger.info(f"Asset: {point.name}, x: {x}, y:{y}, cc:{self.enable_gcp_client}")

        if x is not None and y is not None:
            # check if the current point is an anomalous point
            check_for_anomalies = process_the_point(x,y)
            point.fieldsDouble.add(key = "analytic", value = True)
            if check_for_anomalies:
                y_pred = self.rf.predict(np.reshape(x,(-1,1)))
                error = (y_pred[0]-y)/(y)
                if error>self.error_threshold:
                    self.last_states.append(1)
                    self.last_anomalies.append((x,y))
                else:
                    self.last_states.append(0)

                # check if there are consecutive 3 anomalies, and then filter out
                # any false positives
                if sum(self.last_states) == self.n_steps:
                    x_feat = list(zip(*self.last_anomalies))[0]
                    x_feat = np.reshape(x_feat, (-1,1))
                    y_feat = list(zip(*self.last_anomalies))[1]

                    with config_context(target_offload="auto", allow_fallback_to_host=True):
                        lm = LinearRegression()
                        lm.fit(x_feat, y_feat)

                    if abs(lm.coef_)<200:
                        self.anomalies.append((x,y))
                        if error<0.3:
                            point.fieldsDouble.add(key = "anomaly_status", value = 0.3)
                            # anomaly_type="LOW"
                        elif error<0.6:
                            # anomaly_type = "MEDIUM"
                            point.fieldsDouble.add(key = "anomaly_status", value = 0.6)
                        else:
                            # anomaly_type = "HIGH"
                            point.fieldsDouble.add(key = "anomaly_status", value = 1)
                    else:
                        self.last_states.append(0)
        else:
            logger.error("No input received for %s %s, %s %s. Skipping anomaly detection."
                         , self.x_name, x, self.y_name, y)
            point.fieldsDouble.add(key = "analytic", value = False)

        # write data back to db if it is an anomaly point or there is an alarm for the point
        response = udf_pb2.Response()
        if not any(kv.key == "anomaly_status" for kv in point.fieldsDouble):
            point.fieldsDouble.add(key = "anomaly_status", value = 0.0)
        time_now = time.time_ns()
        point.fieldsDouble.add(key = 'processing_time', value = time_now-start_time)

        point.fieldsDouble.add(key = 'end_end_time', value = time_now-point.time)
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
