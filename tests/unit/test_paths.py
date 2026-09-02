import os
from pathlib import Path
from jarvis.system.paths import get_app_paths, initialize_paths, AppPaths

def test_get_app_paths_defaults(monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)

    paths = get_app_paths("jarvis_test")
    home = Path.home()
    assert paths.config == home / ".config" / "jarvis_test"
    assert paths.data == home / ".local" / "share" / "jarvis_test"
    assert paths.state == home / ".local" / "state" / "jarvis_test"
    assert paths.cache == home / ".cache" / "jarvis_test"
    assert paths.runtime == Path("/tmp") / f"jarvis_test-{os.getuid()}"


def test_get_app_paths_custom_env(monkeypatch, tmp_path):
    cfg = tmp_path / "custom_config"
    data = tmp_path / "custom_data"
    state = tmp_path / "custom_state"
    cache = tmp_path / "custom_cache"
    runtime = tmp_path / "custom_runtime"

    monkeypatch.setenv("XDG_CONFIG_HOME", str(cfg))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime))

    paths = get_app_paths("jarvis_test")
    assert paths.config == cfg / "jarvis_test"
    assert paths.data == data / "jarvis_test"
    assert paths.state == state / "jarvis_test"
    assert paths.cache == cache / "jarvis_test"
    assert paths.runtime == runtime / "jarvis_test"


def test_initialize_paths(tmp_path):
    paths = AppPaths(
        config=tmp_path / "config",
        data=tmp_path / "data",
        state=tmp_path / "state",
        cache=tmp_path / "cache",
        runtime=tmp_path / "runtime",
    )
    initialize_paths(paths)
    assert paths.config.exists()
    assert paths.data.exists()
    assert paths.state.exists()
    assert paths.cache.exists()
    assert paths.runtime.exists()
    assert oct(paths.config.stat().st_mode)[-3:] == "700"
    assert oct(paths.data.stat().st_mode)[-3:] == "700"
    assert oct(paths.state.stat().st_mode)[-3:] == "700"
    assert oct(paths.cache.stat().st_mode)[-3:] == "700"
    assert oct(paths.runtime.stat().st_mode)[-3:] == "700"
