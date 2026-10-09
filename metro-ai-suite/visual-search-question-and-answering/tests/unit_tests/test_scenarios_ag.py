# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""End-to-end UI scenarios A-G driven through the real Streamlit widgets."""

import datetime
import glob
import json
import os
import time
from io import BytesIO

import pytest

from streamlit.testing.v1 import AppTest

# Cluster deployments ingest far slower than a local compose stack, so allow
# the timeout to be raised without editing the suite.
APP_TIMEOUT = int(os.environ.get("APP_TEST_TIMEOUT", "180"))
HOST_DATA_PATH = os.environ.get("HOST_DATA_PATH", "/home/user/data")
SUBSET = os.path.join(HOST_DATA_PATH, "DAVIS", "subset")
CONTAINER_SUBSET = "/home/user/data/DAVIS/subset"


def fresh():
    at = AppTest.from_file("/home/user/visual-search-qa/src/app.py", default_timeout=APP_TIMEOUT)
    at.run()
    return at


@pytest.fixture(scope="module", autouse=True)
def dataset():
    """Own the sidecars and the ingested corpus.

    Other suites in this directory delete meta/ and clear the DB, so these
    scenarios must not rely on state left behind by whatever ran before.
    """
    meta = os.path.join(CONTAINER_SUBSET, "meta")
    os.makedirs(meta, exist_ok=True)
    files = sorted(
        glob.glob(os.path.join(CONTAINER_SUBSET, "*.jpg"))
        + glob.glob(os.path.join(CONTAINER_SUBSET, "*.mp4"))
    )
    assert files, f"demo dataset missing under {CONTAINER_SUBSET}"
    for i, f in enumerate(files):
        base = os.path.splitext(os.path.basename(f))[0]
        cam = "cam-ui" if base.startswith("tractor") else f"camera_{i % 3 + 1}"
        date = 20260115 if base.startswith("tractor") else 20260220 + (i % 3)
        with open(os.path.join(meta, base + ".json"), "w") as fh:
            json.dump({"camera": cam, "capture_date": date, "tags": ["demo"]}, fh)

    at = fresh()
    at.button(key="kclear_db").click().run()
    time.sleep(3)
    at.text_input(key="kfilePath").input(SUBSET)
    at.button(key="kupdate_db").click().run()
    time.sleep(5)
    yield
    # Scenario F ends with an empty DB; restore the corpus so suites that run
    # after this module still have data to search.
    at2 = fresh()
    at2.text_input(key="kfilePath").input(SUBSET)
    at2.button(key="kupdate_db").click().run()
    time.sleep(5)


def _log(at):
    log = at.session_state.latest_log or ""
    return "\n".join(log) if isinstance(log, list) else log


def _hits(at):
    log = at.session_state.latest_log or []
    return len(log) if isinstance(log, list) else (1 if log.strip() else 0)


def do_search(at, text, k=10):
    at.number_input(key="kk").set_value(k)
    at.text_input(key="ktext").input(text)
    at.button(key="kSearch").click().run()
    return _log(at)


def search_hits(at, text, k=10):
    do_search(at, text, k)
    return _hits(at)


# ---------------------------------------------------------------- Use-case A
def test_a_update_db_directory():
    at = fresh()
    at.text_input(key="kfilePath").input(SUBSET)
    at.button(key="kupdate_db").click().run()
    log = _log(at)
    # The log is a rendered dict; parse the status field rather than substring
    # matching, since it also carries counters such as "failed: 0".
    fields = dict(line.split(": ", 1) for line in log.splitlines() if ": " in line)
    status = fields.get("status", "")
    assert status in ("completed", "success"), f"UpdateDB status={status!r} log={log[:300]}"
    assert fields.get("failed", "0") == "0", f"UpdateDB reported failures: {log[:300]}"


# ---------------------------------------------------------------- Use-case B
def test_b_text_search_relevance():
    at = fresh()
    expected = ["tractor", "deer", "helicopter", "rollercoaster"]
    misses = [q for q in expected if q not in do_search(at, q)]
    assert not misses, f"queries returned no matching media: {misses}"


def test_b2_result_count_respected():
    at = fresh()
    for k in (3, 7):
        n = search_hits(at, "tractor", k=k)
        assert n <= k, f"asked for {k} results, UI rendered {n}"
        assert n > 0, f"no results for k={k}"


def test_b3_results_carry_timestamp_and_media():
    at = fresh()
    log = do_search(at, "tractor")
    assert "timestamp" in log, "results are missing timestamp field"
    assert "file_path" in log or "video_rel_url" in log, "results carry no media reference"


def test_b4_frame_type_is_canonical():
    """dataprep emits FULL_FRAME for video frames and full_frame for images.

    A mixed result set must reach the UI with a single spelling, otherwise any
    consumer comparing this field drops whichever half it did not spell.
    """
    from app import normalize_meta

    raw = [
        {"frame_type": "FULL_FRAME", "content_type": "video"},
        {"frame_type": "full_frame", "content_type": "image"},
        {"frame_type": "DETECTED_CROP", "content_type": "video"},
    ]
    got = [normalize_meta(m)["frame_type"] for m in raw]
    assert got == ["full_frame", "full_frame", "detected_crop"], got
    # A row without the field must not gain one.
    assert "frame_type" not in normalize_meta({"content_type": "image"})


# ---------------------------------------------------------------- Use-case C
def test_c_camera_filter():
    at = fresh()
    assert "tractor" in do_search(at, "tractor", k=20)

    at2 = fresh()
    at2.text_input(key="kCamera").input("cam-ui")
    filtered = do_search(at2, "tractor", k=20)
    assert filtered.strip(), "camera filter returned nothing at all"
    # Only tractor.* carries camera cam-ui in the sidecars.
    for line in filtered.splitlines():
        if line.startswith("file_path: ") and line.strip() != "file_path:":
            assert "tractor" in line, f"camera filter leaked a non-cam-ui item: {line}"


def test_c2_date_filter():
    at = fresh()
    at.date_input(key="kf_s_time").set_value(datetime.date(2026, 1, 1))
    at.date_input(key="kf_e_time").set_value(datetime.date(2026, 1, 31)).run()
    jan = do_search(at, "tractor", k=20)
    # Only tractor is dated 20260115; everything else is 202602xx.
    for line in jan.splitlines():
        if line.startswith("file_path: ") and line.strip() != "file_path:":
            assert "tractor" in line, f"date filter leaked an out-of-range item: {line}"

    at2 = fresh()
    at2.date_input(key="kf_s_time").set_value(datetime.date(2025, 1, 1))
    at2.date_input(key="kf_e_time").set_value(datetime.date(2025, 12, 31)).run()
    assert search_hits(at2, "tractor", k=20) == 0, "empty date range still returned hits"


# ---------------------------------------------------------------- Use-case D
def test_d_image_query():
    at = fresh()
    candidates = sorted(glob.glob(os.path.join(CONTAINER_SUBSET, "deer*.jpg")))
    assert candidates, f"no source image found under {CONTAINER_SUBSET}"
    # file_for_search holds the uploader's file-like object; the app opens it with PIL.
    with open(candidates[0], "rb") as fh:
        at.session_state.file_for_search = BytesIO(fh.read())
    at.number_input(key="kk").set_value(5)
    at.button(key="kSearch").click().run()
    log = _log(at)
    assert log.strip(), "image query returned nothing"
    assert "deer" in log, f"image query did not retrieve its own category: {log[:200]}"


# ---------------------------------------------------------------- Use-case E
def test_e_dedup_toggle():
    at = fresh()
    at.checkbox(key="kded").set_value(False)
    off = search_hits(at, "tractor", k=20)
    at.checkbox(key="kded").set_value(True)
    on = search_hits(at, "tractor", k=20)
    assert off > 0, "no results with dedup off"
    assert on <= off, f"dedup increased result count: off={off} on={on}"


# ---------------------------------------------------------------- Use-case G
def test_g_qa_over_selection():
    at = fresh()
    do_search(at, "tractor")
    assert at.session_state.data, "no search results to select from"
    at.chat_input[0].set_value("Describe what you see in one sentence.").run()
    answer = _log(at)
    assert answer.strip(), "VQA produced no answer"
    assert "rror" not in answer, f"VQA errored: {answer[:200]}"


# ---------------------------------------------------------------- Use-case F
def test_f_clear_db():
    at = fresh()
    at.button(key="kclear_db").click().run()
    time.sleep(5)
    at2 = fresh()
    n = search_hits(at2, "tractor", k=20)
    assert n == 0, f"ClearDB left {n} searchable results"
