***Settings***
Documentation    This is main test case file.
Library          test_suite.py

***Keywords***

LdHelm_Test_case_001
    [Documentation]     [LoiteringDetection] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    ${status}          TC_001_LDHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

LdHelm_Test_case_002
    [Documentation]      [LoiteringDetection] Verify the webRTC streaming  - helm based
    ${status}          TC_002_LDHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

SpHelm_Test_case_001
    [Documentation]     [SmartParking] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    ${status}          TC_001_SPHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

SpHelm_Test_case_002
    [Documentation]      [SmartParking] Verify the webRTC streaming  - helm based
    ${status}          TC_002_SPHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

SiHelm_Test_case_001
    [Documentation]     [SmartIntersection] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    ${status}          TC_001_SIHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

SiHelm_Test_case_002
    [Documentation]      [SmartIntersection] Verify the webRTC streaming  - helm based
    ${status}          TC_002_SIHELM
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

***Test Cases***

LDHELM_TC_001
    [Documentation]    [LoiteringDetection] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   LdHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

LDHELM_TC_002
    [Documentation]    [LoiteringDetection] Verify the webRTC streaming  - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   LdHelm_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

SPHELM_TC_001
    [Documentation]    [SmartParking] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   SpHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

SPHELM_TC_002
    [Documentation]    [SmartParking] Verify the webRTC streaming  - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   SpHelm_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

SIHELM_TC_001
    [Documentation]    [SmartIntersection] Verify deploying the application and running multiple AI pipelines - backend : CPU - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   SiHelm_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

SIHELM_TC_002
    [Documentation]    [SmartIntersection] Verify the webRTC streaming  - helm based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   SiHelm_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0
