from pathlib import Path


def test_no_shell_exec_tool():
    shell_tool = Path("tools/builtin/shell_exec.py")
    if shell_tool.exists():
        content = shell_tool.read_text()
        assert "shell=True" not in content


def test_no_sudo_in_camera_tools():
    camera_tool = Path("tools/builtin/camera.py")
    if camera_tool.exists():
        assert "sudo" not in camera_tool.read_text()
    media_tool = Path("src/jarvis/tools/builtin/media.py")
    assert "sudo" not in media_tool.read_text()
