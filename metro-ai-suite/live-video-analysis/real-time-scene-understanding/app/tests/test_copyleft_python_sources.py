# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from email.message import Message

from scripts import collect_copyleft_python_sources as collector
from scripts.collect_copyleft_python_sources import copyleft_requirements, has_copyleft_license


def _write_distribution(site_packages, name, version, metadata_fields):
    dist_info = site_packages / f"{name}-{version}.dist-info"
    dist_info.mkdir()
    fields = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}"]
    fields.extend(metadata_fields)
    (dist_info / "METADATA").write_text("\n".join(fields) + "\n", encoding="utf-8")


def test_detects_copyleft_license_expression():
    metadata = Message()
    metadata["License-Expression"] = "GPL-3.0-or-later"

    assert has_copyleft_license(metadata)


def test_detects_license_classifier():
    metadata = Message()
    metadata["Classifier"] = "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)"

    assert has_copyleft_license(metadata)


def test_returns_sorted_exact_pins_for_copyleft_distributions(tmp_path):
    _write_distribution(tmp_path, "sample-mpl", "2.0", ["License: MPL-2.0"])
    _write_distribution(tmp_path, "sample-mit", "1.0", ["License: MIT"])
    _write_distribution(tmp_path, "sample-gpl", "3.1", ["License-Expression: GPL-3.0-or-later"])

    assert copyleft_requirements(tmp_path) == ["sample-gpl==3.1", "sample-mpl==2.0"]


def test_scans_current_environment_when_path_is_omitted(monkeypatch):
    called = []

    def fake_distributions():
        called.append(True)
        return []

    monkeypatch.setattr(collector, "distributions", fake_distributions)

    assert copyleft_requirements() == []
    assert called == [True]