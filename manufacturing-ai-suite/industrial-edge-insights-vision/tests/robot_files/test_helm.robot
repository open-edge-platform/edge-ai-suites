***Settings***
Documentation    This is main test case file.
Library          test_suite.py

***Keywords***

PddHelm_Test_case_001
    [Documentation]     PDD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_PDDHELM
    Should Be Equal As Integers    ${status}    0

PcbHelm_Test_case_001
    [Documentation]     PCB - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_PCBHELM
    Should Be Equal As Integers    ${status}    0



***Test Cases***

#ALL the test cases related to PDD usecase

PDDHELM_TC_001
    [Documentation]    PDD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   PddHelm_Test_case_001
    Should Be True    ${Status}

PCBHELM_TC_001
    [Documentation]    PCB - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   PcbHelm_Test_case_001
    Should Be True    ${Status}