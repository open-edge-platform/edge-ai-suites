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
        
        try:
            # Setup phase
            self.utils.setup(value)
            if value.get("setup-app"): return
            
            # Docker compose up phase
            self.utils.docker_compose_up(value)
            if value.get("verify_status"): return
            
            # Pipeline operations
            self.utils.start_pipeline_and_check(value)
            if value.get("sample_start"): return
            
            if value.get("sample_status"):
                self.utils.get_pipeline_status(value)
                return
            
            if value.get("sample_stop"):
                self.utils.stop_pipeline_and_check(value)
                return
            
            # Default full test flow
            self.utils.get_pipeline_status(value)
            if value.get("grafana_url"):
                self.utils.verify_grafana_url(value)
            else:
                self.utils.container_logs_checker_dlsps(test_case, value)
                self.utils.stop_pipeline_and_check(value)
        finally:
            self.utils.docker_compose_down(value)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.utils.metro_path)
        # subprocess.check_output("git checkout -- .", shell=True, executable='/bin/bash')
        time.sleep(5)