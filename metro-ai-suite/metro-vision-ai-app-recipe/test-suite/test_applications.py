import os
import subprocess
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

USECASES = [
    "smart-parking",
    "smart-intersection",
    "loitering-detection"
]

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))


def run_command(command, cwd=None):
    result = subprocess.run(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.returncode, result.stdout.decode(), result.stderr.decode()


def start_application(usecase):
    usecase_path = os.path.join(BASE_PATH, usecase)
    # Step 1: ./install.sh <usecase> (with TTY workaround)
    install_script = os.path.join(usecase_path, 'install.sh')
    code, out, err = run_command(f"script -q -c 'bash {install_script} {usecase}' /dev/null", cwd=usecase_path)
    assert code == 0, f"Install failed for {usecase}: {err}"
    # Step 2: docker compose up -d
    code, out, err = run_command("docker compose up -d", cwd=usecase_path)
    assert code == 0, f"Docker up failed for {usecase}: {err}"
    # Step 3: ./sample_start.sh
    start_script = os.path.join(usecase_path, 'sample_start.sh')
    code, out, err = run_command(f"bash {start_script}", cwd=usecase_path)
    assert code == 0, f"Sample start failed for {usecase}: {err}"
    return usecase_path


def stop_application(usecase_path):
    # Step 4: docker compose down
    code, out, err = run_command("docker compose down", cwd=usecase_path)
    assert code == 0, f"Docker down failed: {err}"


def _test_usecase(usecase):
    usecase_path = start_application(usecase)
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=chrome_options)
    try:
        # 1. Check if main app is up
        driver.get("http://localhost:3000")
        assert "404" not in driver.title, f"App not running for {usecase}"

        # 2. Check if you can login to Grafana dashboard (on port 3000)
        driver.get("http://localhost:3000/login")
        username_input = driver.find_element("name", "user")
        password_input = driver.find_element("name", "password")
        username_input.send_keys("admin")
        password_input.send_keys("admin")
        driver.find_element("css selector", "button[type='submit']").click()
        driver.implicitly_wait(5)
        assert "Grafana" in driver.title or "Home" in driver.page_source, "Grafana login failed"

        # 3. Check if Grafana dashboard is showing data (on port 3000)
        driver.get("http://localhost:3000/dashboards")
        driver.implicitly_wait(5)
        assert "No data" not in driver.page_source, "Grafana dashboard is not showing data"

        # 4. Check health of all docker services
        import subprocess, json
        result = subprocess.run(["docker", "compose", "ps", "--format", "json"], cwd=usecase_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert result.returncode == 0, f"docker compose ps failed: {result.stderr.decode()}"
        services = json.loads(result.stdout.decode())
        unhealthy_services = [s['Name'] for s in services if s.get('Health', '').lower() not in ('healthy', '')]
        assert not unhealthy_services, f"Unhealthy services: {unhealthy_services}"
    finally:
        driver.quit()
        stop_application(usecase_path)


@pytest.mark.parametrize("usecase", USECASES)
def test_all_usecases(usecase):
    _test_usecase(usecase)
