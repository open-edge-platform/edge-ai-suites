import unittest
import subprocess
import os

env = os.environ.copy()


class test_suite(unittest.TestCase):

    ##################################################################################################################################################
    #                                   Test case with industrial_edge_insights_vision apps use cases
    ##################################################################################################################################################
    
    def TC_001_app(self):
        env["TEST_CASE"] = "APP001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_002_app(self):
        env["TEST_CASE"] = "APP002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
   


if __name__ == '__main__':
    unittest.main()