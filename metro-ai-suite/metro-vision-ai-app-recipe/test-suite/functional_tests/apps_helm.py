import os
import time
import unittest
import utils as module

JSONPATH = os.path.dirname(os.path.abspath(__file__)) + '/../configs/config.json'

class generate_repo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.path.dirname(os.path.abspath(__file__))
        cls.utils = module.utils()
        time.sleep(10)

    def test_generate_repo(self):
        self.utils.generate_repo()

class BaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.path.dirname(os.path.abspath(__file__))
        cls.utils = module.utils()

class TestCaseManager(BaseTest):
    def test_metro_apps(self):
        test_case = os.environ['TEST_CASE']
        key, value = self.utils.json_reader(test_case, JSONPATH)
        self.utils.update_values_helm(value)
        self.utils.helm_deploy(value)
        self.utils.helm_send_curl_requests(value)
        time.sleep(5)
        self.utils.container_logs_checker_helm(test_case,value)
        if value.get("app") == "SI":
            self.utils.helm_uninstall_complete_si(value)
        else:
            self.utils.helm_uninstall(value)
        time.sleep(5)