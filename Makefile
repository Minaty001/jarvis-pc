.PHONY: all build appimage deb run-pkg install test doctor clean help

help:
	@echo "JARVIS PC — Commands:"
	@echo "  make build      Build all distribution packages (AppImage, deb, .run)"
	@echo "  make appimage   Build standalone portable AppImage"
	@echo "  make deb        Build native Debian/Mint package (.deb)"
	@echo "  make run-pkg    Build self-extracting .run installer"
	@echo "  make install    Install JARVIS PC locally for current user"
	@echo "  make doctor     Run system diagnostics check"
	@echo "  make test       Run pytest test suite"
	@echo "  make clean      Clean build and dist directories"

build:
	@./scripts/build.sh all --verify

appimage:
	@./scripts/build.sh appimage --verify

deb:
	@./scripts/build.sh deb --verify

run-pkg:
	@./scripts/build.sh run --verify

install:
	@./scripts/install.sh

doctor:
	@python3 -m jarvis.cli.doctor

test:
	@uv run pytest

clean:
	@./scripts/build.sh clean
