"""Main entrypoint for jarvis module execution."""
import sys
from pathlib import Path

# Ensure repository root is in sys.path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

try:
    from scripts.doctor import run_doctor
except ImportError:
    from doctor import run_doctor  # fallback if scripts directory is directly in sys.path


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        print(run_doctor())
    else:
        print("JARVIS CLI v1.0.0 (Linux)")


if __name__ == "__main__":
    main()
