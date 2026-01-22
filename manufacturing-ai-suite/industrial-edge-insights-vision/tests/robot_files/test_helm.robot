***Settings***
Documentation    This is main test case file.
Library          test_suite.py

***Keywords***

PddHelm_Test_case_001
    [Documentation]     PDD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_PDDHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

PcbHelm_Test_case_001
    [Documentation]     PCB - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_PCBHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

WeldHelm_Test_case_001
    [Documentation]     WELD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_WELDHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

WsgHelm_Test_case_001
    [Documentation]     WSG - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    ${status}          TC_001_WSGHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}



***Test Cases***

#ALL the test cases related to PDD usecase

PDDHELM_TC_001
    [Documentation]    PDD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   PddHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

PCBHELM_TC_001
    [Documentation]    PCB - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   PcbHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

WELDHELM_TC_001
    [Documentation]    WELD - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   WeldHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

WSGHELM_TC_001
    [Documentation]    WSG - Verify the helm chart and helm install  - Deploy the applcation steps on CPU and uninstall Helm
    [Tags]      app
    ${Status}    Run Keyword And Return Status   WsgHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0