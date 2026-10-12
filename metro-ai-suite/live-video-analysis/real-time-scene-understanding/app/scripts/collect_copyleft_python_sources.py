# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Print exact requirement pins for installed Python packages with copyleft metadata."""

from __future__ import annotations

import re
import sys
from email.message import Message
from importlib.metadata import distributions
from pathlib import Path

COPYLEFT_LICENSE = re.compile(
    r"\b(?:AGPL|GPL|LGPL|MPL|EPL|CDDL|EUPL|OSL|CPAL|CPL)\b"
    r"|copyleft|general public license|lesser general public license"
    r"|mozilla public license|eclipse public license"
    r"|common development and distribution license|common public license"
    r"|european union public licen[cs]e",
    re.IGNORECASE,
)
PACKAGE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
PACKAGE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*")


def has_copyleft_license(metadata: Message) -> bool:
    license_fields = [metadata.get("License-Expression", ""), metadata.get("License", "")]
    license_fields.extend(metadata.get_all("Classifier", []))
    return any(COPYLEFT_LICENSE.search(value) for value in license_fields)


def copyleft_requirements(site_packages: Path | None = None) -> list[str]:
    search_path = [str(site_packages)] if site_packages else None
    requirements = set()

    installed_distributions = distributions(path=search_path) if search_path is not None else distributions()
    for distribution in installed_distributions:
        metadata = distribution.metadata
        package_name = metadata.get("Name")
        package_version = distribution.version
        if not package_name or not has_copyleft_license(metadata):
            continue
        if not PACKAGE_NAME.fullmatch(package_name) or not PACKAGE_VERSION.fullmatch(package_version):
            raise ValueError(f"Invalid package requirement metadata: {package_name!r}=={package_version!r}")
        requirements.add(f"{package_name}=={package_version}")

    return sorted(requirements, key=str.casefold)


def main() -> None:
    for requirement in copyleft_requirements():
        print(requirement)


if __name__ == "__main__":
    main()