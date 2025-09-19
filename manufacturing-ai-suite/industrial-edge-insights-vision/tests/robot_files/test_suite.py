import unittest
import subprocess
import os

env = os.environ.copy()


class test_suite(unittest.TestCase):

    ##################################################################################################################################################
    #                                   Test case with industrial_edge_insights_vision apps use cases
    ##################################################################################################################################################
    

    def TC_001_PDD(self):
        env["TEST_CASE"] = "PDD001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_PDD(self):
        env["TEST_CASE"] = "PDD002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_PDD(self):
        env["TEST_CASE"] = "PDD003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_PDD(self):
        env["TEST_CASE"] = "PDD004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_005_PDD(self):
        env["TEST_CASE"] = "PDD005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_001_WELD(self):
        env["TEST_CASE"] = "WELD001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_WELD(self):
        env["TEST_CASE"] = "WELD002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_WELD(self):
        env["TEST_CASE"] = "WELD003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_WELD(self):
        env["TEST_CASE"] = "WELD004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_005_WELD(self):
        env["TEST_CASE"] = "WELD005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_001_PCB(self):
        env["TEST_CASE"] = "PCB001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_PCB(self):
        env["TEST_CASE"] = "PCB002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_PCB(self):
        env["TEST_CASE"] = "PCB003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_PCB(self):
        env["TEST_CASE"] = "PCB004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_005_PCB(self):
        env["TEST_CASE"] = "PCB005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_001_WSG(self):
        env["TEST_CASE"] = "WSG001"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_002_WSG(self):
        env["TEST_CASE"] = "WSG002"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_003_WSG(self):
        env["TEST_CASE"] = "WSG003"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

    def TC_004_WSG(self):
        env["TEST_CASE"] = "WSG004"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret
    
    def TC_005_WSG(self):
        env["TEST_CASE"] = "WSG005"
        ret = subprocess.call("nosetests3 --nocapture -v ../functional_tests/apps.py:TestCaseManager.test_apps", shell=True, env=env)
        return ret

if __name__ == '__main__':
    unittest.main()