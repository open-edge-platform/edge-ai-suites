from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException

class ElementWaiter:
  def __init__(self, driver: WebDriver, timeout=10):
    self.driver = driver
    self.timeout = timeout

  def wait_and_assert(self, condition, error_message="Element not found"):
    try:
      element = WebDriverWait(self.driver, self.timeout).until(condition)
      assert element, error_message
      return element
    except TimeoutException:
        assert False, error_message

  def wait_for_text_change(self, element_locator, initial_text, timeout=30, error_message="Text did not change"):
    """Wait for the text of an element to change from a specific value."""
    try:
      WebDriverWait(self.driver, timeout).until(
        lambda driver: driver.find_element(*element_locator).text != initial_text
      )
    except TimeoutException:
      assert False, error_message

  def perform_login(self, url, username_selector, username_selector_value, password_selector, password_selector_value, login_selector, login_selector_value, username, password):
    """Performs login action."""
    self.driver.get(url)  # Load login page

    try:
      # Wait for the username selector to be present
      WebDriverWait(self.driver, self.timeout).until(EC.presence_of_element_located((username_selector, username_selector_value)))
    except TimeoutException:
      assert False, 'username selector not found within 10 seconds'

    username_input = self.driver.find_element(username_selector, username_selector_value)
    password_input = self.driver.find_element(password_selector, password_selector_value)
    login_button = self.driver.find_element(login_selector, login_selector_value)

    username_input.send_keys(username)
    password_input.send_keys(password)
    login_button.click()  # Try to log in
