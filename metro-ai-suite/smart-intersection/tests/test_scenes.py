# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.ui_utils import waiter, driver
from .conftest import SMART_INTERSECTION_URL, SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD

@pytest.mark.zephyr_id("NEX-T9370")
def test_intersection_demo_avability(waiter):
    """Test that the admin login functionality works correctly."""
    # Perform login using Waiter class object
    waiter.perform_login(
        SMART_INTERSECTION_URL,
        By.ID, "username",
        By.ID, "password",
        By.ID, "login-submit",
        SMART_INTERSECTION_USERNAME, SMART_INTERSECTION_PASSWORD
    )

    # Find the link element that contains the image with alt text "Intersection-Demo"
    link_element = waiter.wait_and_assert(
        EC.presence_of_element_located((By.XPATH, "//a[img[@alt='Intersection-Demo']]")),
        error_message="Link containing image with alt text 'Intersection-Demo' is not present on the page"
    )
    link_element.click()

    # Verify that the scene name element is present and has the correct text
    scene_name_element = waiter.wait_and_assert(
        EC.presence_of_element_located((By.ID, "scene_name")),
        error_message="Scene name element is not present or text does not match 'Intersection-Demo'"
    )
    assert scene_name_element.text == "Intersection-Demo", (
        "Scene name text does not match 'Intersection-Demo'"
    )


# def test_add_scene(waiter):
#     """Test that the admin can add a new scene."""
#     # Perform login using Waiter class object
#     waiter.perform_login(
#         SMART_INTERSECTION_URL,