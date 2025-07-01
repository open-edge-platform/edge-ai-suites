# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
from selenium.webdriver.common.by import By
from tests.utils.ui_utils import driver
from tests.utils.utils import perform_login, get_password_from_supass_file
from .conftest import SMART_INTERSECTION_URL

@pytest.mark.zephyr_id("NEX-T9389")
def test_intersection_demo_avability(driver):
    """Test that the admin login functionality works correctly."""
    perform_login(
        driver,
        SMART_INTERSECTION_URL,
        By.ID, "username",
        By.ID, "password",
        By.ID, "login-submit",
        "admin", get_password_from_supass_file()
    )

    # Find the link element that contains the image with alt text "Intersection-Demo"
    link_element = driver.find_element(By.XPATH, "//a[img[@alt='Intersection-Demo']]")
    assert link_element, "Link containing image with alt text 'Intersection-Demo' is not present on the page"

    # Click the link element
    link_element.click()

    # Verify that the scene name element is present and has the correct text
    scene_name_element = driver.find_element(By.ID, "scene_name")
    assert scene_name_element and scene_name_element.text == "Intersection-Demo", (
        "Scene name element is not present or text does not match 'Intersection-Demo'"
    )