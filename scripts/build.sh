#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

print_header() {
    echo -e "${CYAN}${BOLD}"
    echo "=========================================================="
    echo "       JARVIS PC — Unified Distribution Builder           "
    echo "=========================================================="
    echo -e "${NC}"
}

usage() {
    echo -e "${BOLD}Usage:${NC} $0 [TARGET] [OPTIONS]"
    echo ""
    echo -e "${BOLD}Targets:${NC}"
    echo "  all         Build all distribution packages (default)"
    echo "  appimage    Build standalone AppImage (.AppImage)"
    echo "  deb         Build native Debian/Mint package (.deb)"
    echo "  run         Build self-extracting shell installer (.run)"
    echo "  clean       Clean build artifacts and dist directory"
    echo ""
    echo -e "${BOLD}Options:${NC}"
    echo "  --verify    Run doctor verification on built images"
    echo "  --help, -h  Show this help screen"
    exit 0
}

TARGET="all"
VERIFY=false

for arg in "$@"; do
    case "$arg" in
        all|appimage|deb|run|clean) TARGET="$arg" ;;
        --verify) VERIFY=true ;;
        --help|-h) usage ;;
        *) echo -e "${RED}Unknown argument: $arg${NC}"; usage ;;
    esac
done

print_header

if [ "$TARGET" = "clean" ]; then
    echo -e "${YELLOW}Cleaning build and dist directories...${NC}"
    rm -rf "$ROOT_DIR/build" "$DIST_DIR"/*.AppImage "$DIST_DIR"/*.deb "$DIST_DIR"/*.run "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz
    echo -e "${GREEN}Clean completed successfully.${NC}"
    exit 0
fi

# Step 1: Ensure wheel is built first
echo -e "${BLUE}[1/4] Building base Python wheel...${NC}"
mkdir -p "$DIST_DIR"
uv build --wheel --out-dir "$DIST_DIR"
WHEEL=$(ls -t "$DIST_DIR"/jarvis_pc-*.whl | head -n1)
echo -e "  -> ${GREEN}Wheel:${NC} $(basename "$WHEEL")"

# Step 2: Build targeted artifacts
case "$TARGET" in
    appimage)
        echo -e "\n${BLUE}[2/4] Building standalone AppImage...${NC}"
        "$SCRIPT_DIR/build_appimage.sh"
        ;;
    deb)
        echo -e "\n${BLUE}[2/4] Building Debian package...${NC}"
        "$SCRIPT_DIR/build_deb.sh"
        ;;
    run)
        echo -e "\n${BLUE}[2/4] Building Self-Extracting installer...${NC}"
        "$SCRIPT_DIR/build_installer.sh"
        ;;
    all)
        echo -e "\n${BLUE}[2/4] Building standalone AppImage...${NC}"
        "$SCRIPT_DIR/build_appimage.sh"
        echo -e "\n${BLUE}[3/4] Building Debian package...${NC}"
        "$SCRIPT_DIR/build_deb.sh"
        echo -e "\n${BLUE}[4/4] Building Self-Extracting installer...${NC}"
        "$SCRIPT_DIR/build_installer.sh"
        ;;
esac

# Optional verification
if [ "$VERIFY" = true ]; then
    echo -e "\n${YELLOW}Verifying built packages...${NC}"
    if [ -f "$DIST_DIR/JARVIS-x86_64.AppImage" ]; then
        echo -n "Verifying AppImage... "
        "$DIST_DIR/JARVIS-x86_64.AppImage" --appimage-extract-and-run version >/dev/null && echo -e "${GREEN}OK${NC}"
    fi
    if [ -f "$DIST_DIR/jarvis_1.0.0_all.deb" ]; then
        echo -n "Verifying .deb integrity... "
        dpkg-deb -I "$DIST_DIR/jarvis_1.0.0_all.deb" >/dev/null && echo -e "${GREEN}OK${NC}"
    fi
    if [ -f "$DIST_DIR/jarvis-installer.run" ]; then
        echo -n "Verifying .run installer... "
        "$DIST_DIR/jarvis-installer.run" --help >/dev/null && echo -e "${GREEN}OK${NC}"
    fi
fi

# Generate SHA256 checksums
echo -e "\n${BLUE}Generating SHA256 checksums...${NC}"
(
    cd "$DIST_DIR"
    rm -f SHA256SUMS
    sha256sum JARVIS-*.AppImage jarvis_*.deb jarvis-installer.run jarvis_pc-*.whl 2>/dev/null > SHA256SUMS || true
)
if [ -s "$DIST_DIR/SHA256SUMS" ]; then
    echo -e "  -> ${GREEN}Checksums saved to:${NC} dist/SHA256SUMS"
fi

# Print summary table
echo -e "\n${CYAN}=========================================================="
echo "                BUILD COMPLETE — SUMMARY"
echo -e "==========================================================${NC}"
printf "%-30s | %-10s | %s\n" "Artifact" "Size" "Install / Run Command"
echo "--------------------------------------------------------------------------------"
if [ -f "$DIST_DIR/JARVIS-x86_64.AppImage" ]; then
    SIZE=$(du -h "$DIST_DIR/JARVIS-x86_64.AppImage" | cut -f1)
    printf "%-30s | %-10s | %s\n" "dist/JARVIS-x86_64.AppImage" "$SIZE" "./dist/JARVIS-x86_64.AppImage"
fi
if [ -f "$DIST_DIR/jarvis_1.0.0_all.deb" ]; then
    SIZE=$(du -h "$DIST_DIR/jarvis_1.0.0_all.deb" | cut -f1)
    printf "%-30s | %-10s | %s\n" "dist/jarvis_1.0.0_all.deb" "$SIZE" "sudo apt install ./dist/jarvis_1.0.0_all.deb"
fi
if [ -f "$DIST_DIR/jarvis-installer.run" ]; then
    SIZE=$(du -h "$DIST_DIR/jarvis-installer.run" | cut -f1)
    printf "%-30s | %-10s | %s\n" "dist/jarvis-installer.run" "$SIZE" "./dist/jarvis-installer.run"
fi
if [ -f "$DIST_DIR/SHA256SUMS" ]; then
    SIZE=$(du -h "$DIST_DIR/SHA256SUMS" | cut -f1)
    printf "%-30s | %-10s | %s\n" "dist/SHA256SUMS" "$SIZE" "sha256sum -c dist/SHA256SUMS"
fi
echo -e "${CYAN}==========================================================${NC}\n"
