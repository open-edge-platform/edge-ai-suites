import logging
import os
import time
import unittest

from dotenv import dotenv_values, load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By

logging.basicConfig(level=logging.INFO)

FILE_PATH = os.path.dirname(os.path.abspath(__file__))
ENV_FILE_PATH = os.path.join(FILE_PATH, ".env")

load_dotenv(ENV_FILE_PATH)


class ImageBasedVideoSearchTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config = dotenv_values(ENV_FILE_PATH)
        options = webdriver.ChromeOptions()
        options.add_argument("window-size=1280,800")
        cls.driver = webdriver.Chrome(options=options)
        cls.driver.get(cls.config["ROOT_URL"])
        cls.logger = logging.getLogger("ImageBasedVideoSearchTest")
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        pass

    def find_button(self, button_text):
        """
        Helper method to find a button by its text.
        """
        return self.driver.find_element(
            By.XPATH, f"//button[contains(text(), '{button_text}')]"
        )

    def test_startup(self):
        # Assert page title is correct
        self.assertIn("Image Search", self.driver.title)

        # Assert that map loads
        map_element = self.driver.find_element(By.ID, "map")
        self.assertIsNotNone(map_element)

        # Assert that video loads
        video_iframe = self.driver.find_element(
            By.XPATH, "//iframe[@title='Local Stream']"
        )
        self.driver.switch_to.frame(video_iframe)
        video_element = self.driver.find_element(By.ID, "video")
        self.driver.switch_to.default_content()
        self.assertIsNotNone(video_element)

        # Assert that buttons loads
        button_texts = [
            "Analyze Stream",
            "Capture Frame",
            "Upload Image",
            "Clear Database",
        ]
        for text in button_texts:
            button = self.find_button(text)
            self.assertIsNotNone(button)

    def test_live_search(self):

        # Start Video Analysis
        self.logger.info("Starting Video Stream Analysis...")
        analyze_button = self.find_button("Analyze Stream")
        analyze_button.click()

        # Wait until analysis is done
        time.sleep(45)

        # Stop Video Analysis
        self.logger.info("Stopping Video Stream Analysis...")
        stop_button = self.find_button("Stop Analysis")
        stop_button.click()

        # Do Image Search
        self.logger.info("Starting Image Search...")
        capture_button = self.find_button("Capture Frame")
        capture_button.click()
        time.sleep(2)
        search_button = self.find_button("Search Object")
        search_button.click()
        time.sleep(5)

        # Check Search Results
        self.logger.info("Checking Search Results...")
        image_list = self.driver.find_element(By.CLASS_NAME, "image-list")
        image_items = image_list.find_elements(By.TAG_NAME, "li")
        self.logger.info(f"Found {len(image_items)} image results.")
        self.assertEqual(len(image_items), 10)

        # Clear the Database
        self.logger.info("Clearing the database...")
        clear_button = self.find_button("Clear Database")
        clear_button.click()
        time.sleep(2)
        self.logger.info("Database cleared successfully.")


if __name__ == "__main__":
    suite = unittest.TestSuite()
    suite.addTest(ImageBasedVideoSearchTest("test_startup"))
    suite.addTest(ImageBasedVideoSearchTest("test_live_search"))
    runner = unittest.TextTestRunner()
    runner.run(suite)
