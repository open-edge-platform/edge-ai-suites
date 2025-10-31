#	System Requirements

## Hardware requirements

- Platform

    - Intel® Celeron® Processor 7305E (1C+1R/2C+1R usecase)
    - Intel® Core™ Ultra 7 Processor 165H (4C+4R usecase)

    - Intel® Core™ i7-13700 and Intel® Arc™ A770 Graphics (16C+4R usecase)

- BIOS setting

    - MTL

        | Setting                                          | Step                                                         |
        | ------------------------------------------------ | ------------------------------------------------------------ |
        | Enable the Hidden BIOS Setting in Seavo Platform | "Right Shift+F7" Then Change Enabled Debug Setup Menu from [Enabled] to [Disable] |
        | Disable VT-d in BIOS                             | Intel Advanced Menu → System Agent (SA) Configuration → VT-d setup menu → VT-d<Disabled>    <br>Note: If VT-d can’t be disabled, disable Intel Advanced Menu → CPU Configuration → X2APIC |
        | Disable SAGV in BIOS                             | Intel Advanced Menu → [System Agent (SA) Configuration]  →  Memory configuration →  SAGV <Disabled> |
        | Enable NPU Device                                | Intel Advanced Menu → CPU Configuration → Active SOC-North Efficient-cores <ALL>   <br>Intel Advanced Menu → System Agent (SA) Configuration → NPU Device <Enabled> |
        | TDP Configuration                                | SOC TDP configuration is very important for performance. Suggestion: TDP = 45W. For extreme heavy workload, TDP = 64W <br>---TDP = 45W settings: Intel Advanced → Power & Performance → CPU - Power Management Control → Config TDP Configurations → Power Limit 1 <45000> <br>---TDP = 64W settings: Intel Advanced → Power & Performance → CPU - Power Management Control → Config TDP Configurations →  Configurable TDP Boot Mode [Level2] |

    - RPL-S+A770

        | Setting                  | Step                                                         |
        | ------------------------ | ------------------------------------------------------------ |
        | Enable ResizeBar in BIOS | Intel Advanced Menu -> System Agent (SA) Configuration -> PCI Express Configuration -> PCIE Resizable BAR Support <Enabled> |



## Software requirements

| Software           | Version                |
| ------------------ | ---------------------- |
| Intel  OpenVINO    | 2025.2.0               |
| Intel  oneMKL      | 2025.1.0               |
| NEO OpenCL         | Release/23.22.26516.25 |
| cmake              | 3.21.2                 |
| boost              | 1.83.0                 |
| spdlog             | 1.8.2                  |
| thrift             | 0.18.1                 |
| gRPC               | 1.58.1                 |
| zlib               | 1.3.1                 |
| oneAPI Level  Zero | 1.17.19                |