import re
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def test_runtime_dependencies_are_exactly_represented_in_production_lock():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    runtime = {
        _normalize(re.match(r"[A-Za-z0-9_.-]+", requirement).group(0))
        for requirement in project["project"]["dependencies"]
    }
    pins = {}
    for raw in (ROOT / "requirements.lock").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line and not any(op in line for op in (">=", "<=", "~=", "!=", "<", ">"))
        name, version = line.split("==", 1)
        normalized = _normalize(name)
        assert normalized not in pins
        assert version
        pins[normalized] = version
    assert runtime <= set(pins)


def test_docker_build_uses_lock_and_installs_project_without_dependency_resolution():
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "COPY pyproject.toml requirements.lock ./" in dockerfile
    assert "pip install --no-cache-dir -r requirements.lock" in dockerfile
    assert "pip install --no-cache-dir --no-deps ." in dockerfile
