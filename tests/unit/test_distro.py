import pytest
from jarvis.system.distro import detect_distribution, LinuxDistribution


def test_detect_distribution():
    distro = detect_distribution()
    assert isinstance(distro, LinuxDistribution)
    assert distro.id != ""
