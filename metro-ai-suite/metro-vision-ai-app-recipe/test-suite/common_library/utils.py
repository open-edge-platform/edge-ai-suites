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
        """Get standardized Chrome options for headless browsing"""
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
        """Execute shell command with proper error handling"""
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
        """Read a JSON configuration file and return the entry matching the test case key.
        Args:
            tc (str): Test case key to look up in the JSON file.
            JSON_PATH (str): Path to the JSON configuration file.
        Returns:
            (key, value) tuple for the matched test case, or (None, None) if not found or on error.
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
        """Execute install command and check if docker-compose.yml got created and host_ip/sample_app updated in .env"""
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
        """Execute docker compose up and verify container status"""
        try:
            logging.info("Starting Docker containers with docker compose up...")
            self._execute_command("docker compose up -d", description='docker compose up')
            time.sleep(5)
            return self._verify_container_status(value)
        except Exception as e:
            logging.error(f"Exception in docker_compose_up: {e}")
            return False
    

    def _verify_container_status(self, value):
        """Verify the status of containers using docker ps and wait for dlstreamer-pipeline-server"""
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
        """Start the sample pipeline(s) for the selected app and validate startup.
        Compact implementation that preserves existing logging messages and behavior for SP, LD, and SI.
        """
        os.chdir(self.metro_path)
        logging.info("Checking pipeline status with sample_status.sh before starting pipeline")

        app = value.get("app")
        if app not in ("SP", "LD"):
            if app == "SI":
                logging.info("SI app - skipping pipeline start. Not yet implemented")
                return
            logging.info("Unsupported app type for pipeline start")
            return
        # Check current status
        status_output = subprocess.check_output("./sample_status.sh", shell=True, executable='/bin/bash').decode('utf-8')
        logging.info(f"sample_status.sh output: {status_output}")
        if "No running pipelines" not in status_output:
            raise Exception("Pipelines are already running")
        logging.info("No pipelines are currently running - ready to start new pipeline")
        # Start pipelines
        cmd = "./sample_start.sh"
        result = subprocess.run(cmd, shell=True, executable='/bin/bash', capture_output=True, text=True)
        output = result.stdout
        if app == "SP":
            success_message = "Pipelines initialized."
            if success_message not in output:
                raise Exception(f"Pipeline start failed. Expected message not found: '{success_message}'")
            return None
        # app == "LD": extract response IDs
        response_ids = []
        for line in output.split('\n'):
            id_matches = re.findall(r'[0-9a-f]{32}', line)
            for match in id_matches:
                if match not in response_ids:
                    response_ids.append(match)
        if response_ids:
            logging.info(f"Found {len(response_ids)} response IDs for LD: {response_ids}")
            return response_ids
        logging.error("No response IDs found in LD pipeline start output")
        raise Exception("LD pipeline start did not return any response IDs")
        

    def get_pipeline_status(self, value):
        """Optimized pipeline status check with real-time monitoring"""
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
        """Simplified validation - only check FPS data"""
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
        """Optimized container logs checking with better error handling"""
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
        """Check for warning messages in DLSPS logs and report them."""
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
        """Optimized keyword search in log file"""
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
            logging.info(f"Verifying Grafana Dashboard")
            chrome_options = self._get_chrome_options()
            driver = webdriver.Chrome(options=chrome_options)
            driver.implicitly_wait(10)
            if value.get("app") == "SI":
                login_url = f"http://{hostIP}:3000/login"
                dashboard_url = f"http://{hostIP}:3000/dashboards"
                post_success_log = "Grafana Dashboard is accessible and showing data for SI"
            else:
                logging.info("Detected docker deployment - using standard grafana path")
                login_url = f"https://{hostIP}/grafana/login"
                dashboard_url = f"https://{hostIP}/grafana/dashboards"
                post_success_log = "Grafana Dashboard is accessible and showing data"

            # Navigate to login page and ensure it's accessible
            driver.get(login_url)
            assert "404" not in driver.title, "Grafana login page not accessible"
            # Perform login
            username_input = driver.find_element("name", "user")
            password_input = driver.find_element("name", "password")
            username_input.send_keys("admin")
            password_input.send_keys("admin")
            driver.find_element("css selector", "button[type='submit']").click()
            driver.implicitly_wait(5)

            # Handle docker password change prompt if it appears
            if value.get("app") != "SI":
                try:
                    if "change-password" in driver.current_url or "password" in driver.page_source.lower():
                        logging.info("Password change prompt detected, skipping...")
                        try:
                            skip_button = driver.find_element("xpath", "//button[contains(text(), 'Skip')]")
                            skip_button.click()
                        except:
                            driver.get(login_url.replace('/login', ''))
                except:
                    pass

            # Verify login success and dashboard accessibility
            assert "Grafana" in driver.title or "Home" in driver.page_source, "Grafana login failed"
            driver.get(dashboard_url)
            driver.implicitly_wait(10)
            assert "No data" not in driver.page_source, "Grafana dashboard is not showing data"
            logging.info(post_success_log)
            return True
        except Exception as e:
            logging.error(f"Failed to verify Grafana URL: {e}")
            raise Exception(f"Grafana URL verification failed: {e}")
        finally:
            if driver:
                driver.quit()


    def stop_pipeline_and_check(self, value):
        """Stop pipeline and verify all pipelines are stopped"""
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
        """Verify that no pipelines are currently running"""
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
    
        
    def docker_compose_down(self):
        """Bring down docker-compose services for the metro project and report remaining containers.

        Uses docker compose down -v and then inspects running containers to identify
        any project-related containers that may require manual cleanup.
        """
        logging.info('Stopping services with docker compose down')
        os.chdir(self.metro_path)
        try:
            self._execute_command("docker compose down -v", description='docker compose down')
            logging.info("Docker compose down executed successfully")
            time.sleep(3)
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