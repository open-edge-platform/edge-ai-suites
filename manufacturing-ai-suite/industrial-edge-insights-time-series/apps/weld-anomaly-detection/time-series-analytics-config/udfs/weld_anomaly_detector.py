#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#

""" Custom user defined function for anomaly detection on 
the weld data. """

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

# Anomaly detection on the weld data
class AnomalyDetectorHandler(Handler):
    """ Handler for the anomaly detection UDF. It processes incoming points
    and detects anomalies based on the weld data.
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
        # extract the values from the point
        for point_data in point.fieldsDouble:
            if point_data.key == "Pressure":
                pressure = point_data.value
            elif point_data.key == "CO2 Weld Flow":
                co2_weld_flow = point_data.value
            elif point_data.key == "Feed":
                feed = point_data.value
            elif point_data.key == "Primary Weld Current":
                primary_weld_current = point_data.value
            elif point_data.key == "Wire Consumed":
                wire_consumed = point_data.value
            elif point_data.key == "Secondary Weld Voltage":
                secondary_weld_voltage = point_data.value
            else:
                continue

        logger.info(f"Pressure: {pressure}, CO2 Weld Flow: {co2_weld_flow}, Feed: {feed}, \
                    Primary Weld Current: {primary_weld_current}, Wire Consumed: {wire_consumed}, \
                        Secondary Weld Voltage: {secondary_weld_voltage}")

        # # write data back to db if it is an anomaly point or there is an alarm for the point
        response = udf_pb2.Response()
        response.point.CopyFrom(point)

        self._agent.write_response(response, True)

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
