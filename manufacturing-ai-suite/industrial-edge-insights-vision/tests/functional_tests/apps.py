import os
import time
import unittest
import utils as module
import subprocess

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
        time.sleep(5)
        self.utils.list_pipelines()
        self.utils.start_pipeline_and_check(value)
        time.sleep(5)
        self.utils.container_logs_checker_dlsps(test_case,value)

    @classmethod
    def tearDownClass(cls):
        cls.utils.stop_pipeline_and_check()
        subprocess.run("docker compose down -v", shell=True, executable='/bin/bash', cwd=cls.utils.path + "/manufacturing-ai-suite/industrial-edge-insights-vision")
        time.sleep(5)