***Settings***
Documentation    This is main test case file.
Library          test_suite.py


***Keywords***

Pdd_Test_case_001
    [Documentation]     PDD - Validate docker compose based PDD deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    ${status}          TC_001_PDD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pdd_Test_case_002
    [Documentation]      PDD - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    ${status}          TC_002_PDD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pdd_Test_case_003
    [Documentation]      PDD - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    ${status}          TC_003_PDD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pdd_Test_case_004
    [Documentation]      PDD - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    ${status}          TC_004_PDD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pdd_Test_case_005
    [Documentation]      PDD - Validate stopping the app containers using docker compose down -v  : docker-compose based
    ${status}          TC_005_PDD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Weld_Test_case_001
    [Documentation]     WELD - Validate docker compose based WELD deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    ${status}          TC_001_WELD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Weld_Test_case_002
    [Documentation]      WELD - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    ${status}          TC_002_WELD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Weld_Test_case_003
    [Documentation]      WELD - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    ${status}          TC_003_WELD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Weld_Test_case_004
    [Documentation]      WELD - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    ${status}          TC_004_WELD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Weld_Test_case_005
    [Documentation]      WELD - Validate stopping the app containers using docker compose down -v  : docker-compose based
    ${status}          TC_005_WELD
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pcb_Test_case_001
    [Documentation]     PCB - Validate docker compose based PCB deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    ${status}          TC_001_PCB
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pcb_Test_case_002
    [Documentation]      PCB - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    ${status}          TC_002_PCB
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pcb_Test_case_003
    [Documentation]      PCB - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    ${status}          TC_003_PCB
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pcb_Test_case_004
    [Documentation]      PCB - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    ${status}          TC_004_PCB
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Pcb_Test_case_005
    [Documentation]      PCB - Validate stopping the app containers using docker compose down -v  : docker-compose based
    ${status}          TC_005_PCB
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Wsg_Test_case_001
    [Documentation]     WSG - Validate docker compose based WSG deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    ${status}          TC_001_WSG
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Wsg_Test_case_002
    [Documentation]      WSG - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    ${status}          TC_002_WSG
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Wsg_Test_case_003
    [Documentation]      WSG - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    ${status}          TC_003_WSG
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Wsg_Test_case_004
    [Documentation]      WSG - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    ${status}          TC_004_WSG
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}

Wsg_Test_case_005
    [Documentation]      WSG - Validate stopping the app containers using docker compose down -v  : docker-compose based
    ${status}          TC_005_WSG
    Should Not Be Equal As Integers    ${status}    1
    RETURN         Run Keyword And Return Status    ${status}



***Test Cases***

#ALL the test cases related to PDD usecase

PDD_TC_001
    [Documentation]    PDD - Validate docker compose based PDD deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pdd_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

PDD_TC_002
    [Documentation]    PDD - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pdd_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

PDD_TC_003
    [Documentation]    PDD - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pdd_Test_case_003
    Should Not Be Equal As Integers    ${Status}    0

PDD_TC_004
    [Documentation]    PDD - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pdd_Test_case_004
    Should Not Be Equal As Integers    ${Status}    0

PDD_TC_005
    [Documentation]    PDD - Validate stopping the app containers using docker compose down -v  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pdd_Test_case_005
    Should Not Be Equal As Integers    ${Status}    0

WELD_TC_001
    [Documentation]    WELD - Validate docker compose based WELD deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Weld_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

WELD_TC_002
    [Documentation]    WELD - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Weld_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

WELD_TC_003
    [Documentation]    WELD - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Weld_Test_case_003
    Should Not Be Equal As Integers    ${Status}    0

WELD_TC_004
    [Documentation]    WELD - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Weld_Test_case_004
    Should Not Be Equal As Integers    ${Status}    0

WELD_TC_005
    [Documentation]    WELD - Validate stopping the app containers using docker compose down -v  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Weld_Test_case_005
    Should Not Be Equal As Integers    ${Status}    0

PCB_TC_001
    [Documentation]    PCB - Validate docker compose based PCB deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pcb_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

PCB_TC_002
    [Documentation]    PCB - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pcb_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

PCB_TC_003
    [Documentation]    PCB - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pcb_Test_case_003
    Should Not Be Equal As Integers    ${Status}    0

PCB_TC_004
    [Documentation]    PCB - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pcb_Test_case_004
    Should Not Be Equal As Integers    ${Status}    0

PCB_TC_005
    [Documentation]    PCB - Validate stopping the app containers using docker compose down -v  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Pcb_Test_case_005
    Should Not Be Equal As Integers    ${Status}    0

WSG_TC_001
    [Documentation]    WSG - Validate docker compose based WSG deployment and pipeline startup using  ./sample_start.sh : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Wsg_Test_case_001
    Should Not Be Equal As Integers    ${Status}    0

WSG_TC_002
    [Documentation]    WSG - Verify the loaded pipelines	using sample_list.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Wsg_Test_case_002
    Should Not Be Equal As Integers    ${Status}    0

WSG_TC_003
    [Documentation]    WSG - Verify pipeline status of all/specific instance using sample_status.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Wsg_Test_case_003
    Should Not Be Equal As Integers    ${Status}    0

WSG_TC_004
    [Documentation]    WSG - Validate stopping of running pipeline using sample_stop.sh  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Wsg_Test_case_004
    Should Not Be Equal As Integers    ${Status}    0

WSG_TC_005
    [Documentation]    WSG - Validate stopping the app containers using docker compose down -v  : docker-compose based
    [Tags]      app
    ${Status}    Run Keyword And Return Status   Wsg_Test_case_005
    Should Not Be Equal As Integers    ${Status}    0