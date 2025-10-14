import unittest
import subprocess
import os

env = os.environ.copy()


class test_suite(unittest.TestCase):

    ##################################################################################################################################################
    #                                   Test case with industrial_edge_insights_vision apps use cases
    ##################################################################################################################################################
    

    def TC_001_SP(self):
        env["TEST_CASE"] = "SP001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_SP(self):
        env["TEST_CASE"] = "SP002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_SP(self):
        env["TEST_CASE"] = "SP003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_SP(self):
        env["TEST_CASE"] = "SP004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_005_SP(self):
        env["TEST_CASE"] = "SP005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_006_SP(self):
        env["TEST_CASE"] = "SP006"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_007_SP(self):
        env["TEST_CASE"] = "SP007"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_001_LD(self):
        env["TEST_CASE"] = "LD001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_LD(self):
        env["TEST_CASE"] = "LD002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_LD(self):
        env["TEST_CASE"] = "LD003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_LD(self):
        env["TEST_CASE"] = "LD004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_005_LD(self):
        env["TEST_CASE"] = "LD005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_006_LD(self):
        env["TEST_CASE"] = "LD006"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_007_LD(self):
        env["TEST_CASE"] = "LD007"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_001_SI(self):
        env["TEST_CASE"] = "SI001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_SI(self):
        env["TEST_CASE"] = "SI002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_SI(self):
        env["TEST_CASE"] = "SI003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_SI(self):
        env["TEST_CASE"] = "SI004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    

if __name__ == '__main__':
    unittest.main()