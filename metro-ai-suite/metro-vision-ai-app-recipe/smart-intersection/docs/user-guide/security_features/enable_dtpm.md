# Enable dTPM for Smart Intersection Security

**Prerequisites**: 
- dTPM module must be physically connected to the PTL Board
- Recommended: Infineon TPM (Xenon_4.1.0) for optimal Smart Intersection compatibility

## Step 1: Download Required Components

 Download IFWI Firmware

- Navigate
  to: [IFWI Firmware Download Location](https://www.intel.com/content/www/us/en/secure/content-details/858133/panther-lake-h-for-edge-platforms-uefi-reference-bios-ifwi-3214-54-alpha-and-3332-52-er-pre-beta.html?wapkw=ifwi&DocID=858133)

    - Download the IFWI file
    - You need to sign in to intel.com to get the access.
    - Extract the zip file.
    - Locate the binary file(*.bin) file according to your platform (e.g., `858133_ptl-h-refbios_releasepackage\858133_ptl-h-refbios3332_52releasepackage\IFWI\CRB\ECG_PTL_PR04_XXXX-XXXODCA_RPRF_SEP5_11E50692_2025WW34.4.02_BI333252_CRB.bin`)

- Navigate
  to: [MFIT Download Location](https://www.intel.com/content/www/us/en/secure/design/confidential/software-kits/kit-details.html?kitId=866974&wapkw=%20Consumer%20and%20Corporate%20Production)
    - Download "Intel_CSME_SW_PTL_2540.8.40.0_Consumer_Corporate.zip" under "Intel_CSME_SW_PTL_2540.8.40.0_Consumer_Corporate"
    - Extract the downloaded zip file
    - "mfi.exe" will be located under "Intel_Silicon_FW_Kit_PTL-H12Xe_ES1_ES2_2025WW41.2.02\Tools\System_Tools\MFIT\Windows64"

## Step 2: Configure IFWI with dTPM Support

1. **Launch MFIT Tool**: Execute `mfit.exe` and wait for the application to fully load.

2. **Decompose Original IFWI**: 
   - Click the **"Decompose Image"** button
   - Select the downloaded IFWI file from the extracted directory
   - Wait for the decomposition process to complete
modul
![MFIT Tool Interface](../_images/security_mfit_tool_interface.png)
![IFWI Decomposition Process](../_images/security_ifwi_decomposition_process.png)

3. **Enable dTPM Configuration & Build Image**:
   - Navigate to **"Platform Protection Features"** section
   - Locate **"TPM Technologies"** subsection
   - From the available TPM options, select **"dTPM"**
   - Click **"Build Image"** to generate the new firmware image
   - The tool will create a new IFWI file named `image.bin` in the same directory
   - Verify the `image.bin` file has been successfully created

![dTPM Configuration Settings](../_images/security_dtpm_configuration_settings.png)

## Step 3: Flash the Modified IFWI

> **Important**: Power OFF the PTL board before flashing

1. **Prepare Flashing Environment**:
   - Ensure the PTL board is properly connected to the flashing hardware
   - Verify DediProg or TTK3 is correctly configured and recognized

2. **Flash the New IFWI**:
   - Using your preferred flashing tool (DediProg or TTK3), load the newly generated `image.bin` file
   - Initiate the flashing process
   - Monitor the flashing progress for any errors
   - Power cycle the PTL board after successful flashing

3. **Verify dTPM Functionality**:
   - Check that dTPM functionality is enabled in the system BIOS/UEFI
   - Confirm dTPM is properly detected by the operating system

