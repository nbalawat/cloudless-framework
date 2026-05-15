"""Unit tests for cloudless dev --reload file watcher."""
from __future__ import annotations

import time
from pathlib import Path

from cloudless.cli.dev import _scan_mtimes


def test_scan_mtimes_empty_dir(tmp_path: Path):
    """Missing dir returns empty dict, not error."""
    assert _scan_mtimes(tmp_path / "missing") == {}
    assert _scan_mtimes(tmp_path) == {}


def test_scan_mtimes_detects_files(tmp_path: Path):
    """All .py files under root are included, recursively."""
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("# b")
    (tmp_path / "other.txt").write_text("not py")
    out = _scan_mtimes(tmp_path)
    keys = sorted(Path(k).name for k in out)
    assert keys == ["a.py", "b.py"]


def test_scan_mtimes_detects_modification(tmp_path: Path):
    """Modifying a file shows up as a different mtime snapshot."""
    p = tmp_path / "x.py"
    p.write_text("# v1")
    snap1 = _scan_mtimes(tmp_path)
    time.sleep(0.05)
    p.write_text("# v2")
    # Force an mtime bump (filesystem resolutions vary)
    new_mtime = p.stat().st_mtime + 1
    import os
    os.utime(p, (new_mtime, new_mtime))
    snap2 = _scan_mtimes(tmp_path)
    assert snap1 != snap2


def test_scan_mtimes_detects_new_file(tmp_path: Path):
    """Adding a new .py file shows up in the next snapshot."""
    (tmp_path / "a.py").write_text("# a")
    snap1 = _scan_mtimes(tmp_path)
    (tmp_path / "b.py").write_text("# b")
    snap2 = _scan_mtimes(tmp_path)
    assert set(snap2.keys()) > set(snap1.keys())


def test_scan_mtimes_detects_deletion(tmp_path: Path):
    """Deleting a file shrinks the snapshot."""
    (tmp_path / "a.py").write_text("# a")
    (tmp_path / "b.py").write_text("# b")
    snap1 = _scan_mtimes(tmp_path)
    (tmp_path / "b.py").unlink()
    snap2 = _scan_mtimes(tmp_path)
    assert set(snap1.keys()) > set(snap2.keys())
