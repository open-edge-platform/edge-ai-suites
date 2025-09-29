#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for anomaly detection in weld sensor data. """

import os
import logging
import pickle
import time
import warnings
from xml.parsers.expat import model
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import catboost as cb
import pandas as pd
import numpy as np



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

# Anomaly detection on the weld sensor data
class AnomalyDetectorHandler(Handler):
    """ Handler for the anomaly detection UDF. It processes incoming points
    and detects anomalies based on the weld sensor data.
    """
    def __init__(self, agent):
        self._agent = agent
        # read the saved model and load it
        def load_model(filename):
            with open(filename, 'rb') as f:
                model = pickle.load(f)
            return model
        # Need to enable after model training
        model_name = (os.path.basename(__file__)).replace('.py', '.cb')
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../models/" + model_name)
        model_path = os.path.abspath(model_path)
        # self.rf = load_model(model_path)

        # Initialize a CatBoostClassifier model for anomaly detection
        self.model = cb.CatBoostClassifier(
            depth=10,            # Set the depth of each tree to 10
            iterations=2000,     # Number of boosting iterations (trees)
            learning_rate=0.1,   # Step size for each iteration
            task_type="CPU",     # Specify to use CPU for training/inference
            devices="1:2",       # Specify device IDs (not used for CPU, but kept for config compatibility)
            random_seed=40,      # Set random seed for reproducibility
        )

        self.model.load_model(model_path)

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
        server = None
        start_time = time.time_ns()
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

        fields = {}
        for kv in point.fieldsDouble:
            fields[kv.key] = kv.value
        for kv in point.fieldsInt:
            fields[kv.key] = kv.value
        for kv in point.fieldsString:
            fields[kv.key] = kv.value
        point_series = pd.Series(fields)
        if "Primary Weld Current" in point_series and point_series["Primary Weld Current"] > 50:
            defect_likelihood_main = self.model.predict_proba(point_series)
            bad_defect = defect_likelihood_main[0]*100
            good_defect = defect_likelihood_main[1]*100
            if bad_defect > 50:
                point.fieldsDouble.add(key = "anomaly_status", value = 1.0)
            logger.info(f"Good Weld: {good_defect:.2f}%, Defective Weld: {bad_defect:.2f}%")
        else:
            logger.info("Good Weld: N/A, Defective Weld: N/A") 

        point.fieldsDouble.add(key = "Good Weld", value = round(good_defect, 2) if "good_defect" in locals() else 0.0)
        point.fieldsDouble.add(key = "Defective Weld", value = round(bad_defect,2) if "bad_defect" in locals() else 0.0)
        time_now = time.time_ns()
        point.fieldsDouble.add(key = 'processing_time', value = time_now-start_time)

        point.fieldsDouble.add(key = 'end_end_time', value = time_now-point.time)

        logger.info("Processing point %s %s for source %s", point.time, time.time(), server)

        response = udf_pb2.Response()
        if not any(kv.key == "anomaly_status" for kv in point.fieldsDouble):
            point.fieldsDouble.add(key = "anomaly_status", value = 0.0)
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
