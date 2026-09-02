import tomllib
from pathlib import Path


def test_pyproject_extras_complete():
    pyproject = Path("pyproject.toml").read_text()
    data = tomllib.loads(pyproject)
    extras = data["project"]["optional-dependencies"]
    for required in ["core", "voice", "camera", "desktop", "dev", "all"]:
        assert required in extras, f"Missing optional dependency extra: {required}"
