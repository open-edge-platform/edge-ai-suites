# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Path-containment tests for `data_dir` (fuzz finding §1.2).

`register_source` lets the caller pick `data_dir`, and the service then does
`os.makedirs` on it. Without containment that is "create a directory anywhere
the service user can write", and every recording/segment afterwards lands
there too.
"""

from __future__ import annotations

import os

import pytest

from shared.config import (
    AppConfig,
    SourceConfig,
    expand_user_path,
    resolve_contained_dir,
)
from source_worker import SourceManager


@pytest.fixture
def root(tmp_path):
    d = tmp_path / "segments"
    d.mkdir()
    return str(d)


class TestResolveContainedDir:
    def test_child_is_allowed(self, root):
        assert resolve_contained_dir([root], os.path.join(root, "cam_child")) == os.path.join(
            root, "cam_child"
        )

    def test_nested_child_is_allowed(self, root):
        target = os.path.join(root, "a", "b", "c")
        assert resolve_contained_dir([root], target) == target

    def test_root_itself_is_rejected(self, root):
        # A source must own a subdirectory, not the shared root.
        with pytest.raises(ValueError):
            resolve_contained_dir([root], root)

    def test_dotdot_escape_is_rejected(self, root):
        with pytest.raises(ValueError, match=r"\.\."):
            resolve_contained_dir([root], os.path.join(root, "..", "pwn"))

    def test_absolute_path_outside_root_is_rejected(self, root):
        with pytest.raises(ValueError, match="escapes"):
            resolve_contained_dir([root], "/tmp/pwn")

    def test_relative_path_is_rejected(self, root):
        # This is the reported `data_dir: "fuzzstring"` case: relative to the
        # service CWD, `os.makedirs` used to raise PermissionError -> 500.
        with pytest.raises(ValueError, match="absolute"):
            resolve_contained_dir([root], "fuzzstring")

    def test_nul_byte_is_rejected(self, root):
        with pytest.raises(ValueError, match="NUL"):
            resolve_contained_dir([root], os.path.join(root, "a\x00b"))

    def test_sibling_with_root_as_prefix_is_rejected(self, root):
        # Guards against a naive `startswith` check: "<root>-evil" shares the
        # root's string prefix but is not inside it.
        with pytest.raises(ValueError, match="escapes"):
            resolve_contained_dir([root], root + "-evil/x")

    def test_symlink_escaping_the_root_is_rejected(self, root, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        os.symlink(str(outside), os.path.join(root, "link"))
        with pytest.raises(ValueError, match="symlink resolution"):
            resolve_contained_dir([root], os.path.join(root, "link", "pwn"))

    def test_extra_allowed_root_is_honoured(self, root, tmp_path):
        alt = tmp_path / "alt"
        alt.mkdir()
        target = os.path.join(str(alt), "cam")
        assert resolve_contained_dir([root, str(alt)], target) == target

    def test_root_that_does_not_exist_yet_still_works(self, tmp_path):
        # Fresh install: nothing has created the segments tree yet. This must
        # not reject every registration.
        fresh = str(tmp_path / "nope" / "segments")
        target = os.path.join(fresh, "cam_child")
        assert resolve_contained_dir([fresh], target) == target

    def test_symlinked_root_pointing_elsewhere_is_allowed(self, tmp_path):
        # Legitimate ops setup: the segments dir is a symlink to another volume.
        volume = tmp_path / "volume"
        volume.mkdir()
        link_root = str(tmp_path / "segments")
        os.symlink(str(volume), link_root)
        target = os.path.join(link_root, "cam_child")
        assert resolve_contained_dir([link_root], target) == target

    def test_no_roots_configured_is_rejected(self):
        with pytest.raises(ValueError, match="no permitted data root"):
            resolve_contained_dir([], "/tmp/x")


class TestExpandUserPath:
    def test_expands_tilde(self):
        assert expand_user_path("~/x") == os.path.join(os.path.expanduser("~"), "x")

    def test_does_not_expand_env_vars(self, monkeypatch):
        # `expandvars` on request input would turn the response's `data_dir`
        # into an environment-variable oracle for an unauthenticated caller.
        monkeypatch.setenv("VSA_SECRET_PROBE", "leaked")
        assert expand_user_path("/x/${VSA_SECRET_PROBE}") == "/x/${VSA_SECRET_PROBE}"


class TestSourceManagerDataDir:
    """`SourceManager._resolve_data_dir` must contain both of its branches."""

    def _manager(self, root, extra_roots=None):
        config = AppConfig(
            data_dir=root, allowed_data_roots=list(extra_roots or [])
        )
        mgr = SourceManager.__new__(SourceManager)  # skip the watchdog thread
        mgr.config = config
        return mgr

    def test_default_branch_uses_source_id_subdir(self, root):
        mgr = self._manager(root)
        source = SourceConfig(source_id="cam_child", source_url="rtsp://h/s")
        assert mgr._resolve_data_dir(source) == os.path.join(root, "cam_child")

    def test_explicit_data_dir_inside_root_is_accepted(self, root):
        mgr = self._manager(root)
        target = os.path.join(root, "custom")
        source = SourceConfig(
            source_id="cam_child", source_url="rtsp://h/s", data_dir=target
        )
        assert mgr._resolve_data_dir(source) == target

    def test_explicit_data_dir_outside_root_is_rejected(self, root):
        mgr = self._manager(root)
        source = SourceConfig(
            source_id="cam_child", source_url="rtsp://h/s", data_dir="/tmp/pwn"
        )
        with pytest.raises(ValueError, match="escapes"):
            mgr._resolve_data_dir(source)

    def test_traversal_via_source_id_is_rejected(self, root):
        # The API layer's regex already blocks this id; the default branch is
        # contained anyway so loosening one side alone is not a traversal.
        mgr = self._manager(root)
        source = SourceConfig(source_id="../../tmp/pwn", source_url="rtsp://h/s")
        with pytest.raises(ValueError):
            mgr._resolve_data_dir(source)

    def test_allowed_data_roots_permits_other_mount(self, root, tmp_path):
        alt = tmp_path / "nvme"
        alt.mkdir()
        mgr = self._manager(root, extra_roots=[str(alt)])
        target = os.path.join(str(alt), "cam_child")
        source = SourceConfig(
            source_id="cam_child", source_url="rtsp://h/s", data_dir=target
        )
        assert mgr._resolve_data_dir(source) == target
