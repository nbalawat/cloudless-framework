"""Unit tests for `cloudless dev --all` topology planning."""
from __future__ import annotations

import io
import json
import socket
from contextlib import redirect_stdout
from pathlib import Path

from cloudless.cli import dev_all


def _scaffold_project(path: Path, *, agents: list[str]) -> Path:
    """Write a minimal project layout with the given agents declared."""
    path.mkdir()
    agent_lines = "\n".join(
        f"  {n}: {{cloud: aws, interfaces: [http, a2a]}}" for n in agents
    )
    (path / "cloudless.yaml").write_text(
        f"project: testproj\ndefault_cloud: aws\nagents:\n{agent_lines}\n"
    )
    return path


def test_build_local_manifest_shape():
    manifest = dev_all._build_local_manifest(
        {"support": {"port": 8080}, "orders": {"port": 8081}},
        project="myproj",
    )
    assert manifest["project"] == "myproj"
    assert manifest["agents"]["support"]["http_url"] == "http://127.0.0.1:8080/invocations"
    assert manifest["agents"]["orders"]["a2a_url"] == "http://127.0.0.1:8081/a2a"
    assert manifest["agents"]["support"]["audience"] == "local://support"
    assert manifest["agents"]["support"]["cloud"] == "local"


def test_free_port_walks_past_busy_port():
    # Bind a socket at 7900 and ensure _free_port_from(7900) returns 7901.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
        busy.bind(("127.0.0.1", 7900))
        busy.listen(1)
        port = dev_all._free_port_from(7900)
        assert port > 7900


def test_run_with_no_yaml_returns_1(tmp_path: Path):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = dev_all.run(project_root=tmp_path, block=False)
    assert rc == 1
    assert "not found" in buf.getvalue()


def test_run_with_invalid_yaml_returns_2(tmp_path: Path):
    (tmp_path / "cloudless.yaml").write_text("project: BAD CAPS\n")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = dev_all.run(project_root=tmp_path, block=False)
    assert rc == 2


def test_run_writes_local_manifest(tmp_path: Path):
    proj = _scaffold_project(tmp_path / "p", agents=["support", "orders"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = dev_all.run(project_root=proj, base_port=8800, block=False)
    assert rc == 0
    manifest_path = proj / ".cloudless" / "dev-manifest.json"
    assert manifest_path.is_file()
    data = json.loads(manifest_path.read_text())
    assert sorted(data["agents"]) == ["orders", "support"]
    # Ports should be distinct and >= base_port
    ports = [int(d["http_url"].split(":")[-1].split("/")[0]) for d in data["agents"].values()]
    assert len(set(ports)) == 2
    assert all(p >= 8800 for p in ports)


def test_run_with_empty_agents_returns_1(tmp_path: Path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "cloudless.yaml").write_text(
        "project: testproj\ndefault_cloud: aws\nagents: {}\n"
    )
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = dev_all.run(project_root=proj, block=False)
    assert rc == 1
    assert "No agents" in buf.getvalue()
