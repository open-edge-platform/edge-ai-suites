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
        self.utils.update_values_helm(value)
        self.utils.helm_deploy(value)
        self.utils.start_pipeline_and_check(value, "helm")
        self.utils.list_pipelines(value, "helm")

        self.utils.get_pipeline_status(value, "helm")
        self.utils.container_logs_checker_helm(test_case,value)
        time.sleep(5)
        self.utils.stop_pipeline_and_check(value, "helm")


    @classmethod
    def tearDownClass(cls):
        cls.utils.helm_uninstall()
        time.sleep(5)