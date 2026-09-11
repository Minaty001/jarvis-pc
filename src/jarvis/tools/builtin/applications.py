from __future__ import annotations

from jarvis.system.process import ProcessResult, run_process

ALLOWED_APPLICATIONS: dict[str, tuple[str, ...]] = {
    "firefox": ("firefox",),
    "chrome": ("google-chrome",),
    "terminal": ("x-terminal-emulator",),
}

_ALLOWED_URL_SCHEMES = ("http", "https")


class ApplicationError(RuntimeError):
    pass


async def open_application(name: str) -> ProcessResult:
    key = name.strip().lower()
    command = ALLOWED_APPLICATIONS.get(key)
    if command is None:
        raise ApplicationError(f"application {name!r} is not allowed")

    return await run_process(list(command), timeout=10.0)


async def open_url(url: str) -> ProcessResult:
    scheme = url.strip().split(":", 1)[0].lower()
    if scheme not in _ALLOWED_URL_SCHEMES:
        raise ApplicationError(f"unsupported URL scheme {scheme!r}")
    return await run_process(["xdg-open", url.strip()], timeout=10.0)
