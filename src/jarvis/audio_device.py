"""Audio Device and Bluetooth Microphone Management for JARVIS.

Detects connected Bluetooth headsets/microphones, automatically activates their
microphone profile (HSP/HFP), sets them as default input sources, and falls back to
system microphones seamlessly.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from typing import Optional, Tuple

logger = logging.getLogger("jarvis.audio_device")


def detect_and_configure_bluetooth_mic() -> Tuple[bool, str]:
    """Detect connected Bluetooth audio devices and configure microphone profile.

    Returns:
        Tuple of (is_bluetooth_active: bool, device_description: str)
    """
    if not shutil.which("pactl"):
        logger.debug("pactl binary not found, using system default audio device.")
        return False, "Default System Microphone"

    try:
        cards_out = subprocess.check_output(["pactl", "list", "cards"], text=True, stderr=subprocess.DEVNULL)
        cards = cards_out.split("Card #")

        bt_device_alias = "Bluetooth Headset"

        for card_chunk in cards:
            if "bluez_card" in card_chunk:
                card_name = None
                active_profile = None
                available_mic_profiles = []

                for line in card_chunk.splitlines():
                    line_str = line.strip()
                    if line_str.startswith("Name: "):
                        card_name = line_str.split("Name: ", 1)[1].strip()
                    elif line_str.startswith("device.alias = "):
                        bt_device_alias = line_str.split("=", 1)[1].strip().strip('"')
                    elif line_str.startswith("Active Profile: "):
                        active_profile = line_str.split("Active Profile: ", 1)[1].strip()
                    elif "sources: 1" in line_str:
                        prof_name = line_str.split(":")[0].strip()
                        available_mic_profiles.append(prof_name)

                if card_name and available_mic_profiles:
                    preferred = [
                        "headset-head-unit-msbc",
                        "headset-head-unit",
                        "headset-head-unit-cvsd",
                    ]
                    target_profile = next((p for p in preferred if p in available_mic_profiles), available_mic_profiles[0])

                    # Only switch if not already on a microphone profile
                    if active_profile != target_profile and (not active_profile or active_profile not in available_mic_profiles):
                        logger.info("Found Bluetooth device '%s'. Activating mic profile '%s'", bt_device_alias, target_profile)
                        subprocess.run(
                            ["pactl", "set-card-profile", card_name, target_profile],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        time.sleep(0.2)
                    else:
                        logger.debug("Bluetooth device '%s' already on mic profile '%s'", bt_device_alias, active_profile)

        # Look for active bluez input source and ensure it is default
        sources_out = subprocess.check_output(["pactl", "list", "sources", "short"], text=True, stderr=subprocess.DEVNULL)
        for line in sources_out.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                src_name = parts[1]
                if "bluez_input" in src_name:
                    subprocess.run(
                        ["pactl", "set-default-source", src_name],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    return True, f"Bluetooth Microphone ({bt_device_alias})"

    except Exception as err:
        logger.warning("Error configuring bluetooth microphone: %s", err)

    return False, "Built-in / Default System Microphone"


def get_active_microphone_name() -> str:
    """Get human-readable description of current active input device."""
    try:
        if shutil.which("pactl"):
            sources_out = subprocess.check_output(["pactl", "list", "sources", "short"], text=True, stderr=subprocess.DEVNULL)
            for line in sources_out.splitlines():
                if "bluez_input" in line:
                    return "Bluetooth Microphone (Active)"
    except Exception:
        pass
    return "Default System Microphone"
