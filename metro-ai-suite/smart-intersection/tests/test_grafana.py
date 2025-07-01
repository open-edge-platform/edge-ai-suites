# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
from .conftest import GRAFANA_URL, GRAFANA_PASSWORD, GRAFANA_USERNAME
from selenium.webdriver.common.by import By
from tests.utils.ui_utils import driver
from tests.utils.utils import perform_login


@pytest.mark.zephyr_id("NEX-T9371")
def test_grafana_anthem_dashboard_avability(driver):
  perform_login(
    driver,
    GRAFANA_URL,
    By.CSS_SELECTOR, "[data-testid='data-testid Username input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Password input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Login button']",
    GRAFANA_USERNAME, GRAFANA_PASSWORD
  )
