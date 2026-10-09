import unittest
import subprocess
import os
import sys

env = os.environ.copy()
SUITE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env["PYTHONPATH"] = os.pathsep.join(
    filter(None, [os.path.join(SUITE_ROOT, "common_library"), env.get("PYTHONPATH")])
)


class test_suite(unittest.TestCase):

    def _run_apps(self, test_case):
        env["TEST_CASE"] = test_case
        return subprocess.call(
            [sys.executable, "-m", "unittest", "functional_tests.apps.TestCaseManager.test_apps", "-v"],
            cwd=SUITE_ROOT,
            env=env,
        )

    def _run_helm_apps(self, test_case):
        env["TEST_CASE"] = test_case
        return subprocess.call(
            [sys.executable, "-m", "unittest", "functional_tests.apps_helm.TestCaseManager.test_metro_apps", "-v"],
            cwd=SUITE_ROOT,
            env=env,
        )

    ##################################################################################################################################################
    #                                   Test case with industrial_edge_insights_vision apps use cases
    ##################################################################################################################################################
    

    def TC_001_SP(self):
        return self._run_apps("SP001")

    def TC_002_SP(self):
        return self._run_apps("SP002")

    def TC_003_SP(self):
        return self._run_apps("SP003")

    def TC_004_SP(self):
        return self._run_apps("SP004")

    def TC_005_SP(self):
        return self._run_apps("SP005")
    
    def TC_006_SP(self):
        return self._run_apps("SP006")
    
    def TC_007_SP(self):
        return self._run_apps("SP007")

    def TC_001_LD(self):
        return self._run_apps("LD001")

    def TC_002_LD(self):
        return self._run_apps("LD002")

    def TC_003_LD(self):
        return self._run_apps("LD003")

    def TC_004_LD(self):
        return self._run_apps("LD004")

    def TC_005_LD(self):
        return self._run_apps("LD005")
    
    def TC_006_LD(self):
        return self._run_apps("LD006")
    
    def TC_007_LD(self):
        return self._run_apps("LD007")

    def TC_001_SI(self):
        return self._run_apps("SI001")

    def TC_002_SI(self):
        return self._run_apps("SI002")

    def TC_003_SI(self):
        return self._run_apps("SI003")

    def TC_004_SI(self):
        return self._run_apps("SI004")
    
    def TC_001_SPHELM(self):
        return self._run_helm_apps("SPHELM001")
    
    def TC_002_SPHELM(self):
        return self._run_helm_apps("SPHELM002")
    
    def TC_001_LDHELM(self):
        return self._run_helm_apps("LDHELM001")
    
    def TC_002_LDHELM(self):
        return self._run_helm_apps("LDHELM002")
    
    def TC_001_SIHELM(self):
        return self._run_helm_apps("SIHELM001")
    
    def TC_002_SIHELM(self):
        return self._run_helm_apps("SIHELM002")

if __name__ == '__main__':
    unittest.main()