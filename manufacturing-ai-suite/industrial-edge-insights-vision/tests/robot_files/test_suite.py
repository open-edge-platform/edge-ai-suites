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
            [sys.executable, "-m", "unittest", "functional_tests.apps_helm.TestCaseManager.test_apps", "-v"],
            cwd=SUITE_ROOT,
            env=env,
        )

    ##################################################################################################################################################
    #                                   Test case with industrial_edge_insights_vision apps use cases
    ##################################################################################################################################################
    

    def TC_001_PDD(self):
        return self._run_apps("PDD001")

    def TC_002_PDD(self):
        return self._run_apps("PDD002")

    def TC_003_PDD(self):
        return self._run_apps("PDD003")

    def TC_004_PDD(self):
        return self._run_apps("PDD004")

    def TC_005_PDD(self):
        return self._run_apps("PDD005")

    def TC_001_PCB(self):
        return self._run_apps("PCB001")

    def TC_002_PCB(self):
        return self._run_apps("PCB002")

    def TC_003_PCB(self):
        return self._run_apps("PCB003")

    def TC_004_PCB(self):
        return self._run_apps("PCB004")
    
    def TC_005_PCB(self):
        return self._run_apps("PCB005")
    
    def TC_001_PDDHELM(self):
        return self._run_helm_apps("PDDHELM001")

    def TC_001_PCBHELM(self):
        return self._run_helm_apps("PCBHELM001")



if __name__ == '__main__':
    unittest.main()