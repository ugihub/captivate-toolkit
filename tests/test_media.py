import json

from captivate_toolkit.media import probe_media


def test_probe_media_parses_audio_and_video(tmp_path, monkeypatch):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"placeholder")

    payload = {
        "streams": [
            {"codec_type": "video", "codec_name": "h264", "width": 1024, "height": 776},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
        "format": {"duration": "12.5"},
    }
    monkeypatch.setattr(
        "captivate_toolkit.media.run_command",
        lambda *args, **kwargs: type(
            "Result", (), {"stdout": json.dumps(payload), "returncode": 0}
        )(),
    )

    info = probe_media(media)

    assert info.duration == 12.5
    assert info.has_audio is True
    assert info.video_codec == "h264"
