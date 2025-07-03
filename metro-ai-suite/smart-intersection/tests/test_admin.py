import pytest
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.ui_utils import waiter, driver
from tests.utils.utils import check_components_access
from .conftest import SMART_INTERSECTION_URL, SMART_INTERSECTION_PASSWORD, SMART_INTERSECTION_USERNAME

logger = logging.getLogger(__name__)

@pytest.mark.zephyr_id("NEX-T9389")
def test_login(waiter):
    """Test that the admin login functionality works correctly."""
    waiter.perform_login(
        SMART_INTERSECTION_URL,
        By.ID, "username",
        By.ID, "password",
        By.ID, "login-submit",
        SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD
    )

    # Verify that the expected elements are present on the page
    nav_scenes = waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "nav-scenes")),
        error_message='"nav-scenes" element not found on the page'
    )

    assert nav_scenes

@pytest.mark.zephyr_id("NEX-T9390")
def test_logout(waiter):
    """Test that the admin logout functionality works correctly."""
    waiter.perform_login(
        SMART_INTERSECTION_URL,
        By.ID, "username",
        By.ID, "password",
        By.ID, "login-submit",
        SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD
    )

    # Verify that the expected elements are present on the page
    nav_scenes = waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "nav-scenes")),
        error_message='"nav-scenes" element not found on the page'
    )
    nav_cameras = waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "nav-cameras")),
        error_message='"nav-cameras" element not found on the page'
    )
    assert nav_scenes and nav_cameras

    # Perform logout action
    logout_link = waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "nav-sign-out")),
        error_message='"nav-sign-out" element not found on the page'
    )
    logout_link.click()

    # Wait for the 'username' input to be present
    waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "username")),
        error_message='"username" input field not found within 10 seconds'
    )

@pytest.mark.zephyr_id("NEX-T9388")
def test_change_password(waiter):
    """Test that the admin can change the password successfully."""
    waiter.perform_login(
        SMART_INTERSECTION_URL,
        By.ID, "username",
        By.ID, "password",
        By.ID, "login-submit",
        SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD
    )

    # Navigate to Password change page
    waiter.driver.get(SMART_INTERSECTION_URL + "/admin/password_change")

    # Wait for the password fields to be present
    waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "id_old_password")),
        error_message='Password fields not found within 10 seconds'
    )

    old_password_input = waiter.driver.find_element(By.ID, "id_old_password")
    new_password1_input = waiter.driver.find_element(By.ID, "id_new_password1")
    new_password2_input = waiter.driver.find_element(By.ID, "id_new_password2")

    old_password_input.send_keys(SMART_INTERSECTION_PASSWORD)
    new_password1_input.send_keys(SMART_INTERSECTION_PASSWORD)
    new_password2_input.send_keys(SMART_INTERSECTION_PASSWORD)

    # Submit the password change
    submit_button = waiter.driver.find_element(By.XPATH, "//input[@type='submit' and @value='Change my password']")
    submit_button.click()

    # Wait for the success message to be present
    waiter.wait_and_assert(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Password change successful"),
        error_message='"Password change successful" message not found within 10 seconds'
    )

@pytest.mark.zephyr_id("NEX-T9374")
def test_web_option_availability(waiter):
  """Test that the web option is available in the admin interface."""
  waiter.perform_login(
    SMART_INTERSECTION_URL,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD
  )

  # Find all links in the navbar
  navbar_links = waiter.driver.find_elements(By.CSS_SELECTOR, ".navbar-nav .nav-link")

  # Check each link for a 200 status code
  for link in navbar_links:
    url = link.get_attribute("href")
    logger.info("Checking URL: %s", url)
    check_components_access(url)