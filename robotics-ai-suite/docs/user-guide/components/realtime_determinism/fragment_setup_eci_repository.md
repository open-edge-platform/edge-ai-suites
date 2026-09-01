1. Open a terminal prompt which will be used to execute the remaining steps.

2. Download the ECI APT key to the system keyring:

    ```bash
    sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
    ```

    Add the signed entry to APT sources and configure the APT client to use the ECI APT repository:

    ```bash
    echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list
    echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list
    ```

3. Configure the ECI APT repository to have higher priority over other repositories and pin the version of the `libflann` packages:

    ```bash
    sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/isar'
    sudo bash -c 'echo -e "\nPackage: libflann*\nPin: version 1.19.*\nPin-Priority: -1\n\nPackage: flann*\nPin: version 1.19.*\nPin-Priority: -1" >> /etc/apt/preferences.d/isar'
    ```

4. Update the packages list:

    ```bash
    sudo apt update
    ```
