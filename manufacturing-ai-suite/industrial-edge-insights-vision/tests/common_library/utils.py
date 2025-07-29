import os
import time
import json
import logging
import subprocess
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
repo_path = os.path.abspath(os.path.join(current_dir, '../../../../'))
sys.path.extend([
    current_dir,
    repo_path,
    os.path.abspath(os.path.join(current_dir, '../configs/dlsps'))
])

hostIP = subprocess.check_output(
    "ip route get 1 | awk '{print $7}'|head -1", shell=True
).decode('utf-8').split("\n")[0]

class utils:
    def __init__(self):
        """Initialize the utils class with the base path."""
        self.path = repo_path

    def json_reader(self, tc, JSON_PATH):
        """
        Read a JSON file and return the value for the given test case key.

        Args:
            tc (str): Test case key.
            JSON_PATH (str): Path to the JSON file.

        Returns:
            tuple: (key, value) if found, else None.
        """
        print('\n**********Reading json**********')
        with open(JSON_PATH, "r") as jsonFile:
            json_config = json.load(jsonFile)
        for key, value in json_config.items():
            if key == tc:
                print("Test Case : ", key, "\nValue : ", value)
                return key, value

    def docker_compose_up(self, value):
        """
        Prepare the environment and start docker compose services for the test.

        Args:
            value (dict): Dictionary containing test type and other parameters.
        """
        print('\n\n**********Navigating to industrial-edge-insights-vision directory...')
        os.chdir('{}'.format(self.path + "/manufacturing-ai-suite/industrial-edge-insights-vision"))
        
        print('\n**********Copying appropriate .env file**********')
        if value.get("type") == "pdd":
            subprocess.check_output("cp .env_pallet_defect_detection .env", shell=True, executable='/bin/bash')
        elif value.get("type") == "weld":
            subprocess.check_output("cp .env_weld_porosity_classification .env", shell=True, executable='/bin/bash')
        
        print('\n**********Updating .env file**********')
        env_path = ".env"
        env_updates = {
            "HOST_IP": hostIP,
            "MTX_WEBRTCICESERVERS2_0_USERNAME": "intel1234",
            "MTX_WEBRTCICESERVERS2_0_PASSWORD": "intel1234"
        }
        with open(env_path, "r") as file:
            lines = file.readlines()
        with open(env_path, "w") as file:
            for line in lines:
                key = line.split("=")[0].strip()
                if key in env_updates:
                    file.write(f"{key}={env_updates[key]}\n")
                    env_updates.pop(key)
                else:
                    file.write(line)
            for key, value in env_updates.items():
                file.write(f"{key}={value}\n")
        
        print('\n**********Running setup.sh script**********')
        subprocess.check_output("./setup.sh", shell=True, executable='/bin/bash')

        print('\n\n***********Starting services with docker compose***********')
        try:
            subprocess.check_output("docker compose up -d", shell=True, executable='/bin/bash')
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to start services with docker compose. Command: {e.cmd}, Return Code: {e.returncode}, Output: {e.output}")
            raise

    def list_pipelines(self):
        """
        List the available pipelines using sample_list.sh and check server status.
        Raises an exception if pipelines are not loaded or server is unreachable.
        """
        print('\n\n**********List pipelines sample_list.sh**********')
        try:
            output = subprocess.check_output("./sample_list.sh", shell=True, executable='/bin/bash')
            output = output.decode('utf-8')  # Decode bytes to string
            print(f"sample_list.sh output:\n{output}")
            if "HTTP Status Code: 200" not in output:
                raise Exception("Server is not reachable. HTTP Status Code is not 200.")
            if "Loaded pipelines:" in output:
                pipelines = output.split("Loaded pipelines:")[1].strip()
                if not pipelines:
                    raise Exception("Loaded pipelines list is empty.")
                print("Server is reachable, and pipelines are loaded successfully.")
            else:
                raise Exception("Loaded pipelines information is missing in the output.")
        except Exception as e:
            logging.error(str(e))
            raise

    def start_pipeline_and_check(self, value):
        """
        Start the pipeline using sample_start.sh and check for success.

        Args:
            value (dict): Dictionary containing test type and other parameters.
        """
        time.sleep(5)
        os.chdir('{}'.format(self.path + "/manufacturing-ai-suite/industrial-edge-insights-vision"))
        print("\n\n**********Starting pipeline 'pallet_defect_detection' with sample_start.sh**********")
        try:
            if value.get("type")=="pdd":
                output = subprocess.check_output("./sample_start.sh -p pallet_defect_detection", shell=True, executable='/bin/bash')
            elif value.get("type")=="weld":
                output = subprocess.check_output("./sample_start.sh -p weld_porosity_classification", shell=True, executable='/bin/bash')
            output = output.decode('utf-8')  # Decode bytes to string
            print(f"sample_start.sh output:\n{output}")

            success_message = "posted successfully"
            if success_message not in output:
                raise Exception(f"Pipeline start failed. Expected message not found: '{success_message}'")
            response_index = output.find(success_message) + len(success_message)
            response_string = output[response_index:].strip()
            if not response_string:
                raise Exception("Response string is empty after posting payload.")
            print("Pipeline started successfully, and response string is valid.")
        except Exception as e:
            logging.error(str(e))
            raise

    def container_logs_checker_dlsps(self, tc, value):
        """
        Checks the logs of dlstreamer-pipeline-server for specific keywords.

        Args:
            tc (str): Test case identifier.
            value (dict): Dictionary containing keywords to check.

        Returns:
            bool: True if all keywords are found in the logs, False otherwise.
        """
        print('********** Checking dlstreamer-pipeline-server container logs **********')
        time.sleep(3)
        container = "dlstreamer-pipeline-server"
        log_file = f"logs_{container}_{tc}.txt"
        print(f"================== {container} ==================")
        subprocess.run(f"docker compose logs --tail=1000 {container} | tee {log_file}", shell=True, executable='/bin/bash', check=True)
        keywords = value.get("dlsps_log_param", [])
        log_present = all(self.search_element(log_file, keyword) for keyword in keywords)
        if log_present:
            print("PASS: All keywords found in logs.")
            return True
        else:
            print("FAIL: Keywords not found in logs.")
            return False

    def search_element(self, logFile, keyword):
        """
        Searches for a specific keyword in a log file.

        Args:
            logFile (str): Path to the log file.
            keyword (str): Keyword to search for.

        Returns:
            bool: True if the keyword is found, False otherwise.
        """
        keyword_found = False
        keywords_file = os.path.abspath(logFile)
        with open(keywords_file, 'rb') as file:
            for curr_line in file:
                each_line = curr_line.decode()
                print(each_line)
                if keyword in each_line:
                    keyword_found = True
        if keyword_found:
            print("PASS: Keyword Found", keyword)
            return True
        else:
            print("FAIL:Keyword NOT Found", keyword)
            return False

    def stop_pipeline_and_check(self):
        """
        Stop the pipeline using sample_stop.sh and check for success.
        Raises an exception if the pipeline does not stop successfully.
        """
        print("\n\n**********Stopping pipeline with sample_stop.sh**********")
        try:
            output = subprocess.check_output("./sample_stop.sh", shell=True, executable='/bin/bash')
            output = output.decode('utf-8')  # Decode bytes to string
            print(f"sample_stop.sh output:\n{output}")
            success_message = "stopped successfully"
            if success_message not in output:
                raise Exception(f"Pipeline stop failed. Expected message not found: '{success_message}'")
            print("Pipeline stopped successfully.")
        except Exception as e:
            logging.error(str(e))
            raise

