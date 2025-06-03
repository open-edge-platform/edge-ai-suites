import logging
import os
import time
import unittest

from dotenv import dotenv_values, load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
import tempfile

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

    def capture_screenshot(self, name):
        """
        Helper method to capture a screenshot.
        """
        screenshot_path = os.path.join(tempfile.gettempdir(), f"{name}.png")
        self.driver.save_screenshot(screenshot_path)
        self.logger.info(f"Screenshot saved: {screenshot_path}")
        return screenshot_path

    def upload_image(self, file_path):
        """
        Helper method to upload a file.
        """
        self.logger.info(f"Uploading file: {file_path}")
        upload_input = self.driver.find_element(
            By.XPATH, f"//input[@type='file' and @accept='image/*']"
        )
        upload_input.send_keys(file_path)
        time.sleep(2)
        self.logger.info("File uploaded successfully.")

    def find_button(self, button_text):
        """
        Helper method to find a button by its text.
        """
        return self.driver.find_element(
            By.XPATH, f"//button[contains(text(), '{button_text}')]"
        )

    def start_video_analysis(self):
        """
        Helper method to start video analysis.
        """
        self.logger.info("Starting Video Stream Analysis...")
        analyze_button = self.find_button("Analyze Stream")
        analyze_button.click()
        time.sleep(2)

    def stop_video_analysis(self):
        """
        Helper method to stop video analysis.
        """
        self.logger.info("Stopping Video Stream Analysis...")
        stop_button = self.find_button("Stop Analysis")
        stop_button.click()
        time.sleep(2)

    def capture_frame(self):
        """
        Helper method to capture a frame from the video.
        """
        self.logger.info("Capturing Frame...")
        capture_button = self.find_button("Capture Frame")
        capture_button.click()
        time.sleep(2)

    def search_object(self):
        """
        Helper method to search for an object in the video.
        """
        self.logger.info("Searching for Object...")
        search_button = self.find_button("Search Object")
        search_button.click()
        time.sleep(5)

    def get_search_results(self):
        """
        Helper method to check the search results.
        """
        self.logger.info("Checking Search Results...")
        image_list = self.driver.find_element(By.CLASS_NAME, "image-list")
        image_items = image_list.find_elements(By.TAG_NAME, "li")
        self.logger.info(f"Found {len(image_items)} image results.")
        return image_items

    def clear_database(self):
        """
        Helper method to clear the database.
        """
        self.logger.info("Clearing the database...")
        clear_button = self.find_button("Clear Database")
        clear_button.click()
        time.sleep(2)
        self.logger.info("Database cleared successfully.")

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

    def test_recorded_stream_search_from_frame_capture(self):

        # Set the logs in a new line
        print()

        # Start Video Analysis
        self.start_video_analysis()

        # Wait until analysis completes
        time.sleep(45)

        # Stop Video Analysis
        self.stop_video_analysis()

        # Do Image Search from the captured frame
        self.logger.info("Starting Image Search...")
        self.capture_frame()
        self.search_object()

        # Check Search Results
        image_items = self.get_search_results()

        # Assert that we have 10 results
        self.assertEqual(len(image_items), 10)

        # Clear the Database
        self.clear_database()

    def test_live_stream_search_from_frame_capture(self):

        # Set the logs in a new line
        print()

        # Start Video Analysis
        self.start_video_analysis()

        # Wait until analysis start
        time.sleep(15)

        # Do Image Search from the captured frame
        self.logger.info("Starting Image Search...")
        self.capture_frame()
        self.search_object()

        # Check Search Results
        image_items = self.get_search_results()

        # Assert that we have 10 results
        self.assertEqual(len(image_items), 10)

        # Stop Video Analysis
        self.stop_video_analysis()

        # Clear the Database
        self.clear_database()

    def test_recorded_stream_search_from_image_upload(self):

        # Set the logs in a new line
        print()

        # Start Video Analysis
        self.start_video_analysis()

        # Wait until analysis completes
        time.sleep(45)

        # Stop Video Analysis
        self.stop_video_analysis()

        # Do Image Search from an uploaded image
        self.logger.info("Starting Image Search...")
        self.capture_screenshot("test_image")
        image_path = os.path.join(tempfile.gettempdir(), "test_image.png")
        self.upload_image(image_path)
        self.search_object()

        # Check Search Results
        image_items = self.get_search_results()

        # Assert that we have 10 results
        self.assertEqual(len(image_items), 10)

        # Clear the Database
        self.clear_database()

    def test_live_stream_search_from_image_upload(self):

        # Set the logs in a new line
        print()

        # Start Video Analysis
        self.start_video_analysis()

        # Wait until analysis start
        time.sleep(15)

        # Do Image Search from an uploaded image
        self.logger.info("Starting Image Search...")
        self.capture_screenshot("test_image")
        image_path = os.path.join(tempfile.gettempdir(), "test_image.png")
        self.upload_image(image_path)
        self.search_object()

        # Check Search Results
        image_items = self.get_search_results()

        # Assert that we have 10 results
        self.assertEqual(len(image_items), 10)

        # Stop Video Analysis
        self.stop_video_analysis()

        # Clear the Database
        self.clear_database()


if __name__ == "__main__":
    suite = unittest.TestSuite()
    tests = [
        "test_startup",
        "test_recorded_stream_search_from_frame_capture",
        "test_live_stream_search_from_frame_capture",
        "test_recorded_stream_search_from_image_upload",
        "test_live_stream_search_from_image_upload",
    ]
    for test in tests:
        suite.addTest(ImageBasedVideoSearchTest(test))

    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)
