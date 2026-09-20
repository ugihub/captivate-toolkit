import struct

from captivate_toolkit.cli import main


def test_help_returns_zero(capsys):
    assert main(["--help"]) == 0
    assert "extract" in capsys.readouterr().out


def test_extract_command_writes_manifest_and_swf(tmp_path, capsys):
    source = tmp_path / "lesson.exe"
    body = b"A" * 40
    source.write_bytes(b"prefix" + b"FWS" + bytes([9]) + struct.pack("<I", len(body) + 8) + body)

    assert main(["extract", str(source), "--out", str(tmp_path / "output")]) == 0

    job = tmp_path / "output" / "lesson"
    assert (job / "swf" / "main.swf").exists()
    assert (job / "manifest.json").exists()
    assert "[ok]" in capsys.readouterr().out


def test_extract_batch_returns_failure_when_one_input_fails(tmp_path):
    source = tmp_path / "valid.exe"
    body = b"A" * 40
    source.write_bytes(b"FWS" + bytes([9]) + struct.pack("<I", len(body) + 8) + body)

    assert (
        main(
            [
                "extract",
                str(source),
                str(tmp_path / "missing.exe"),
                "--out",
                str(tmp_path / "output"),
            ]
        )
        == 1
    )
