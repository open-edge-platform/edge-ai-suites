# Copyright Intel Corporation

""" Custom user defined function for anomaly detection on the windturbine speed and generated power data. """

import os
import sys
import json
from collections import deque
from distutils.util import strtobool
from kapacitor.udf.agent import Agent, Handler, Server
from kapacitor.udf import udf_pb2
import signal
import stat
import logging
import tempfile
import pickle
import math
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearnex import patch_sklearn
patch_sklearn()
# import paho.mqtt.client as mqtt
import modin.pandas as pd
import datetime
import time
# from gcp_mqtt_client import get_client

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger()
        

# Anomaly detection on the windturbine speed and generated power data
class AnomalyDetectorHandler(Handler):
    def __init__(self, agent):
        self._agent = agent
        # read the saved model and load it
        def load_model(filename):
          with open(filename, 'rb') as f:
              model = pickle.load(f)
          return model        
        self.rf = load_model("/app/models/windturbine_anomaly_detector.pkl")

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

        # # variables for publishing the anomaly data to mqtt broker
        # self.client = mqtt.Client()
        # mqtt_host = os.getenv("MQTT_BROKER_HOST")
        # mqtt_port = int(os.getenv("MQTT_BROKER_PORT"))
        # self.client.connect(mqtt_host, mqtt_port, 60)
        # self.client.loop_start()

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
        start_time = time.time()
        is_anomaly = 0
        is_alarm = 0
        anomaly_type = None
        check_for_anomalies = 1

        # logger.info(f"**************Recvd point {point}")

        def process_the_point(x,y):
            if (math.isnan(x) or math.isnan(y)):
                self.last_states.append(0)
                return 0

            if ((x<=self.cut_in_speed) or (x>self.cut_in_speed and y<self.min_power_th) or (x>self.cut_out_speed)):
                self.last_states.append(0)
                return 0

            return 1        

        # extract the wind speed and power from the point 
        point_dict = point.fieldsDouble
        x,y = point_dict[self.x_name], point_dict[self.y_name]
        # logger.info(f"Asset: {point.name}, x: {x}, y:{y}, cc:{self.enable_gcp_client}")

        # check if there is an active alarm for timestamp of the current point
        ns = point.time # in nanoseconds
        ts = pd.Timestamp(ns)

        # check if the current point is an anomalous point
        check_for_anomalies = process_the_point(x,y)

        if (check_for_anomalies):
            y_pred = self.rf.predict(np.reshape(x,(-1,1)))
            error = (y_pred[0]-y)/(y)
            if (error>self.error_threshold):
                self.last_states.append(1)
                self.last_anomalies.append((x,y))
            else:
                self.last_states.append(0)        

            # check if there are consecutive 3 anomalies, and then filter out any false positives
            if (sum(self.last_states)==self.n_steps):
                x_feat = list(zip(*self.last_anomalies))[0]
                x_feat = np.reshape(x_feat, (-1,1))
                y_feat = list(zip(*self.last_anomalies))[1]

                lm = LinearRegression()
                lm.fit(x_feat, y_feat)

                if (abs(lm.coef_)<200):
                    is_anomaly = 1
                    self.anomalies.append((x,y))     
                    if (error<0.3):
                        point.fieldsDouble['anomaly_status'] = 0.3
                        anomaly_type="LOW"
                    elif(error<0.6):
                        anomaly_type = "MEDIUM"
                        point.fieldsDouble['anomaly_status'] = 0.6
                    else:
                        anomaly_type = "HIGH"                    
                        point.fieldsDouble['anomaly_status'] = 1.0
                else:
                    self.last_states.append(0)

        # create a new dict from existing, as there is some problem in serializing the point_dict
        pub_point_dict = {'wind_speed':point_dict['wind_speed'], 
                       'grid_active_power':point_dict['grid_active_power']
                       }
        pub_point_dict = {key:value for key,value in point_dict.items()}
        for key, value in point.fieldsString.items():
            pub_point_dict[key] = value
        for key, value in point.fieldsBool.items():
            pub_point_dict[key] = value            
        pub_point_dict['time'] = ts.strftime('%Y-%m-%d %X')
        
        # write data back to db if it is an anomaly point or there is an alarm for the point
        response = udf_pb2.Response()
        response.point.CopyFrom(point)
        # Commenting out publishing this topic, as now the requirement is to publish just one topic
        # which has turbine name and anomaly value
        # base_mqtt_topic_name = point.name
        # mqtt_topics = {}
        # mqtt_topics[base_mqtt_topic_name+"/opcdata"] = str(pub_point_dict)
        if(is_anomaly):
            self._agent.write_response(response, True)
            # pub_point_dict['anomaly_type'] = anomaly_type
            # mqtt_topics[os.path.join(base_mqtt_topic_name,"anomaly")] = str(pub_point_dict)

        # mqtt_topics["events"] = str(pub_point_dict)

        # for topic in mqtt_topics.keys():
        #     # msg = json.dumps(pub_point_dict)
        #     self.client.publish(topic, mqtt_topics[topic])
        end_time = time.time()
        process_time = (end_time - start_time)*1000
        logger.debug(f"Function point took {process_time:.4f} milliseconds to complete.")

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
