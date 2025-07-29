# Automation Framework for Industrial Edge Insights Vision

This directory contains happy path test scripts and utility functions required for automation testing.

### Installation Steps:

1. **Update the system and install required packages:**

    ```sh
    sudo apt-get update
    sudo pip3 install robotframework
    sudo apt install python3-nose
    ```

## Automation Tests Folder Structure

The folder structure is designed to ensure a clear and organized workflow.

### Folder Structure:

1. **configs:** Contains files required to configure the environment.
2. **common_library:** Contains utility scripts.
3. **functional_tests:** Contains Python test files.
4. **robot_files:** Contains Robot Framework test files.

```
tests 
  |--> configs 
  |--> common_library
  |--> functional_tests
  |--> robot_files
```

## Running Industrial Edge Insights Vision Automation Tests

To run sanity test cases for Industrial Edge Insights Vision, use the following command:

```sh
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/tests/robot_files
robot test.robot
```

- **Explanation:**
  - `robot test.robot` executes the Robot Framework sanity test file.

After running the tests, the following files will be generated in the `robot_files` directory:
- `log.html`
- `output.xml`
- `report.html`

To view the test results, open the `report.html` file in a web browser.