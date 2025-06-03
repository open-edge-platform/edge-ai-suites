import logging
import os
import time
import unittest

from dotenv import dotenv_values, load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
import tempfile
from datetime import datetime

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
        self.logger.debug(f"Screenshot saved: {screenshot_path}")
        return screenshot_path

    def upload_image(self, file_path):
        """
        Helper method to upload a file.
        """
        self.logger.debug(f"Uploading file: {file_path}")
        upload_input = self.driver.find_element(
            By.XPATH, f"//input[@type='file' and @accept='image/*']"
        )
        upload_input.send_keys(file_path)
        time.sleep(2)
        self.logger.debug("File uploaded successfully.")

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
        self.logger.debug("Starting Video Stream Analysis...")
        analyze_button = self.find_button("Analyze Stream")
        analyze_button.click()
        time.sleep(2)

    def stop_video_analysis(self):
        """
        Helper method to stop video analysis.
        """
        self.logger.debug("Stopping Video Stream Analysis...")
        stop_button = self.find_button("Stop Analysis")
        stop_button.click()
        time.sleep(2)

    def capture_frame(self):
        """
        Helper method to capture a frame from the video.
        """
        self.logger.debug("Capturing Frame...")
        capture_button = self.find_button("Capture Frame")
        capture_button.click()
        time.sleep(2)

    def search_object(self):
        """
        Helper method to search for an object in the video.
        """
        self.logger.debug("Searching for Object...")
        search_button = self.find_button("Search Object")
        search_button.click()
        time.sleep(5)

    def get_search_results(self):
        """
        Helper method to check the search results.
        """
        self.logger.debug("Checking Search Results...")
        image_list = self.driver.find_element(By.CLASS_NAME, "image-list")
        image_items = image_list.find_elements(By.TAG_NAME, "li")
        self.logger.debug(f"Found {len(image_items)} image results.")
        return image_items

    def extract_property(self, item, property_name):
        self.logger.debug(f"Extracting property: {property_name}")
        span = item.find_element(
            By.XPATH, f".//span[contains(text(), '{property_name}')]"
        )
        text = span.text
        try:
            return text.split(":", 1)[1].strip()
        except Exception:
            return -1

    def clear_database(self):
        """
        Helper method to clear the database.
        """
        self.logger.debug("Clearing the database...")
        clear_button = self.find_button("Clear Database")
        clear_button.click()
        time.sleep(2)
        self.logger.debug("Database cleared successfully.")

    def sort_results_by(self, sort_by):
        """
        Helper method to sort the results.
        """
        self.logger.debug(f"Sorting results by: {sort_by}")
        sort_select = self.driver.find_element(By.XPATH, "//select[@id='sort-by']")
        for option in sort_select.find_elements(By.TAG_NAME, "option"):
            if option.text.strip().lower() == sort_by.lower():
                option.click()
                break
        time.sleep(2)

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

    def test_start_video_analysis(self):
        self.logger.debug("Starting Video Analysis...")
        self.start_video_analysis()

        # Wait for a few seconds to ensure the video analysis starts
        time.sleep(2)

        # Assert that the Stop Analysis button is present
        stop_button = self.find_button("Stop Analysis")
        self.assertIsNotNone(stop_button, "Video Analysis did not start properly.")

        # Wait for video analysis to make progress
        self.logger.debug("Waiting for Video Analysis to make progress...")
        time.sleep(30)

    def test_stop_video_analysis(self):
        self.logger.debug("Stopping Video Analysis...")
        self.stop_video_analysis()

        # Wait for a few seconds to ensure the video analysis stops
        time.sleep(2)

        # Assert that the Analyze Stream button is present
        analyze_button = self.find_button("Analyze Stream")
        self.assertIsNotNone(analyze_button, "Video Analysis did not stop properly.")

    def test_search_by_frame_capture(self):
        self.logger.debug("Starting Image Search from Frame Capture...")
        self.capture_frame()
        self.search_object()

    def test_search_by_image_upload(self):
        self.logger.debug("Starting Image Search from Upload...")
        self.capture_screenshot("test_image")
        image_path = os.path.join(tempfile.gettempdir(), "test_image.png")
        self.upload_image(image_path)
        self.search_object()

    def test_results_count(self):
        # Check Search Results
        image_items = self.get_search_results()

        # Assert that we have 10 results
        self.assertEqual(len(image_items), 10, "Search did not return 10 results.")

    def test_results_sorting(self):

        # Sort Results By Distance
        self.sort_results_by("distance")
        sorted_items = self.get_search_results()
        distances = [self.extract_property(item, "Distance") for item in sorted_items]
        distances = [float(d) for d in distances]

        # Assert that the first element has the highest distance
        self.assertEqual(
            distances[0],
            max(distances),
            "First element does not have the highest distance",
        )

        # Sort Results By Label
        self.sort_results_by("label")
        sorted_items = self.get_search_results()
        labels = [self.extract_property(item, "Label") for item in sorted_items]
        labels = [l.lower() for l in labels]

        # Assert that the first element has the lowest label
        self.assertEqual(
            labels[0], min(labels), "First element does not have the lowest label"
        )

        # Sort Results By Timestamp
        self.sort_results_by("Date")
        sorted_items = self.get_search_results()
        timestamps = [self.extract_property(item, "Timestamp") for item in sorted_items]
        timestamps = [datetime.strptime(t, "%m/%d/%Y, %I:%M:%S %p") for t in timestamps]

        # Assert that the first element has the highest timestamp
        self.assertEqual(
            timestamps[0],
            max(timestamps),
            "First element does not have the highest timestamp",
        )

    def test_clear_database(self):
        # Clear the Database
        self.logger.debug("Clearing the database...")
        self.clear_database()


if __name__ == "__main__":

    tests = [
        # Suite 1 do Recorded Stream Search with Input by Frame Capture
        [
            "test_startup",
            "test_start_video_analysis",
            "test_stop_video_analysis",
            "test_search_by_frame_capture",
            "test_results_count",
            "test_results_sorting",
            "test_clear_database",
        ],
        # Suite 2 do Live Stream Search with Input by Frame Capture
        [
            "test_startup",
            "test_start_video_analysis",
            "test_search_by_frame_capture",
            "test_stop_video_analysis",
            "test_results_count",
            "test_results_sorting",
            "test_clear_database",
        ],
        # Suite 3 do Recorded Stream Search with Input by Image Upload
        [
            "test_startup",
            "test_start_video_analysis",
            "test_stop_video_analysis",
            "test_search_by_image_upload",
            "test_results_count",
            "test_results_sorting",
            "test_clear_database",
        ],
        # Suite 4 do Live Stream Search with Input by Image Upload
        [
            "test_startup",
            "test_start_video_analysis",
            "test_search_by_image_upload",
            "test_stop_video_analysis",
            "test_results_count",
            "test_results_sorting",
            "test_clear_database",
        ],
    ]

    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)

    # Run each test suite
    for test_suite in tests:
        suite = unittest.TestSuite()
        for test in test_suite:
            suite.addTest(ImageBasedVideoSearchTest(test))
        runner.run(suite)
