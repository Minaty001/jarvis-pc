import io
import zipfile
from unittest.mock import patch
import numpy as np
import pytest

from jarvis.voice.wake_word import WakeWordDetector, download_vosk_model


def test_wake_word_fails_closed_when_recognizer_none():
    """Verify detector never fires on loud audio frames if recognizer/model is absent."""
    with patch("jarvis.voice.wake_word.get_model", return_value=None):
        detector = WakeWordDetector()
        assert not detector.is_available
        # Generate high-amplitude / loud audio frame
        loud_pcm = (np.ones(1280, dtype=np.int16) * 30000).tobytes()
        assert detector.feed(loud_pcm) is False


def test_download_vosk_model_rejects_path_traversal(tmp_path):
    """Verify zip extraction prevents directory traversal attacks."""
    # Create an in-memory zip archive with a malicious traversal entry
    zip_bytes_io = io.BytesIO()
    with zipfile.ZipFile(zip_bytes_io, "w") as zf:
        zf.writestr("../../../evil.txt", "malicious payload")
    zip_data = zip_bytes_io.getvalue()

    target_dir = str(tmp_path / "models" / "vosk-model-small-en-us-0.15")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = patch("urllib.request.urlopen").start()
        mock_resp.return_value.__enter__.return_value.read.return_value = zip_data

        success = download_vosk_model(target_dir=target_dir)
        # Should fail safely without writing outside the target dir
        assert success is False
        assert not (tmp_path.parent / "evil.txt").exists()
