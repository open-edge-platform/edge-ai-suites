# Running Tests for File Watcher Service

This guide will help you run the tests for the File Watcher service using the pytest framework.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Running Unit Test](#running-unit-test)

---

## Prerequisites

Before running the tests, ensure you have the following installed:

- For backend
   - Python (Visit [Python Official Website](https://www.python.org/downloads/))
   - `pip` (Python package installer)

## Running Unit Test

If you prefer to run the tests in a virtual environment, please follow these steps:

1. **Clone the Repository**

   Clone the repository to your local machine or download the source code as a ZIP file directly from the [repository](https://github.com/open-edge-platform/edge-ai-suites).:

   ```bash
   git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
   ```

2. **Create a Virtual Environment**

   Navigate to your project directory and create a virtual environment using `venv`:

   ```bash
   # Replace `<venv_name>` with your preferred name.
   python -m venv <venv_name>
   ```

3. **Activate the Virtual Environment**

    Activate the virtual environment:
    - On Windows:

      ```bash
      <venv_name>\Scripts\activate
      ```

    - On Linux:

      ```bash
      source <venv_name>/bin/activate
      ```

4. **Install the Required Packages**

    With the virtual environment activated, install the required packages:

    - On Windows:
      ```bash
      # Navigate to the test folder
      cd edge-ai-suites\manufacturing-ai-suite\hmi-augmented-worker\tests

      # Install the packages
      pip install -r requirements_dev.txt --no-cache-dir
      ```

      If you system is behind a proxy, do as follows:

      ```bash
      # Replace <your_proxy> and <port> to your network proxy and port number
      pip install -r requirements_dev.txt --no-cache-dir --proxy <your_proxy>:<port>
      ```

    - On Linux:
      ```bash
      # Navigate to the test folder
      cd edge-ai-suites/manufacturing-ai-suite/hmi-augmented-worker/tests

      # Install the packages
      pip install -r requirements_dev.txt --no-cache-dir
      ```

5. **Run the Tests**

   Use the `pytest` command to run the tests:

   ```bash
   pytest
   ```

   This will discover and run all the test cases defined in the `tests` directory.

6. **Deactivate Virtual Environment**

   Remember to deactivate the virtual environment when you are done with the test:

   ```bash
   deactivate
   ```

7. **Delete the Virtual Environment [OPTIONAL]**

    If you no longer need the virtual environment, you can delete it:

    ```bash
    # Navigate to the directory where venv is created in Step 1
    rm -rf venv
    ```