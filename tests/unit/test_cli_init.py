"""Unit tests for `cloudless init` — no cloud calls."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cloudless.cli import init as init_cmd
from cloudless.cli.main import main


@pytest.fixture
def tmp_target():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


class TestInitScaffolding:
    def test_creates_project_directory(self, tmp_target):
        rc = init_cmd.run("my-app", target_dir=tmp_target)
        assert rc == 0
        assert (tmp_target / "my-app").is_dir()

    def test_creates_expected_files(self, tmp_target):
        init_cmd.run("my-app", target_dir=tmp_target)
        base = tmp_target / "my-app"
        for expected in (
            "cloudless.yaml",
            "pyproject.toml",
            "README.md",
            ".gitignore",
            "src/agents/hello.py",
            "evals/datasets/hello.jsonl",
            "tests/test_hello.py",
            ".cloudless/dev-secrets.yaml.example",
        ):
            assert (base / expected).is_file(), f"missing scaffolded file: {expected}"

    def test_default_framework_is_langgraph(self, tmp_target):
        init_cmd.run("lg-app", target_dir=tmp_target)
        hello = (tmp_target / "lg-app" / "src/agents/hello.py").read_text()
        assert "LangGraphAgent" in hello
        assert "StateGraph" in hello

    def test_strands_framework(self, tmp_target):
        init_cmd.run("st-app", framework="strands", target_dir=tmp_target)
        hello = (tmp_target / "st-app" / "src/agents/hello.py").read_text()
        assert "StrandsAgent" in hello
        assert "StrandsCoreAgent" in hello

    def test_cloud_default_aws(self, tmp_target):
        init_cmd.run("aws-app", target_dir=tmp_target)
        cfg = (tmp_target / "aws-app" / "cloudless.yaml").read_text()
        assert "default_cloud: aws" in cfg

    def test_cloud_gcp(self, tmp_target):
        init_cmd.run("gcp-app", cloud="gcp", target_dir=tmp_target)
        cfg = (tmp_target / "gcp-app" / "cloudless.yaml").read_text()
        assert "default_cloud: gcp" in cfg

    def test_conflict_without_force_returns_1(self, tmp_target):
        (tmp_target / "my-app").mkdir()
        rc = init_cmd.run("my-app", target_dir=tmp_target)
        assert rc == 1

    def test_force_overwrites(self, tmp_target):
        (tmp_target / "my-app").mkdir()
        (tmp_target / "my-app" / "stale.txt").write_text("old")
        rc = init_cmd.run("my-app", force=True, target_dir=tmp_target)
        assert rc == 0
        assert not (tmp_target / "my-app" / "stale.txt").exists()
        assert (tmp_target / "my-app" / "cloudless.yaml").is_file()

    def test_unknown_framework_raises(self, tmp_target):
        with pytest.raises(ValueError, match="Unknown framework"):
            init_cmd.run("bad", framework="autogen", target_dir=tmp_target)


class TestCLIDispatch:
    """Test the top-level `cloudless` CLI dispatcher."""

    def test_version_command_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main(["--version"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert out.startswith("cloudless ")

    def test_init_via_cli(self, tmp_target, monkeypatch):
        monkeypatch.chdir(tmp_target)
        rc = main(["init", "cli-app"])
        assert rc == 0
        assert (tmp_target / "cli-app" / "cloudless.yaml").is_file()

    def test_help_lists_init(self, capsys):
        with pytest.raises(SystemExit):
            main(["--help"])
        out = capsys.readouterr().out
        assert "init" in out

    def test_no_command_errors(self, capsys):
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code != 0
