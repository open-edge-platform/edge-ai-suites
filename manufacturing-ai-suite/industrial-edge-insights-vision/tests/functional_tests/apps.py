import os
import time
import unittest
import utils as module

JSONPATH = os.path.dirname(os.path.abspath(__file__)) + '/../configs/config.json'

class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.path.dirname(os.path.abspath(__file__))
        cls.utils = module.utils()

class TestCaseManager(BaseTest):
    def test_apps(self):
        test_case = os.environ['TEST_CASE']
        key, value = self.utils.json_reader(test_case, JSONPATH)
        self.utils.docker_compose_up(value)
        time.sleep(3)

        self.utils.update_payload(value)
        self.utils.start_pipeline_and_check(value)
        
        if not value.get("check_sample_start"):
            self.utils.list_pipelines(value)
            
        if value.get("check_sample_status") or value.get("check_sample_stop") or (not value.get("check_sample_start") and not value.get("check_sample_list")):
            self.utils.get_pipeline_status(value)
            
        if not value.get("check_sample_start") and not value.get("check_sample_list") and not value.get("check_sample_status") and not value.get("check_sample_stop"):
            self.utils.container_logs_checker_dlsps(test_case, value)
            
        if value.get("check_sample_stop") or (not value.get("check_sample_start") and not value.get("check_sample_list") and not value.get("check_sample_status")):
            self.utils.stop_pipeline_and_check(value)
       

    @classmethod
    def tearDownClass(cls):
        cls.utils.docker_compose_down()
        time.sleep(5)