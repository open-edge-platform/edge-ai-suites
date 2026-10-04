***Settings***
Documentation    This is main test case file.
Library          test_suite.py


***Keywords***


Sp_Test_case_001
    [Documentation]     [SmartParking] Verify install.sh to download the assets and check the assets are downloaded
    ${status}          TC_001_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_002
    [Documentation]      [SmartParking] docker compose up and verify the status of the containers 
    ${status}          TC_002_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_003
    [Documentation]      [SmartParking] run sample_start.sh to run predefined smart parking pipelines
    ${status}          TC_003_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_004
    [Documentation]      [SmartParking] Verify the ./sample_status.sh script and check the status
    ${status}          TC_004_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_005
    [Documentation]      [SmartParking] Verify ./sample_stop.sh script and check if all the streams have stopped
    ${status}          TC_005_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_006
    [Documentation]      [SmartParking] docker compose down and verify the status of all the containers
    ${status}          TC_006_SP
    Should Be Equal As Integers    ${status}    0

Sp_Test_case_007
    [Documentation]      [SmartParking] Run and view application output in grafana dashboard backend:CPU
    ${status}          TC_007_SP
    Should Be Equal As Integers    ${status}    0


Ld_Test_case_001
    [Documentation]     [LoiteringDetection] Verify install.sh to download the assets and check the assets are downloaded
    ${status}          TC_001_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_002
    [Documentation]      [LoiteringDetection] docker compose up and verify the status of the containers 
    ${status}          TC_002_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_003
    [Documentation]      [LoiteringDetection] run sample_start.sh to run predefined smart parking pipelines
    ${status}          TC_003_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_004
    [Documentation]      [LoiteringDetection] Verify the ./sample_status.sh script and check the status
    ${status}          TC_004_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_005
    [Documentation]      [LoiteringDetection] Verify ./sample_stop.sh script and check if all the streams have stopped
    ${status}          TC_005_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_006
    [Documentation]      [LoiteringDetection] docker compose down and verify the status of all the containers
    ${status}          TC_006_LD
    Should Be Equal As Integers    ${status}    0

Ld_Test_case_007
    [Documentation]      [LoiteringDetection] Run and view application output in grafana dashboard backend:CPU
    ${status}          TC_007_LD
    Should Be Equal As Integers    ${status}    0


Si_Test_case_001
    [Documentation]     [SmartIntersection] Verify install.sh to download the assets and check the assets are downloaded
    ${status}          TC_001_SI
    Should Be Equal As Integers    ${status}    0

Si_Test_case_002
    [Documentation]      [SmartIntersection] docker compose up and verify the status of the containers 
    ${status}          TC_002_SI
    Should Be Equal As Integers    ${status}    0

Si_Test_case_003
    [Documentation]      [SmartIntersection] docker compose down and verify the status of all the containers
    ${status}          TC_003_SI
    Should Be Equal As Integers    ${status}    0

Si_Test_case_004
    [Documentation]      [SmartIntersection] Run and view application output in grafana dashboard backend:CPU
    ${status}          TC_004_SI
    Should Be Equal As Integers    ${status}    0



***Test Cases***

#ALL the test cases related to SP usecase


SP_TC_001
    [Documentation]    [SmartParking] Verify install.sh to download the assets and check the assets are downloaded
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_001
    Should Be True    ${Status}

SP_TC_002
    [Documentation]    [SmartParking] docker compose up and verify the status of the containers 
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_002
    Should Be True    ${Status}

SP_TC_003
    [Documentation]    [SmartParking] run sample_start.sh to run predefined smart parking pipelines
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_003
    Should Be True    ${Status}

SP_TC_004
    [Documentation]    [SmartParking] Verify the ./sample_status.sh script and check the status
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_004
    Should Be True    ${Status}

SP_TC_005
    [Documentation]    [SmartParking] Verify ./sample_stop.sh script and check if all the streams have stopped
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_005
    Should Be True    ${Status}

SP_TC_006
    [Documentation]    [SmartParking] docker compose down and verify the status of all the containers
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_006
    Should Be True    ${Status}

SP_TC_007
    [Documentation]    [SmartParking] Run and view application output in grafana dashboard backend:CPU
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Sp_Test_case_007
    Should Be True    ${Status}

LD_TC_001
    [Documentation]    [LoiteringDetection] Verify install.sh to download the assets and check the assets are downloaded
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_001
    Should Be True    ${Status}

LD_TC_002
    [Documentation]    [LoiteringDetection] docker compose up and verify the status of the containers 
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_002
    Should Be True    ${Status}

LD_TC_003
    [Documentation]    [LoiteringDetection] run sample_start.sh to run predefined smart parking pipelines
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_003
    Should Be True    ${Status}

LD_TC_004
    [Documentation]    [LoiteringDetection] Verify the ./sample_status.sh script and check the status
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_004
    Should Be True    ${Status}

LD_TC_005
    [Documentation]    [LoiteringDetection] Verify ./sample_stop.sh script and check if all the streams have stopped
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_005
    Should Be True    ${Status}

LD_TC_006
    [Documentation]    [LoiteringDetection] docker compose down and verify the status of all the containers
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_006
    Should Be True    ${Status}

LD_TC_007
    [Documentation]    [LoiteringDetection] Run and view application output in grafana dashboard backend:CPU
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Ld_Test_case_007
    Should Be True    ${Status}

SI_TC_001
    [Documentation]    [SmartIntersection] Verify install.sh to download the assets and check the assets are downloaded
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Si_Test_case_001
    Should Be True    ${Status}

SI_TC_002
    [Documentation]    [SmartIntersection] docker compose up and verify the status of the containers 
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Si_Test_case_002
    Should Be True    ${Status}

SI_TC_003
    [Documentation]    [SmartIntersection] docker compose down and verify the status of all the containers
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Si_Test_case_003
    Should Be True    ${Status}

SI_TC_004
    [Documentation]    [SmartIntersection] Run and view application output in grafana dashboard backend:CPU
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Si_Test_case_004
    Should Be True    ${Status}
