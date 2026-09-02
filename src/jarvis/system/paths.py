import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    config: Path
    data: Path
    state: Path
    cache: Path
    runtime: Path


def _env_path(env_var: str, default: Path) -> Path:
    val = os.environ.get(env_var)
    if val:
        return Path(val)
    return default


def get_app_paths(app_name: str = "jarvis") -> AppPaths:
    home = Path.home()
    
    config_base = _env_path("XDG_CONFIG_HOME", home / ".config")
    data_base = _env_path("XDG_DATA_HOME", home / ".local" / "share")
    state_base = _env_path("XDG_STATE_HOME", home / ".local" / "state")
    cache_base = _env_path("XDG_CACHE_HOME", home / ".cache")
    
    runtime_env = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_env:
        runtime_dir = Path(runtime_env) / app_name
    else:
        runtime_dir = Path("/tmp") / f"{app_name}-{os.getuid()}"

    return AppPaths(
        config=config_base / app_name,
        data=data_base / app_name,
        state=state_base / app_name,
        cache=cache_base / app_name,
        runtime=runtime_dir,
    )


def initialize_paths(paths: AppPaths) -> None:
    for path in (paths.config, paths.data, paths.state, paths.cache, paths.runtime):
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
