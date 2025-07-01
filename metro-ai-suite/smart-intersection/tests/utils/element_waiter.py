# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

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
