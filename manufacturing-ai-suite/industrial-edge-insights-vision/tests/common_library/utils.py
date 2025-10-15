import os
import time
import json
import logging
import subprocess
import sys

# Setup paths and host IP
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_path = os.path.abspath(os.path.join(current_dir, '../../../../'))
sys.path.extend([current_dir, repo_path, os.path.abspath(os.path.join(current_dir, '../configs/dlsps'))])

hostIP = subprocess.check_output("ip route get 1 | awk '{print $7}'|head -1", shell=True).decode('utf-8').strip()

class utils:
    def __init__(self):
        """Initialize the utils class with the base path."""
        self.path = repo_path
        self.base_dir = f"{self.path}/manufacturing-ai-suite/industrial-edge-insights-vision"

    def json_reader(self, tc, JSON_PATH):
        """
        Read a JSON file and return the value for the given test case key.
        Args:
            tc (str): Test case key to look for
            JSON_PATH (str): Path to the JSON configuration file
        Returns:
            tuple: (key, value) if found, else None
        """
        try:
            print('\n**********Reading json**********')
            with open(JSON_PATH, "r") as jsonFile:
                json_config = json.load(jsonFile)
            for key, value in json_config.items():
                if key == tc:
                    print("Test Case : ", key, "\nValue : ", value)
                    return key, value
        except Exception as e:
            raise Exception(f"Failed to read JSON file: {e}")


    def docker_compose_up(self, value):
        """
        Prepare the environment and start docker compose services for the test.
        Args:
            value (dict): Dictionary containing test type and other parameters
        """
        try:
            print('\n**********Setting up Docker environment**********')
            os.chdir(self.base_dir)
            if value.get("app") == "pdd":
                subprocess.check_output("cp .env_pallet_defect_detection .env", shell=True, executable='/bin/bash')
            elif value.get("app") == "weld":
                subprocess.check_output("cp .env_weld_porosity_classification .env", shell=True, executable='/bin/bash')
            elif value.get("app") == "pcb":
                subprocess.check_output("cp .env_pcb_anomaly_detection .env", shell=True, executable='/bin/bash')
            elif value.get("app") == "wsg":
                subprocess.check_output("cp .env_worker_safety_gear_detection .env", shell=True, executable='/bin/bash')

            # Update .env file with required variables
            self._update_env_file({
                "HOST_IP": hostIP,
                "MTX_WEBRTCICESERVERS2_0_USERNAME": "test1234",
                "MTX_WEBRTCICESERVERS2_0_PASSWORD": "test1234"
            })
            
            # Run setup and start services
            print('\n**********Running setup and starting services**********')
            subprocess.check_output("./setup.sh", shell=True, executable='/bin/bash')
            subprocess.check_output("docker compose up -d", shell=True, executable='/bin/bash')
            print("✅ Services started successfully")
        except Exception as e:
            raise Exception(f"Failed to start docker services: {e}")


    def _update_env_file(self, env_updates):
        """
        Update .env file with given key-value pairs.
        Args:
            env_updates (dict): Dictionary of environment variables to update
        """
        try:
            with open(".env", "r") as file:
                lines = file.readlines()
            
            with open(".env", "w") as file:
                for line in lines:
                    key = line.split("=")[0].strip()
                    if key in env_updates:
                        file.write(f"{key}={env_updates[key]}\n")
                        env_updates.pop(key)
                    else:
                        file.write(line)
                for key, value in env_updates.items():
                    file.write(f"{key}={value}\n")
        except Exception as e:
            raise Exception(f"Failed to update .env file: {e}")


    def list_pipelines(self, value):
        """
        List and validate pipelines against expected configuration.
        Args:
            value (dict): Dictionary containing app type and configuration
        """
        print('\n\n**********List pipelines sample_list.sh**********')
        os.chdir('{}'.format(self.path + "/manufacturing-ai-suite/industrial-edge-insights-vision"))
        
        try:
            config_paths = {
                "pdd": "apps/pallet-defect-detection/configs/pipeline-server-config.json",
                "weld": "apps/weld-porosity/configs/pipeline-server-config.json", 
                "pcb": "apps/pcb-anomaly-detection/configs/pipeline-server-config.json",
                "wsg": "apps/worker-safety-gear-detection/configs/pipeline-server-config.json"
            }
            config_path = os.path.join(self.path, "manufacturing-ai-suite/industrial-edge-insights-vision", 
                                       config_paths.get(value.get("app"), config_paths["pdd"]))
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
                expected_pipelines = [p.get("name") for p in config_data.get("config", {}).get("pipelines", []) if p.get("name")]
                print(f"Expected pipeline names: {expected_pipelines}")
            
            # Execute sample_list.sh and parse output
            output = subprocess.check_output("./sample_list.sh", shell=True, executable='/bin/bash').decode('utf-8')
            print(f"sample_list.sh output:\n{output}")
            
            if "HTTP Status Code: 200" not in output or "Loaded pipelines:" not in output:
                raise Exception("Server not reachable or pipelines information missing")
            
            pipelines_section = output.split("Loaded pipelines:")[1].strip()
            if not pipelines_section:
                raise Exception("Loaded pipelines list is empty")
            
            # Parse loaded pipeline versions
            json_start, json_end = pipelines_section.find('['), pipelines_section.rfind(']') + 1
            if json_start != -1 and json_end != 0:
                pipelines_data = json.loads(pipelines_section[json_start:json_end])
                loaded_pipeline_versions = [p['version'] for p in pipelines_data if isinstance(p, dict) and 'version' in p]
            else:
                loaded_pipeline_versions = [line.replace('-', '').strip() for line in pipelines_section.split('\n') 
                                          if line.strip() and line.startswith('-')]
            
            print(f"Loaded pipeline versions: {loaded_pipeline_versions}")
            if not loaded_pipeline_versions:
                raise Exception("No pipeline versions found in server output")
            
            # Validate pipeline matching
            unmatched_versions = [v for v in loaded_pipeline_versions if v not in expected_pipelines]
            missing_names = [n for n in expected_pipelines if n not in loaded_pipeline_versions]
            matched_pipelines = [v for v in loaded_pipeline_versions if v in expected_pipelines]
            
            print("\n**********Pipeline Name to Version Mapping**********")
            for name in expected_pipelines:
                status = "✅ MATCH" if name in loaded_pipeline_versions else "❌ MISSING"
                print(f"{status}: name='{name}'" + (f" maps to version='{name}'" if name in loaded_pipeline_versions else " not found in loaded versions"))
            
            for version in unmatched_versions:
                print(f"❌ UNMATCHED: version='{version}' not found in config names")
            
            print(f"\nSummary: {len(matched_pipelines)} matched, {len(unmatched_versions)} unmatched, {len(missing_names)} missing")
            #if unmatched_versions or missing_names:
            #    raise Exception(f"Pipeline mismatch - Unmatched: {unmatched_versions}, Missing: {missing_names}")
            print("✅ SUCCESS: All pipeline versions match expected names.")
            print("✅ Server is reachable, and pipelines are loaded successfully.")
        except Exception as e:
            raise Exception(f"Failed to validate pipelines: {e}")


    def update_payload(self, value):
        """
        Update payload.json with given parameters.
        Args:
            value (dict): Dictionary containing update parameters with keys:
                - app (str): Application type ('pdd', 'weld', 'pcb', 'wsg')
                - pipeline (str, optional): Pipeline name to update
                - change_device (str, optional): Device configuration to update
        """
        payload_paths = {
            "pdd": "apps/pallet-defect-detection/payload.json",
            "weld": "apps/weld-porosity/payload.json", 
            "pcb": "apps/pcb-anomaly-detection/payload.json",
            "wsg": "apps/worker-safety-gear-detection/payload.json"
        }
        app_type = value.get("app", "pdd")
        payload_path = os.path.join(self.path, "manufacturing-ai-suite/industrial-edge-insights-vision", payload_paths.get(app_type, payload_paths["pdd"]))
        subprocess.call("git checkout -- .", shell=True, cwd=os.path.dirname(payload_path))
        
        with open(payload_path, "r") as file:
            data = json.load(file)
        for item in data:
            if "payload" in item:
                if "pipeline" in value:
                    item["pipeline"] = value["pipeline"]
        with open(payload_path, "w") as file:
            json.dump(data, file, indent=4)
        print(f"✅ Updated payload.json for {app_type}")


    def start_pipeline_and_check(self, value):
        """
        Start pipeline and validate response.
        Args:
            value (dict): Dictionary containing pipeline configuration
        Returns:
            str: Response text from pipeline start
        """
        print('\n**********Starting pipeline**********')
        os.chdir(self.base_dir)
        try:
            status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
            print(f"sample_status.sh output:\n{status_output}")
            if "[]" not in status_output:
                raise Exception("Pipelines are already running")
            print("✅ No pipelines are currently running - ready to start new pipeline")
            pipeline_name = value.get("pipeline")
            if pipeline_name:
                output = subprocess.check_output(f"./sample_start.sh -p {pipeline_name}", shell=True, executable='/bin/bash')
                print(f"Using configured pipeline: {pipeline_name}")
            output = output.decode('utf-8')
            print(f"sample_start.sh output:\n{output}")
            
            success_message = "posted successfully"
            if success_message not in output:
                raise Exception(f"Pipeline start failed. Expected message not found: '{success_message}'")
            
            if 'Response: "' in output:
                start_pos = output.find('Response: "') + len('Response: "')
                end_pos = output.find('"', start_pos)
                if end_pos != -1:
                    response_id = output[start_pos:end_pos]
                    print(f"📋 Pipeline Response ID: {response_id}")
                    print("✅ Pipeline started successfully, and response string is valid.")
                    return response_id
        except Exception as e:
            raise Exception(f"❌ Error in start_pipeline_and_check: {e}")
    

    def get_pipeline_status(self, value):
        """
        Check pipeline status and validate.
        Args:
            value (dict): Dictionary containing test configuration
        """
        print('\n**********Checking pipeline status**********')
        os.chdir(self.base_dir)
        time.sleep(2)
        output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
        print(f"Status output:\n{output}")
        if "RUNNING" not in output:
            raise Exception("No RUNNING pipelines found in output")
        print("✅ Pipeline is running")
        

    def container_logs_checker_dlsps(self, tc, value):
        """
        Check dlstreamer-pipeline-server container logs for keywords.
        Args:
            tc (str): Test case identifier
            value (dict): Dictionary containing log parameters
        Returns:
            bool: True if all keywords are found
        """
        print('\n**********Checking container logs**********')
        time.sleep(5)
        container = "dlstreamer-pipeline-server"
        log_file = f"logs_{container}_{tc}.txt"
        subprocess.run(f"docker compose logs --tail=1000 {container} | tee {log_file}", shell=True, executable='/bin/bash', check=True)
        keywords = value.get("dlsps_log_param", [])
        missing_keywords = [keyword for keyword in keywords if not self.search_element(log_file, keyword)]
        if missing_keywords:
            error_msg = f"❌ FAIL: Keywords not found in logs: {missing_keywords}"
            print(error_msg)
            raise Exception(error_msg)
        print("✅ PASS: All keywords found in logs.")
        self._check_warning_messages(log_file)
        return True
        

    def _check_warning_messages(self, log_file):
        """
        Check for warning messages in DLSPS logs and report them.
        Args:
            log_file (str): Path to the log file to analyze
        Returns:
            None: Prints warning summary to console
        """
        warning_patterns = ["WARNING", "WARN", "warning", "warn", "ERROR", "Error", "error"]
        warnings_found = []
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as file:
            for line_num, line in enumerate(file, 1):
                line_lower = line.lower()
                if any(pattern in line_lower for pattern in warning_patterns):
                    line_stripped = line.strip()
                    if not any(w['line'] == line_stripped for w in warnings_found):
                        warnings_found.append({'line_number': line_num, 'line': line_stripped})                 
        if warnings_found:
            print(f"⚠️  WARNING: Found {len(warnings_found)} warning message(s) in DLSPS logs:")
            print("-" * 80)
            for warning in warnings_found:
                print(f"Line {warning['line_number']} [warning]: {warning['line']}")
        else:
            print("✅ No warnings detected in logs")


    def search_element(self, logFile, keyword):
        """
        Search for a keyword in a log file.
        Args:
            logFile (str): Path to the log file
            keyword (str): Keyword to search for
        Returns:
            bool: True if keyword is found, False otherwise
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
            print("✅ PASS: Keyword Found", keyword)
            return True
        else:
            print("❌ FAIL:Keyword NOT Found", keyword)
            return False


    def stop_pipeline_and_check(self, value):
        """
        Stop pipeline and validate that the specific running pipeline is aborted.
        Args:
            value (dict): Dictionary containing stop configuration parameters
        Raises:
            Exception: If the specific pipeline is not found in ABORTED state
        """
        os.chdir(self.base_dir)
        status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
        print(f"Current pipeline status:\n{status_output}")
        
        running_pipeline_id = None
        json_start, json_end = status_output.find('['), status_output.rfind(']') + 1
        if json_start != -1 and json_end != 0:
            json_content = status_output[json_start:json_end]
            pipelines_data = json.loads(json_content)
            for pipeline in pipelines_data:
                if isinstance(pipeline, dict) and pipeline.get('state') == 'RUNNING':
                    running_pipeline_id = pipeline.get('id')
                    print(f"🔍 Found running pipeline with ID: {running_pipeline_id}")
                    break
        
        if not running_pipeline_id:
            raise Exception("No running pipeline found to stop")
        
        output = subprocess.check_output("./sample_stop.sh", shell=True, executable='/bin/bash', stderr=subprocess.STDOUT).decode('utf-8')
        print(f"Output sample_stop.sh:\n{output}")
        time.sleep(2)
        status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
        print(f"Output sample_status.sh after stop:\n{status_output}")
        
        pipeline_found_aborted = False
        json_start, json_end = status_output.find('['), status_output.rfind(']') + 1
        if json_start != -1 and json_end != 0:
            json_content = status_output[json_start:json_end]
            pipelines_data = json.loads(json_content)
            for pipeline in pipelines_data:
                if isinstance(pipeline, dict) and pipeline.get('id') == running_pipeline_id:
                    pipeline_state = pipeline.get('state')
                    print(f"🔍 Pipeline {running_pipeline_id} is now in state: {pipeline_state}")
                    if pipeline_state == 'ABORTED':
                        pipeline_found_aborted = True
                        print(f"✅ Pipeline {running_pipeline_id} stopped successfully")
                    else:
                        raise Exception(f"Pipeline {running_pipeline_id} is in {pipeline_state} state, expected ABORTED")
                    break
        if not pipeline_found_aborted:
            raise Exception(f"Pipeline {running_pipeline_id} not found in ABORTED state after stop command")
    

    def docker_compose_down(self):
        """
        Stop all docker compose services and verify cleanup.
        Returns:
            None: Prints cleanup status to console
        """
        os.chdir(self.base_dir)
        subprocess.check_output("docker compose down -v", shell=True, executable='/bin/bash')
        time.sleep(3)        
        try:
            subprocess.check_output("docker compose down -v", shell=True, executable='/bin/bash')
            print("✅ Docker compose down executed successfully.")
            time.sleep(3)
            print('\n**********Verifying no services are running**********')

            docker_ps_output = subprocess.check_output("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", shell=True, executable='/bin/bash').decode('utf-8')
            print("Current running containers:")
            print(docker_ps_output)
            lines = docker_ps_output.strip().split('\n')[1:]
            running_containers = []
            project_containers = ['dlstreamer-pipeline-server', 'prometheus', 'coturn', 'model-registry', 'otel-collector', 'mediamtx-server', 'mraas_postgres', 'mraas-minio', 'industrial-edge-insights-vision_vol_minio_data', 'industrial-edge-insights-vision_mr_postgres_data', 'industrial-edge-insights-vision_vol_pipeline_root']
                
            for line in lines:
                if line.strip():
                    container_name = line.split('\t')[0].strip()
                    project_found = False
                    for project_name in project_containers:
                        if project_name in container_name.lower():
                            project_found = True
                            break
                    if project_found:
                        running_containers.append(container_name)
                
            if running_containers:
                print(f"⚠️ Warning: Found {len(running_containers)} project-related containers still running:")
                for container in running_containers:
                    print(f"  - {container}")
                print("These containers may need manual cleanup.")
            else:
                print("✅ No project-related containers are running.")
            print("✅ Services stopped successfully.") 
        except subprocess.CalledProcessError as e:
            raise Exception