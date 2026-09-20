from captivate_toolkit.analysis import AnalysisOptions, analyze_video, select_frame_indices
from captivate_toolkit.config import Settings
from captivate_toolkit.media import MediaInfo


def test_sampling_covers_entire_video():
    indexes = select_frame_indices(total=23, limit=12)

    assert len(indexes) == 12
    assert indexes == sorted(set(indexes))
    assert indexes[0] == 0
    assert indexes[-1] == 22


def test_sampling_one_frame_uses_middle():
    assert select_frame_indices(total=9, limit=1) == [4]


def test_no_audio_is_reported_as_skipped(monkeypatch, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    frame = tmp_path / "frame.jpg"
    frame.write_bytes(b"jpeg")

    monkeypatch.setattr(
        "captivate_toolkit.analysis.probe_media",
        lambda _: MediaInfo(10.0, False, True, "h264", 640, 480),
    )
    monkeypatch.setattr("captivate_toolkit.analysis.extract_frames", lambda *args: [frame])

    class Response:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": "notes"})()})()]

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return Response()

    result = analyze_video(
        video,
        tmp_path / "analysis",
        settings=Settings(api_key="", vision_model="vision", text_model="text"),
        options=AnalysisOptions(skip_transcription=True),
        client=FakeClient(),
    )

    assert "dilewati" in result.warnings[0]
    assert result.vision_notes_path.read_text(encoding="utf-8") == "notes"
    assert result.summary_path.exists()
