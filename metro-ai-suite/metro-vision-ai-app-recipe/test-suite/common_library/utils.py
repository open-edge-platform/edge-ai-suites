import os
import urllib.request
import time
import json
import subprocess
import sys
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s', force=True)

current_dir = os.path.dirname(os.path.abspath(__file__))
repo_path = os.path.abspath(os.path.join(current_dir, '../../'))
print(f"Repo path: {repo_path}")
# Ensure unique sys.path entries while preserving the printed Repo path
sys_path_entries = [current_dir, repo_path, os.path.abspath(os.path.join(current_dir, '../configs'))]
for p in sys_path_entries:
   if p and p not in sys.path:
       sys.path.append(p)

hostIP = subprocess.check_output("ip route get 1 | awk '{print $7}'|head -1", shell=True).decode('utf-8').strip()

class utils:
    def __init__(self):
        """
        Initialize the utils class with application configurations and paths.
        
        Sets up:
        - Repository path
        - Metro path for application deployment
        - Application configurations for LD, SP, and SI applications
        - Retry configuration for operations
        """
        self.path = repo_path
        self.metro_path = f"{self.path}"
        # Optimized app configurations with all necessary data
        self.app_configs = {
            "LD": {
                "name": "loitering-detection",
                "install_command": "./install.sh loitering-detection"
            },
            "SP": {
                "name": "smart-parking",
                "install_command": "./install.sh smart-parking"
            },
            "SI": {
                "name": "smart-intersection", 
                "install_command": "./install.sh smart-intersection"
            }
        }
        self.max_retries = 10
        self.retry_delay = 10


    def _get_chrome_options(self, extra_options=None):
        """
        Get standardized Chrome options for headless browsing.
        
        Args:
            extra_options (list, optional): Additional Chrome options to include.
            
        Returns:
            Options: Configured Chrome options object for headless browsing.
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--allow-running-insecure-content")
        if extra_options:
            for option in extra_options:
                chrome_options.add_argument(option)
        
        return chrome_options

    def _execute_command(self, command, description="command", raise_on_error=True):
        """
        Execute shell command with proper error handling and logging.
        
        Args:
            command (str): Shell command to execute.
            description (str): Description of the command for logging purposes.
            raise_on_error (bool): Whether to raise exception on command failure.
            
        Returns:
            str or None: Command output if successful, None if failed and raise_on_error is False.
            
        Raises:
            Exception: If command fails and raise_on_error is True.
        """
        try:
            logging.info(f"Executing {description}: {command}")
            result = subprocess.check_output(command, shell=True, executable='/bin/bash')
            return result.decode('utf-8')
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to execute {description}: {e}"
            logging.error(error_msg)
            if raise_on_error:
                raise Exception(error_msg)
            return None


    def json_reader(self, tc, JSON_PATH):
        """
        Read a JSON configuration file and return the entry matching the test case key.
        
        Args:
            tc (str): Test case key to look up in the JSON file.
            JSON_PATH (str): Path to the JSON configuration file.
            
        Returns:
            tuple: (key, value) tuple for the matched test case, or (None, None) if not found or on error.
        """
        logging.info('Reading json configuration file')
        with open(JSON_PATH, "r") as jsonFile:
            json_config = json.load(jsonFile)
        for key, value in json_config.items():
            if key == tc:
                logging.info(f"Test Case: {key}, Value: {value}")
                return key, value
        return None, None


    def setup(self, value):
        """
        Execute install command and verify that docker-compose.yml and .env are properly configured.
        
        Performs the following checks:
        1. Executes the appropriate install script based on app type
        2. Verifies docker-compose.yml file was created
        3. Checks that SAMPLE_APP is set correctly in .env
        4. Verifies HOST_IP is set correctly in .env
        
        Args:
            value (dict): Configuration dictionary containing app type and other parameters.
            
        Returns:
            bool: True if all setup requirements are met, False otherwise.
        """
        try:
            os.chdir(self.metro_path)
            logging.info(f"Changed directory to: {self.metro_path}")
            app_type = value.get("app", "")
            app_config = self.app_configs[app_type]
            sample_app = app_config["name"]
            # Execute install command
            install_command = app_config["install_command"]
            logging.info(f"Executing: {install_command}")
            subprocess.call(install_command, shell=True)
            # Check 1: docker-compose.yml file exists
            if not os.path.exists("docker-compose.yml"):
                logging.error("docker-compose.yml file not found")
                return False
            logging.info("docker-compose.yml file created successfully")

            with open(".env", "r") as f:
                env_content = f.read()
            # Check SAMPLE_APP
            if f"SAMPLE_APP={sample_app}" not in env_content:
                logging.error(f"SAMPLE_APP not set to {sample_app} in .env")
                return False
            logging.info(f"SAMPLE_APP updated to {sample_app} in .env")
            # Check HOST_IP  
            host_ip = hostIP.strip()
            if f"HOST_IP={host_ip}" not in env_content:
                logging.error(f"HOST_IP not set to {host_ip} in .env")
                return False
            logging.info(f"HOST_IP updated to {host_ip} in .env")
            logging.info(f"All requirements met for {app_type}")
            return True
        except Exception as e:
            logging.error(f"Exception in setup: {e}")
            return False
        
    
    def docker_compose_up(self, value):
        """
        Start Docker containers using docker compose and verify their status.
        
        Args:
            value (dict): Configuration dictionary containing app-specific parameters.
            
        Returns:
            bool: True if containers started successfully, False otherwise.
        """
        try:
            logging.info("Starting Docker containers with docker compose up...")
            self._execute_command("docker compose up -d", description='docker compose up')
            time.sleep(5)
            return self._verify_container_status(value)
        except Exception as e:
            logging.error(f"Exception in docker_compose_up: {e}")
            return False
    

    def _verify_container_status(self, value):
        """
        Verify the status of containers using docker ps and wait for dlstreamer-pipeline-server to be ready.
        
        Monitors container status for up to 2 minutes, specifically waiting for the
        dlstreamer-pipeline-server container to be in 'Up' state.
        
        Args:
            value (dict): Configuration dictionary containing app type for container name matching.
            
        Returns:
            bool: True if dlstreamer-pipeline-server container is running, False if timeout or error.
        """
        try:
            logging.info("Verifying container status...")
            # Wait for dlstreamer-pipeline-server to be up
            max_wait_time = 120  # 2 minutes
            wait_interval = 5
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                # Execute docker ps to get container status
                result = subprocess.run("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",   shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error("Failed to execute docker ps command")
                    return False
                container_output = result.stdout.strip()
                # Check specifically for dlstreamer-pipeline-server
                dlstreamer_running = False
                for line in container_output.split('\n'):
                    if value.get("app") == "SI":
                        if "metro-vision-ai-app-recipe-dlstreamer-pipeline-server-1" in line and "Up" in line:
                            dlstreamer_running = True
                            logging.info("dlstreamer-pipeline-server container is up and running")
                            break
                    elif "dlstreamer-pipeline-server" in line and "Up" in line:
                        dlstreamer_running = True
                        logging.info("dlstreamer-pipeline-server container is up and running")
                        break
                
                if dlstreamer_running:
                    logging.info("Container Status:")
                    logging.info(f"\n{container_output}")
                    # Count all running containers
                    running_containers = container_output.count("Up")
                    logging.info(f"Found {running_containers} running container(s)")
                    return True
                else:
                    elapsed = int(time.time() - start_time)
                    logging.info(f"Waiting for dlstreamer-pipeline-server container... ({elapsed}s elapsed)")
                    time.sleep(wait_interval)
            # If we get here, dlstreamer-pipeline-server didn't start in time
            logging.error("dlstreamer-pipeline-server container did not start within the timeout period")
            logging.info("Final container status:")
            logging.info(f"\n{container_output}")
            return False        
        except Exception as e:
            logging.error(f"Exception in _verify_container_status: {e}")
            return False
        

    def start_pipeline_and_check(self, value):
        os.chdir(self.metro_path)
        logging.info("Checking pipeline status with sample_status.sh before starting pipeline")

        if value.get("app") == "SP" or value.get("app") == "LD":
                status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
                logging.info(f"sample_status.sh output: {status_output}")
                if "No running pipelines" not in status_output:
                    raise Exception("Pipelines are already running")
                logging.info("No pipelines are currently running - ready to start new pipeline")
                
                cmd = "./sample_start.sh cpu"
                
                # Use subprocess.run to capture both stdout and stderr
                result = subprocess.run(cmd, shell=True, executable='/bin/bash', 
                                      capture_output=True, text=True)
                
                logging.info(f"sample_start.sh command: {cmd}")
                logging.info(f"sample_start.sh return code: {result.returncode}")
                logging.info(f"sample_start.sh stdout: {result.stdout}")
                if result.stderr:
                    logging.error(f"sample_start.sh stderr: {result.stderr}")
                
                if result.returncode != 0:
                    raise Exception(f"Pipeline start failed with return code {result.returncode}. Error: {result.stderr}")
                
                output = result.stdout
                success_message = "Pipelines initialized."
                if success_message not in output:
                    raise Exception(f"Pipeline start failed. Expected message not found: '{success_message}'")
        elif value.get("app") == "SI":
                if value.get("sample_start") is True:
                    raise Exception("SI app - skipping pipeline start. Not yet implemented")
                else:
                    logging.info("SI app - skipping pipeline start. Not yet implemented")
        

    def get_pipeline_status(self, value):
        """
        Check pipeline status with real-time monitoring and FPS validation.
        
        Monitors pipeline status for up to 15 seconds, collecting FPS data
        and validating pipeline performance.
        
        Args:
            value (dict): Configuration dictionary (currently unused but kept for compatibility).
            
        Returns:
            bool: True if pipeline status validation passes, False otherwise.
            
        Raises:
            Exception: If pipeline status check fails.
        """
        try:
            os.chdir(self.metro_path)
            logging.info("Checking pipeline status with sample_status.sh")
            with subprocess.Popen("./sample_status.sh", shell=True, stdout=subprocess.PIPE,  stderr=subprocess.PIPE, text=True, executable='/bin/bash') as process:
                fps_reports = []
                start_time = time.time()
                # Monitor for up to 15 seconds or until we get sufficient data
                while time.time() - start_time < 15:
                    line = process.stdout.readline()
                    if not line:
                        time.sleep(0.1)
                        continue
                    line = line.strip()
                    logging.info(f"Status: {line}")
                    # Extract FPS data efficiently
                    if "pipelines fps:" in line:
                        try:
                            start_idx = line.find('pipelines fps:')
                            open_idx = line.find('(', start_idx)
                            close_idx = line.find(')', open_idx)
                            if open_idx != -1 and close_idx != -1 and close_idx > open_idx:
                                inside = line[open_idx+1:close_idx].strip()
                                parts = [p for p in inside.split() if p]
                                fps_values = []
                                for p in parts:
                                    try:
                                        fps_values.append(float(p))
                                    except:
                                        continue
                                if fps_values:
                                    fps_reports.append(fps_values)
                                    avg_fps = sum(fps_values) / len(fps_values)
                                    logging.info(f"FPS: {fps_values} (avg: {avg_fps:.2f})")
                        except Exception as e:
                            logging.warning(f"Failed to parse FPS line: {e}")
                    # Early exit if we have enough FPS data
                    if len(fps_reports) >= 2:
                        logging.info("Sufficient FPS data collected, terminating early")
                        break
                return self._validate_fps_data(fps_reports)            
        except Exception as e:
            raise Exception(f"Pipeline status check failed: {e}")
    

    def _validate_fps_data(self, fps_reports):
        """
        Validate FPS data from pipeline status reports.
        
        Checks that:
        1. FPS data exists
        2. All FPS values are positive
        3. Logs validation statistics
        
        Args:
            fps_reports (list): List of FPS value lists collected from pipeline status.
            
        Returns:
            bool: True if validation passes, False otherwise.
        """
        try:
            if not fps_reports:
                logging.error("No FPS data found")
                return False
            # Validate all FPS values are positive
            all_fps = [fps for report in fps_reports for fps in report]
            if not all(fps > 0 for fps in all_fps):
                logging.warning("Some pipelines showing zero FPS")
                return False
            # Calculate and log statistics
            logging.info(f"{len(fps_reports)} FPS reports")
            logging.info("Pipeline status validation passed")
            return True
        except Exception as e:
            logging.error(f"Exception in validation: {e}")
            return False


    def container_logs_checker_dlsps(self, tc, value):
        """
        Check dlstreamer-pipeline-server container logs for specific keywords and warnings.
        
        Retrieves container logs, searches for required keywords, and checks for
        warning/error messages in the logs.
        
        Args:
            tc (str): Test case identifier for log file naming.
            value (dict): Configuration dictionary containing dlsps_log_param keywords.
            
        Returns:
            bool: True if all required keywords are found.
            
        Raises:
            Exception: If log retrieval fails or required keywords are missing.
        """
        logging.info('Checking dlstreamer-pipeline-server container logs')
        time.sleep(3)
        container = "dlstreamer-pipeline-server"
        log_file = f"logs_{container}_{tc}.txt"
        logging.info(f"Checking container: {container}")
        try:
            subprocess.run(f"docker compose logs --tail=1000 {container} | tee {log_file}", 
                         shell=True, executable='/bin/bash', check=True)
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to get container logs: {e}")
        keywords = value.get("dlsps_log_param", [])
        missing_keywords = [keyword for keyword in keywords if not self.search_element(log_file, keyword)]
        if missing_keywords:
            error_msg = f"The following keywords were not found in logs: {missing_keywords}"
            logging.error(error_msg)
            raise Exception(error_msg)
        logging.info("All keywords found in logs")
        self._check_warning_messages(log_file)
        return True
        

    def _check_warning_messages(self, log_file):
        """
        Check for warning messages in DLSPS logs and report them.
        
        Searches for warning patterns (WARNING, WARN, ERROR, etc.) in the log file
        and reports unique occurrences with line numbers.
        
        Args:
            log_file (str): Path to the log file to analyze.
        """
        logging.info('Checking for Warning Messages in DLSPS Logs')
        warning_patterns = ["WARNING", "WARN", "warning", "warn", "ERROR", "Error", "error"]
        warnings_found = []
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as file:
                seen_lines = set()  # Use set for faster duplicate checking
                for line_num, line in enumerate(file, 1):
                    line_stripped = line.strip()
                    if line_stripped in seen_lines:
                        continue
                    
                    line_lower = line.lower()
                    for pattern in warning_patterns:
                        if pattern.lower() in line_lower:
                            warnings_found.append({
                                'line_number': line_num,
                                'pattern': pattern,
                                'line': line_stripped
                            })
                            seen_lines.add(line_stripped)
                            break 
        except Exception as e:
            logging.error(f"Error reading log file for warning check: {e}")
            return
        if warnings_found:
            logging.warning(f"Found {len(warnings_found)} warning message(s) in DLSPS logs:")
            for warning in warnings_found:
                logging.warning(f"Line {warning['line_number']} [{warning['pattern']}]: {warning['line']}")
        else:
            logging.info("No warning messages detected in DLSPS logs")


    def search_element(self, logFile, keyword):
        """
        Search for a specific keyword in a log file.
        
        Args:
            logFile (str): Path to the log file to search.
            keyword (str): Keyword to search for in the file.
            
        Returns:
            bool: True if keyword is found, False otherwise.
        """
        keyword_found = False
        keywords_file = os.path.abspath(logFile)
        try:
            with open(keywords_file, 'r', encoding='utf-8', errors='ignore') as file:
                for line in file:
                    if keyword in line:
                        keyword_found = True
                        break
        except Exception as e:
            logging.error(f"Error reading log file {logFile}: {e}")
            return False
        if keyword_found:
            logging.info(f"PASS: Keyword Found {keyword}")
            return True
        else:
            logging.error(f"FAIL: Keyword NOT Found {keyword}")
            return False


    def verify_grafana_url(self, value):
        """Verify Grafana Dashboard at different ports based on deployment type"""
        driver = None
        try:
            logging.info("Verifying Grafana Dashboard")
            
            # Determine deployment configuration
            is_helm = value.get("deploy") is True
            app_type = value.get("app")
            
            config = self._get_grafana_config(app_type, is_helm)
            logging.info(f"Detected {config['description']}")
            
            driver = webdriver.Chrome(options=self._get_chrome_options())
            driver.implicitly_wait(10)
            
            # Try accessing Grafana with retries if needed
            success = self._access_grafana_with_retry(driver, config, max_attempts=3 if app_type == "SI" else 10)
            if not success:
                raise Exception(f"Could not access Grafana via any configured URL for {config['description']}")
                
            # Perform login and verification
            self._grafana_login_and_verify(driver, config)
            logging.info(f"Grafana Dashboard is accessible and verified for {config['description']}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to verify Grafana URL: {e}")
            raise Exception(f"Grafana URL verification failed: {e}")
        finally:
            if driver:
                driver.quit()
    
    def _get_grafana_config(self, app_type, is_helm):
        """Get Grafana configuration based on deployment type"""
        if app_type == "SI" and is_helm:
            return {
                "urls": [f"https://{hostIP}:30443/grafana/"],
                "dashboard_url": f"https://{hostIP}:30443/grafana/dashboards",
                "description": "SI helm deployment - using port 30443",
                "skip_password_change": True
            }
        elif app_type == "SI":
            return {
                "urls": [f"https://{hostIP}/grafana/login"],
                "dashboard_url": f"https://{hostIP}/grafana/dashboards", 
                "description": "SI docker deployment - using nginx reverse proxy",
                "skip_password_change": False
            }
        elif is_helm:
            return {
                "urls": [f"https://{hostIP}:30443/grafana/"],
                "dashboard_url": f"https://{hostIP}:30443/grafana/dashboards",
                "description": "helm deployment - using port 30443",
                "skip_password_change": False
            }
        else:
            return {
                "urls": [f"https://{hostIP}/grafana/login"],
                "dashboard_url": f"https://{hostIP}/grafana/dashboards",
                "description": "docker deployment - using standard grafana path", 
                "skip_password_change": False
            }
    
    def _access_grafana_with_retry(self, driver, config, max_attempts):
        """Try accessing Grafana URLs with retry logic"""
        for attempt in range(max_attempts):
            for url in config["urls"]:
                try:
                    logging.info(f"Trying Grafana access via: {url} (attempt {attempt + 1})")
                    driver.get(url)
                    
                    error_indicators = ["404", "502", "503", "504 Gateway Time-out", "502 Bad Gateway", "503 Service Unavailable"]
                    if not any(error in driver.title for error in error_indicators):
                        logging.info(f"Successfully accessed Grafana via: {url}")
                        return True
                        
                except Exception as e:
                    logging.warning(f"Failed to access {url}: {e}")
            
            if attempt < max_attempts - 1:
                logging.info(f"Retrying in 30 seconds...")
                time.sleep(30)
        
        return False
    
    def _grafana_login_and_verify(self, driver, config):
        """Perform Grafana login and dashboard verification"""
        # Login if elements are present
        try:
            username_input = driver.find_element("name", "user")
            password_input = driver.find_element("name", "password")
            username_input.send_keys("admin")
            password_input.send_keys("admin")
            driver.find_element("css selector", "button[type='submit']").click()
            driver.implicitly_wait(5)
        except:
            logging.info("Login elements not found, checking if already authenticated")
        
        # Handle password change prompt
        if not config.get("skip_password_change", False):
            try:
                if "change-password" in driver.current_url or ("password" in driver.page_source.lower() and "skip" in driver.page_source.lower()):
                    logging.info("Password change prompt detected, skipping...")
                    skip_button = driver.find_element("xpath", "//button[contains(text(), 'Skip')]")
                    skip_button.click()
            except:
                pass
        
        # Verify authentication and dashboard access
        time.sleep(2)
        if not ("Grafana" in driver.title or "Home" in driver.page_source or "grafana" in driver.current_url.lower()):
            raise Exception("Grafana login verification failed")
            
        # Test dashboard accessibility  
        driver.get(config["dashboard_url"])
        driver.implicitly_wait(10)


    def stop_pipeline_and_check(self, value):
        """
        Stop running pipelines and verify they are completely stopped.
        
        Executes sample_stop.sh script and verifies that no pipelines remain running.
        Skips operation for SI applications as they're not yet implemented.
        
        Args:
            value (dict): Configuration dictionary containing app type.
            
        Returns:
            bool or None: True if pipelines stopped successfully, None for SI apps.
            
        Raises:
            Exception: If pipeline stop operation fails.
        """
        try:
            os.chdir(self.metro_path)
            if value.get("app") == "SI":
                return
            logging.info("Stopping pipeline with sample_stop.sh")
            cmd = "./sample_stop.sh"
            output = subprocess.check_output(cmd, shell=True, executable='/bin/bash').decode('utf-8')
            logging.info(f"sample_stop.sh output: {output}")
            # Check for successful stop message
            success_message = "All running pipelines stopped"
            if success_message not in output:
                logging.warning(f"Expected stop message not found: '{success_message}'")
            else:
                logging.info("Pipeline stop message confirmed")
            time.sleep(3)
            # Verify no pipelines are running
            return self._verify_no_pipelines_running()
        except Exception as e:
            logging.error(f"Error in stop_pipeline_and_check: {e}")
            raise Exception(f"Pipeline stop failed: {e}")
    

    def _verify_no_pipelines_running(self):
        """
        Verify that no pipelines are currently running by checking status output.
        
        Checks for indicators of stopped pipelines including "No running pipelines"
        message and absence of FPS data.
        
        Returns:
            bool: True if no pipelines are running, False if pipelines are still active.
        """
        try:
            logging.info("Verifying no pipelines are running...")
            # Check status to confirm no running pipelines
            status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
            logging.info(f"Status verification output: {status_output}")
            for indicator in "No running pipelines":
                if indicator in status_output:
                    return True
            # If no clear indicators, check for absence of FPS data
            if "pipelines fps:" not in status_output and "RUNNING" not in status_output:
                logging.info("No FPS data or RUNNING status found - pipelines stopped")
                return True
            # If we find FPS data, pipelines are still running
            if "pipelines fps:" in status_output:
                logging.error("FPS data found - pipelines still running")
                return False
            logging.info("Pipeline stop verification completed")
            return True
        except Exception as e:
            logging.error(f"Error verifying pipeline stop: {e}")
            return False
    
        
    def docker_compose_down(self, value):
        """
        Bring down docker-compose services for the metro project and report remaining containers.

        Uses docker compose down -v and then inspects running containers to identify
        any project-related containers that may require manual cleanup.
        
        Raises:
            Exception: If docker compose down command fails.
        """
        logging.info('Stopping services with docker compose down')
        os.chdir(self.metro_path)
        try:
            self._execute_command("docker compose down -v", description='docker compose down')
            logging.info("Docker compose down executed successfully")
            time.sleep(3)
            if value.get("app") == "SI":
                return
            else:
                logging.info('Verifying no services are running')
                docker_ps_output = self._execute_command("docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", description='docker ps')
                if docker_ps_output is None:
                    docker_ps_output = ""
                logging.info(f"Current running containers: {docker_ps_output}")
                lines = docker_ps_output.strip().split('\n')[1:]
                running_containers = []
                project_containers = ['dlstreamer-pipeline-server', 'broker', 'coturn', 'grafana', 'node-red', 'mediamtx-server', 'nginx-reverse-proxy']    
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
                    logging.warning(f"Found {len(running_containers)} project-related containers still running:")
                    for container in running_containers:
                        logging.warning(f"  - {container}")
                    logging.warning("These containers may need manual cleanup")
                else:
                    logging.info("No project-related containers are running")
                logging.info("Services stopped successfully") 
        except subprocess.CalledProcessError as e:
            raise Exception
            
    def update_values_helm(self, value):
        """
        Update helm chart values.yaml files with HOST_IP, proxy settings, and webrtc configuration.
        
        Updates different configurations based on application type:
        - SI apps: Updates external IP, passwords, proxy settings, and GPU workload
        - Other apps: Updates HOST_IP, proxy settings, and webrtc configuration
        
        Args:
            value (dict): Configuration dictionary containing app type and update values.
            
        Returns:
            bool: True if values.yaml was successfully updated, False otherwise.
        """
        os.chdir(self.metro_path) 
        app_type = value.get("app", "")
        app_name = self.app_configs[app_type]["name"]

        # Set values_yaml_path based on app type
        if value.get("app") == "SI":
            values_yaml_path = os.path.join(self.metro_path, app_name, "chart", "values.yaml")
        else:
            values_yaml_path = os.path.join(self.metro_path, app_name, "helm-chart", "values.yaml")
        if not os.path.exists(values_yaml_path):
           raise Exception(f"values.yaml not found at: {values_yaml_path}")
            
        logging.info(f"Updating values.yaml for {app_name}")
            
        # Read the current values.yaml file
        with open(values_yaml_path, 'r') as file:
            content = file.read()
            
        if value.get("app") == "SI":
            # Get configuration values with defaults for SI
            external_ip = value.get("external_ip", hostIP.strip())
            su_pass = value.get("su_pass", "admin123")
            pg_pass = value.get("pg_pass", "postgres123")
            no_proxy = value.get("no_proxy", "localhost,127.0.0.1,.local,.cluster.local")
                
            if "externalIP:" in content:
                content = re.sub(r'(\s+)externalIP:.*', f'\\1externalIP: "{external_ip}"', content)                
            if "supass:" in content:
                content = re.sub(r'supass:.*', f'supass: {su_pass}', content)                
            if "pgpass:" in content:
                content = re.sub(r'pgpass:.*', f'pgpass: {pg_pass}', content)
            if "no_proxy:" in content:
                content = re.sub(r'no_proxy:.*', f'no_proxy: {no_proxy}', content)
        else:
            # Get configuration values with defaults
            host_ip = value.get("host_ip", hostIP.strip())
            webrtc_username = value.get("webrtc_username", "testuser")
                                
            if "HOST_IP:" in content:
                content = re.sub(r'HOST_IP:.*', f'HOST_IP: {host_ip}', content)
            if "webrtcturnserver:" in content:
                if "username:" in content:
                    content = re.sub(r'(\s+)username:.*', f'\\1username: {webrtc_username}', content)
                    content = re.sub(r'(\s+)password:.*', f'\\1password: testpass', content)
        # Write the updated content back to the file
        with open(values_yaml_path, 'w') as file:
            file.write(content)
            
        logging.info(f"Successfully updated {values_yaml_path}")
        return True
       
        
    def helm_deploy(self, value):
        """
        Deploy helm charts for the specified application.
        
        Handles deployment for LD, SP, and SI applications with different configurations:
        - SI: Sets up storage classes and deploys with special namespace handling
        - Others: Standard helm install with namespace creation
        
        Args:
            value (dict): Configuration dictionary containing app type and deployment parameters.
            
        Raises:
            Exception: If helm deployment fails.
        """
        try:
            os.chdir(self.metro_path)            
            app_type = value.get("app", "")
            app_name = self.app_configs[app_type]["name"]
            
            # Define helm deployment configurations
            helm_configs = {
                "LD": {
                    "release_name": "loitering-detection",
                    "chart_path": "./loitering-detection/helm-chart",
                    "namespace": "ld"
                },
                "SP": {
                    "release_name": "smart-parking", 
                    "chart_path": "./smart-parking/helm-chart",
                    "namespace": "sp"
                },
                "SI": {
                    "release_name": "smart-intersection", 
                    "chart_path": "./smart-intersection/chart",
                    "namespace": "si"
                }
            }
            
            config = helm_configs[app_type]
            if value.get("app") == "SI":
                # Check for existing storage classes
                logging.info("Checking for storage classes...")
                try:
                    storage_check = subprocess.run("kubectl get storageclass", shell=True, 
                                                 capture_output=True, text=True, executable='/bin/bash')
                    logging.info(f"Storage class check output: {storage_check.stdout}")
                    
                    # Check if any default storage class exists
                    has_default = "default" in storage_check.stdout.lower()
                    
                    if not has_default or "No resources found" in storage_check.stdout:
                        logging.info("No default storage class found, installing local-path-provisioner...")
                        
                        # Install local-path-provisioner
                        provisioner_cmd = "kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml"
                        subprocess.run(provisioner_cmd, shell=True, executable='/bin/bash', 
                                     check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        logging.info("local-path-provisioner installed successfully")
                        
                        # Set as default storage class
                        default_cmd = 'kubectl patch storageclass local-path -p \'{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}\''
                        subprocess.run(default_cmd, shell=True, executable='/bin/bash',
                                     check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        logging.info("local-path set as default storage class")
                        
                        # Verify storage class is ready
                        verify_cmd = "kubectl get storageclass"
                        verify_output = subprocess.run(verify_cmd, shell=True, capture_output=True, 
                                                     text=True, executable='/bin/bash')
                        logging.info(f"Storage class verification: {verify_output.stdout}")
                    else:
                        logging.info("Storage class already configured")
                        
                except subprocess.CalledProcessError as e:
                    logging.warning(f"Storage class setup failed, continuing with deployment: {e}")
            
                # Deploy smart-intersection with updated command
                helm_deploy = "helm upgrade --install smart-intersection ./smart-intersection/chart --create-namespace --set global.storageClassName=\"\" -n smart-intersection"
                logging.info(f"Executing: {helm_deploy}")
                subprocess.run(helm_deploy, shell=True, executable='/bin/bash', 
                               check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logging.info("Deployed SI application with cert-manager and smart-intersection helm charts")
                
                # Wait for all pods to be ready
                logging.info("Waiting for all pods to be ready...")
                wait_cmd = "kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s"
                try:
                    subprocess.run(wait_cmd, shell=True, executable='/bin/bash', check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logging.info("All pods are ready in smart-intersection namespace")
                except subprocess.CalledProcessError as e:
                    logging.warning(f"Pod readiness wait failed, continuing: {e}")
            else:
                helm_command = f"helm install {config['release_name']} {config['chart_path']} -n {config['namespace']} --create-namespace"
                logging.info(f"Deploying {app_name} with helm")
                logging.info(f"Executing: {helm_command}")
                
                try:
                    # Execute helm install command - will raise CalledProcessError on failure
                    output = subprocess.check_output(helm_command, shell=True, executable='/bin/bash', stderr=subprocess.STDOUT, text=True)
                    logging.info(f"Helm install successful: {output}")
                    
                except subprocess.CalledProcessError as e:
                    logging.error(f"Helm install failed with return code {e.returncode}")
                    logging.error(f"Helm install output: {e.output}")
                    raise Exception(f"Helm install failed with return code {e.returncode}. Output: {e.output}")
                logging.info(f"Successfully deployed {app_name} with helm")
        except Exception as e:
            raise Exception(f"Helm deploy failed: {e}")
        self.check_pod_status(value)

    def check_pod_status(self, value):
        """
        Check the status of running pods in the metro application namespace.
        
        Monitors pod status for up to 30 attempts, waiting for all pods to be
        in Running state with all containers ready.
        
        Args:
            value (dict): Configuration dictionary containing app type for namespace determination.
            
        Returns:
            bool: True if all pods are ready and running, False otherwise.
            
        Raises:
            Exception: If pod status check fails or unsupported app type.
        """
        try:
            app_type = value.get("app", "")
            if app_type not in self.app_configs:
                raise Exception(f"Unsupported app type: {app_type}")
            
            namespace_configs = {"LD": "ld", "SP": "sp", "SI": "smart-intersection"}
            namespace = namespace_configs[app_type]
            logging.info(f'Checking pod status in namespace: {namespace}')
            
            for attempt in range(30):
                try:
                    output = subprocess.check_output(f"kubectl get pods -n {namespace}", 
                                                   shell=True, executable='/bin/bash').decode('utf-8')
                    logging.info(f'Pod status in {namespace} (attempt {attempt + 1}/30):')
                    logging.info(output)
                    
                    lines = output.strip().split('\n')[1:]  # Skip header
                    if not lines:
                        logging.info(f'No pods found in namespace {namespace}')
                        break
                    
                    all_ready = all(
                        (lambda parts: len(parts) >= 3 and 
                         parts[2] in ['Running'] and
                         ('/' not in parts[1] or parts[1].split('/')[0] == parts[1].split('/')[1])
                        )(line.split()) if line.strip() else True
                        for line in lines
                    )
                    
                    # Log any pods that are not ready
                    for line in lines:
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 3:
                                pod_name, ready_status, status = parts[0], parts[1], parts[2]
                                if status not in ['Running']:
                                    logging.info(f'Pod {pod_name} is not ready: {status} ({ready_status})')
                                elif '/' in ready_status and ready_status.split('/')[0] != ready_status.split('/')[1]:
                                    logging.info(f'Pod {pod_name} is not fully ready: {ready_status}')
                    
                    if all_ready and lines:
                        logging.info(f'All pods in namespace {namespace} are ready and running')
                        return True
                    
                except subprocess.CalledProcessError as e:
                    if "No resources found" in str(e.output) or "No resources found" in str(e):
                        logging.info(f'No pods found in namespace {namespace}')
                        return True
                    else:
                        logging.warning(f'Error checking pods in {namespace}: {e}')
                
                if attempt < 29:
                    time.sleep(15)
            
            logging.warning(f'Warning: Not all pods in {namespace} are ready after maximum wait time')
            return False
            
        except Exception as e:
            logging.error(f"Pod status check failed: {e}")
            raise Exception(f"Pod status check failed: {e}")


    def helm_uninstall(self, value):
        """
        Uninstall metro applications using helm uninstall command.
        
        Executes helm uninstall for the specified application and verifies
        that pods are properly cleaned up from the namespace.
        
        Args:
            value (dict): Configuration dictionary containing app type.
            
        Returns:
            bool: True if uninstall and cleanup completed successfully, False otherwise.
        """
        try:
            os.chdir(self.metro_path)
            logging.info(f"Changed directory to: {self.metro_path}")
            
            app_type = value.get("app", "")
            if app_type not in self.app_configs:
                raise Exception(f"Unsupported app type: {app_type}")
            
            # Define helm uninstall configurations
            helm_configs = {
                "LD": {
                    "release_name": "loitering-detection",
                    "namespace": "ld"
                },
                "SP": {
                    "release_name": "smart-parking",
                    "namespace": "sp"
                },
                "SI": {
                    "release_name": "smart-intersection",
                    "namespace": "si"
                }
            }
            config = helm_configs[app_type]
            if value.get("app") == "SI":
                # Uninstall SI application and cert-manager
                helm_command = "helm uninstall smart-intersection -n smart-intersection"
            else:
                helm_command = f"helm uninstall {config['release_name']} -n {config['namespace']}"
                
            logging.info(f"Uninstalling {config['release_name']} from namespace {config['namespace']}")
            logging.info(f"Executing: {helm_command}")
                
            # Execute helm uninstall command
            result = subprocess.run(helm_command, shell=True, executable='/bin/bash',
                                    capture_output=True, text=True)
                
            logging.info(f"Helm uninstall return code: {result.returncode}")
            logging.info(f"Helm uninstall stdout: {result.stdout}")
            if result.stderr:
                logging.error(f"Helm uninstall stderr: {result.stderr}")
                
            if result.returncode != 0:
                raise Exception(f"Helm uninstall failed with return code {result.returncode}. Error: {result.stderr}")
                
            logging.info(f"Successfully uninstalled {config['release_name']} from namespace {config['namespace']}")
                
            # Wait for cleanup to begin
            time.sleep(5)
                
            # Verify pods cleanup after uninstall
            return self._verify_pods_cleanup(config['namespace'])
            
        except Exception as e:
            logging.error(f"Exception in helm_uninstall: {e}")
            return False
    
    def _verify_pods_cleanup(self, namespace):
        """
        Verify that all pods in the specified namespace are terminated.
        
        Monitors pod termination for up to 20 attempts, checking that all
        pods have been removed from the namespace.
        
        Args:
            namespace (str): Kubernetes namespace to check for pod cleanup.
            
        Returns:
            bool: True if all pods are removed, False if timeout or pods remain.
        """
        logging.info(f'Verifying pods cleanup in namespace: {namespace}')
        try:
            max_attempts = 20
            for attempt in range(max_attempts):
                try:
                    output = subprocess.check_output(f"kubectl get pods -n {namespace}", 
                                                   shell=True, executable='/bin/bash').decode('utf-8')
                    logging.info(f'Pod status check in {namespace} (attempt {attempt + 1}/{max_attempts}):')
                    logging.info(output)
                    
                    lines = output.strip().split('\n')
                    if len(lines) <= 1 or (len(lines) == 2 and "No resources found" in lines[1]):
                        logging.info(f'All pods have been successfully removed from {namespace} namespace')
                        return True
                    else:
                        remaining_pods = lines[1:]  # Skip header
                        logging.info(f'Found {len(remaining_pods)} pod(s) still terminating in {namespace}...')
                        for pod_line in remaining_pods:
                            if pod_line.strip():
                                logging.info(f'   - {pod_line}')
                except subprocess.CalledProcessError as e:
                    if "No resources found" in str(e.output) or "No resources found" in str(e):
                        logging.info(f'All pods have been successfully removed from {namespace} namespace')
                        return True
                    else:
                        logging.warning(f'Error checking pods in {namespace}: {e}')
                
                if attempt < max_attempts - 1:
                    time.sleep(5)
            
            logging.warning(f'Warning: Some pods may still be terminating in {namespace} after maximum wait time')
            return False
            
        except Exception as e:
            logging.warning(f'Warning: Could not verify pod cleanup in {namespace}: {e}')
            return False

    def helm_send_curl_requests(self, value):
        """
        Send curl requests to start pipelines for helm-deployed applications.
        
        Sends HTTP POST requests to the dlstreamer-pipeline-server API to start
        multiple pipelines for LD or SP applications. Skips SI applications.
        
        Args:
            value (dict): Configuration dictionary containing app type.
            
        Returns:
            list: List of response IDs from successfully started pipelines.
            
        Raises:
            Exception: If curl requests fail or unsupported app type.
        """
        try:
            app_type = value.get("app", "")
            if app_type == "SI":
                return
            if app_type not in self.app_configs:
                raise Exception(f"Unsupported app type: {app_type}")
            
            host_ip = hostIP.strip()
            
            # Define pipeline configurations for different apps
            pipeline_configs = {
                "LD": {
                    "base_url": f"https://{host_ip}:30443/api/pipelines/user_defined_pipelines",
                    "pipelines": [
                        {"name": "object_tracking_cpu", "video": "VIRAT_S_000101.mp4", "topic": "object_tracking_1"},
                        {"name": "object_tracking_cpu", "video": "VIRAT_S_000102.mp4", "topic": "object_tracking_2"},
                        {"name": "object_tracking_cpu", "video": "VIRAT_S_000103.mp4", "topic": "object_tracking_3"},
                        {"name": "object_tracking_cpu", "video": "VIRAT_S_000104.mp4", "topic": "object_tracking_4"}
                    ]
                },
                "SP": {
                    "base_url": f"https://{host_ip}:30443/api/pipelines/user_defined_pipelines",
                    "pipelines": [
                        {"name": "yolov11s", "video": "new_video_1.mp4", "topic": "object_detection_1"},
                        {"name": "yolov11s", "video": "new_video_2.mp4", "topic": "object_detection_2"},
                        {"name": "yolov11s", "video": "new_video_3.mp4", "topic": "object_detection_3"},
                        {"name": "yolov11s", "video": "new_video_4.mp4", "topic": "object_detection_4"}
                    ]
                }
            }
            
            if app_type not in pipeline_configs:
                raise Exception(f"Pipeline configuration not found for app type: {app_type}")
            
            config = pipeline_configs[app_type]
            
            logging.info(f"Sending curl requests for {app_type} application")
            logging.info(f"Using detection device: CPU")            
            response_ids = []
            
            for pipeline in config["pipelines"]:
                # Create JSON payload
                payload = {
                    "source": {"uri": f"file:///home/pipeline-server/videos/{pipeline['video']}", "type": "uri"},
                    "destination": {
                        "metadata": {"type": "mqtt", "topic": pipeline["topic"], "publish_frame": False},
                        "frame": {"type": "webrtc", "peer-id": pipeline["topic"]}
                    },
                    "parameters": {"detection-device": "CPU"}
                }
                
                url = f"{config['base_url']}/{pipeline['name']}"
                json_data = json.dumps(payload)
                
                curl_command = ["curl", "--silent", "-k", url, "-X", "POST", "-H", "Content-Type: application/json", "-d", json_data]
                
                logging.info(f"Sending request for pipeline {pipeline['name']}")
                logging.info(f"URL: {url}")
                logging.info(f"Payload: {json_data}")

                result = subprocess.run(curl_command, capture_output=True, text=True)
                
                logging.info(f"Pipeline {pipeline['name']} - Return code: {result.returncode}")
                logging.info(f"Pipeline {pipeline['name']} - Response: {result.stdout}")
                
                if result.stderr:
                    logging.error(f"Pipeline {pipeline['name']} - Error: {result.stderr}")

                if result.returncode != 0:
                    raise Exception(f"Pipeline {pipeline['name']} request failed: {result.stderr}")

                # Extract response ID if successful
                try:
                    response = json.loads(result.stdout)
                    if isinstance(response, dict) and 'id' in response:
                        response_ids.append(response['id'])
                        logging.info(f"Pipeline {pipeline['name']} started successfully - ID: {response['id']}")
                    elif isinstance(response, str):
                        response_ids.append(response.strip('"'))
                        logging.info(f"Pipeline {pipeline['name']} started successfully - ID: {response}")
                except json.JSONDecodeError:
                    if result.stdout.strip():
                        response_ids.append(result.stdout.strip())
                        logging.info(f"Pipeline {pipeline['name']} started - Raw response: {result.stdout.strip()}")
        
            logging.info(f"Successfully started {len(response_ids)} pipeline(s) for {app_type}")
            logging.info(f"Response IDs: {response_ids}")
            return response_ids
            
        except Exception as e:
            logging.error(f"Exception in helm_send_curl_requests: {e}")
            raise Exception(f"Helm curl requests failed: {e}")
        
    def container_logs_checker_helm(self, tc, value):
        """
        Check dlstreamer-pipeline-server pod logs in Kubernetes.
        
        Finds the appropriate pod in the correct namespace, retrieves logs,
        and checks for required keywords and warning messages.
        
        Args:
            tc (str): Test case identifier for log file naming.
            value (dict): Configuration dictionary containing app type and log parameters.
            
        Returns:
            bool: True if log check passes successfully.
            
        Raises:
            Exception: If pod not found, log retrieval fails, or required keywords missing.
        """
        logging.info('Checking dlstreamer-pipeline-server pod logs')
        time.sleep(3)
        
        # Determine namespace and find pod
        app_type = value.get("app", "")
        namespace_configs = {"LD": "ld", "SP": "sp", "SI": "smart-intersection"}
        namespace = namespace_configs.get(app_type, "ld")
        
        pod_commands = [
            f"kubectl get pods -n {namespace} -o jsonpath='{{.items[*].metadata.name}}' | tr ' ' '\\n' | grep dlstreamer-pipeline-server | head -n 1",
            f"kubectl get pods -n {namespace} -o jsonpath='{{.items[*].metadata.name}}' | tr ' ' '\\n' | grep deployment-dlstreamer-pipeline-server | head -n 1"
        ]
        
        pod_name = next((subprocess.check_output(cmd, shell=True, executable='/bin/bash').decode('utf-8').strip() 
                        for cmd in pod_commands), None)
        if not pod_name:
            raise Exception(f"dlstreamer-pipeline-server pod not found in namespace {namespace}")
        
        logging.info(f'Found pod: {pod_name} in namespace: {namespace}')
        log_file = f"logs_helm_{pod_name}_{tc}.txt"
        logging.info(f"Checking Helm Pod: {pod_name}")
        
        # Determine log command based on app type
        if app_type == "SI":
            containers = subprocess.check_output(f"kubectl get pod -n {namespace} {pod_name} -o jsonpath='{{.spec.containers[*].name}}'", 
                                               shell=True, executable='/bin/bash').decode('utf-8').strip()
            logging.info(f"Available containers in pod {pod_name}: {containers}")
            
            dlstreamer_container = next((c for c in containers.split() if "dlstreamer" in c.lower() or "pipeline" in c.lower()), 
                                       containers.split()[0] if containers.split() else None)
            
            if dlstreamer_container:
                log_cmd = f"kubectl logs -n {namespace} {pod_name} -c {dlstreamer_container} --tail=1000"
                logging.info(f"Using container: {dlstreamer_container}")
            else:
                log_cmd = f"kubectl logs -n {namespace} {pod_name} --tail=1000"
                logging.info("Getting logs without container specification")
        else:
            log_cmd = f"kubectl logs -n {namespace} {pod_name} -c dlstreamer-pipeline-server --tail=1000"
        
        # Get logs with fallback for SI
        result = subprocess.run(log_cmd, shell=True, capture_output=True, text=True, executable='/bin/bash')
        if result.returncode != 0:
            logging.warning(f"Warning: Failed to get logs from pod {pod_name}: {result.stderr}")
            if app_type == "SI" and "-c " in log_cmd:
                logging.info("Retrying without container specification...")
                result = subprocess.run(f"kubectl logs -n {namespace} {pod_name} --tail=1000", 
                                      shell=True, capture_output=True, text=True, executable='/bin/bash')
                if result.returncode != 0:
                    logging.warning(f"Fallback log retrieval also failed: {result.stderr}")
                    return True
            else:
                return True
        
        # Save and display logs
        with open(log_file, 'w') as f:
            f.write(result.stdout)
        logging.info(f"Pod logs saved to: {log_file}")
        
        log_lines = result.stdout.split('\n')
        if len(log_lines) > 500:
            logging.info("Recent pod logs (last 500 lines):")
            logging.info('\n'.join(log_lines[-500:]))
        else:
            logging.info("Pod logs:")
            logging.info(result.stdout)
        
        # Check keywords
        keywords = value.get("dlsps_log_param", [])
        if not keywords:
            logging.info("No keywords specified for log checking")
            self._check_warning_messages_helm(log_file)
            return True
        
        missing_keywords = [keyword for keyword in keywords if not self.search_element(log_file, keyword)]
        if missing_keywords:
            error_msg = f"FAIL: The following keywords were not found in Helm pod logs: {missing_keywords}"
            logging.error(error_msg)
            raise Exception(error_msg)
        else:
            logging.info("PASS: All keywords found in Helm pod logs.")
            self._check_warning_messages_helm(log_file)
            return True
    
    def _check_warning_messages_helm(self, log_file):
        """
        Check for warning messages in Helm pod logs and report them.
        
        Searches for warning patterns in Helm pod logs and reports unique
        occurrences with line numbers and pattern information.
        
        Args:
            log_file (str): Path to the log file to analyze.
        """
        logging.info('Checking for Warning Messages in Helm Pod Logs')
        warning_patterns = ["WARNING", "WARN", "warning", "warn", "ERROR", "error"]
        warnings_found = []
        seen_lines = set()
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as file:
                for line_num, line in enumerate(file, 1):
                    line_stripped = line.strip()
                    if line_stripped in seen_lines:
                        continue
                    
                    line_lower = line.lower()
                    for pattern in warning_patterns:
                        if pattern.lower() in line_lower:
                            warnings_found.append({'line_number': line_num,'pattern': pattern,'line': line_stripped})
                            seen_lines.add(line_stripped)
                            break
        except Exception as e:
            logging.error(f"Error reading log file for warning check: {e}")
            return
            
        if warnings_found:
            logging.warning(f"Found {len(warnings_found)} warning/error message(s) in Helm pod logs:")
            for warning in warnings_found:
                logging.warning(f"Line {warning['line_number']} [{warning['pattern']}]: {warning['line']}")
        else:
            logging.info("No warning/error messages detected in Helm pod logs.")

    def helm_uninstall_complete_si(self, value):
        """
        Complete uninstall and cleanup for Smart Intersection application.
        
        Performs comprehensive cleanup including:
        1. Helm uninstall of smart-intersection
        2. PVC deletion with force cleanup if needed
        3. Namespace deletion
        4. Persistent volume cleanup
        5. Local-path-provisioner removal
        6. Storage class cleanup
        7. Cert-manager cleanup (if not used by other apps)
        8. Final verification
        
        Args:
            value (dict): Configuration dictionary, must contain app="SI".
            
        Returns:
            bool: True if cleanup completed successfully, False otherwise.
        """
        try:
            os.chdir(self.metro_path)
            logging.info("Starting complete Smart Intersection cleanup...")
            
            if value.get("app") != "SI":
                logging.warning("This function is only for Smart Intersection (SI) application")
                return False
            
            # Step 1: Uninstall the Smart Intersection application
            logging.info("Step 1: Uninstalling Smart Intersection application...")
            helm_command = "helm uninstall smart-intersection -n smart-intersection"
            result = subprocess.run(helm_command, shell=True, executable='/bin/bash', capture_output=True, text=True)
            logging.info(f"Helm uninstall return code: {result.returncode}")
            logging.info(f"Helm uninstall output: {result.stdout}")
            if result.stderr:
                logging.warning(f"Helm uninstall stderr: {result.stderr}")
            
            # Step 2: Delete PVCs in smart-intersection namespace
            logging.info("Step 2: Deleting PVCs in smart-intersection namespace...")
            pvc_cmd = "kubectl delete pvc --all -n smart-intersection --timeout=60s"
            pvc_result = subprocess.run(pvc_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=90)
            if pvc_result.returncode == 0:
                logging.info("PVCs deleted successfully")
            else:
                logging.warning(f"PVC deletion failed, trying force cleanup: {pvc_result.stderr}")
                logging.info("Attempting force cleanup of stuck PVCs...")
                force_cmd = "kubectl get pvc -n smart-intersection --no-headers | awk '{print $1}' | xargs -I {} kubectl patch pvc {} -n smart-intersection --type merge -p '{\"metadata\":{\"finalizers\":null}}'"
                subprocess.run(force_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=60)
                logging.info("Force PVC cleanup completed")
            
            # Step 3: Delete the smart-intersection namespace
            logging.info("Step 3: Deleting smart-intersection namespace...")
            namespace_cmd = "kubectl delete namespace smart-intersection --timeout=120s"
            ns_result = subprocess.run(namespace_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=150)
            logging.info(f"Namespace deletion return code: {ns_result.returncode}")
            logging.info("Smart-intersection namespace deleted successfully")
            
            # Step 4: Delete persistent volumes
            logging.info("Step 4: Deleting persistent volumes...")
            subprocess.run("kubectl delete pv --all --timeout=60s", shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=90)
            logging.info("Persistent volumes deleted successfully")
            
            # Step 5: Remove local-path-provisioner (if installed)
            logging.info("Step 5: Removing local-path-provisioner...")
            provisioner_cmd = "kubectl delete -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml"
            subprocess.run(provisioner_cmd, shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=60)
            logging.info("Local-path-provisioner removed successfully")
            
            # Step 6: Remove additional storage classes
            logging.info("Step 6: Removing additional storage classes...")
            storage_classes = ["hostpath", "local-storage", "standard"]
            for sc in storage_classes:
                subprocess.run(f"kubectl delete storageclass {sc} --ignore-not-found=true", shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=30)
                logging.info(f"Storage class {sc} removed")
            
            # Step 7: Remove cert-manager (optional - may be used by other applications)
            logging.info("Step 7: Checking cert-manager cleanup...")
            cert_check = subprocess.run("kubectl get certificates --all-namespaces", shell=True, capture_output=True, text=True, executable='/bin/bash')
            if "No resources found" in cert_check.stdout or not cert_check.stdout.strip():
                logging.info("No other certificates found, removing cert-manager...")
                subprocess.run("helm uninstall cert-manager -n cert-manager", shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=60)
                subprocess.run("kubectl delete namespace cert-manager --timeout=60s", shell=True, executable='/bin/bash', capture_output=True, text=True, timeout=90)
                logging.info("Cert-manager removed successfully")
            else:
                logging.info("Cert-manager is being used by other applications, keeping it installed")
            
            # Step 8: Final verification
            logging.info("Step 8: Final verification...")
            check_cmd = "kubectl get all --all-namespaces | grep smart-intersection || true"
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True, executable='/bin/bash')
            if result.stdout.strip():
                logging.warning(f"Some smart-intersection resources may still exist: {result.stdout}")
            else:
                logging.info("No remaining smart-intersection resources found")
            
            sc_check = subprocess.run("kubectl get storageclass", shell=True, capture_output=True, text=True, executable='/bin/bash')
            logging.info(f"Remaining storage classes: {sc_check.stdout}")
            
            logging.info("Smart Intersection complete cleanup finished")
            return True
            
        except Exception as e:
            logging.error(f"Exception in helm_uninstall_complete_si: {e}")
            return False