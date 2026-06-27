"""
Smoke tests for podbill/invoice_minutes.py

Tests cover:
  - billable_minutes() rounding modes (nearest / up / down)
  - mmss() formatting
  - collect_files() directory scanning and --since filtering
  - Full CLI output format (summary table) via subprocess, with ffprobe patched
  - --html-rows output format
  - --help exits cleanly

All tests are read-only and use temp directories — no real client or financial
data is touched.
"""
import math
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

# Put the package on the path so we can import without installing.
sys.path.insert(0, str(Path(__file__).parent.parent))
from podbill.invoice_minutes import (
    billable_minutes,
    collect_files,
    main,
    mmss,
    probe_duration_seconds,
)


# ---------------------------------------------------------------------------
# billable_minutes — core billing math
# ---------------------------------------------------------------------------

class TestBillableMinutes:
    """billable_minutes(seconds, mode) -> integer minutes, always >= 1."""

    def test_nearest_rounds_down(self):
        # 89.9 s = 1.498 min → rounds to 1
        assert billable_minutes(89.9, "nearest") == 1

    def test_nearest_rounds_up(self):
        # 90.0 s = 1.5 min → rounds to 2
        assert billable_minutes(90.0, "nearest") == 2

    def test_nearest_exact_minute(self):
        # 120 s = 2.0 min → 2
        assert billable_minutes(120.0, "nearest") == 2

    def test_nearest_typical_episode(self):
        # 2505 s = 41:45 → 42 min (as shown in the README example)
        assert billable_minutes(2505.0, "nearest") == 42

    def test_round_up_always_rounds_up(self):
        # 61 s = 1.017 min → ceil = 2
        assert billable_minutes(61.0, "up") == 2

    def test_round_up_exact_minute(self):
        # Exact minutes don't get bumped; 120 s = 2.0 → 2
        assert billable_minutes(120.0, "up") == 2

    def test_round_down_truncates(self):
        # 119 s = 1.98 min → int = 1
        assert billable_minutes(119.0, "down") == 1

    def test_round_down_exact_minute(self):
        assert billable_minutes(180.0, "down") == 3

    def test_minimum_is_one_nearest(self):
        # Sub-30-second clip should still bill 1 min
        assert billable_minutes(10.0, "nearest") == 1

    def test_minimum_is_one_up(self):
        assert billable_minutes(1.0, "up") == 1

    def test_minimum_is_one_down(self):
        assert billable_minutes(5.0, "down") == 1

    def test_amount_calculation(self):
        # 42 billable mins × $2.00 = $84.00  (README example: Ep 12)
        mins = billable_minutes(2505.0, "nearest")  # 41:45
        assert round(mins * 2.00, 2) == 84.00

    def test_readme_example_ep13(self):
        # 35:36 = 2136 s → nearest = 36 → $72.00
        assert billable_minutes(2136.0, "nearest") == 36
        assert round(36 * 2.00, 2) == 72.00

    def test_readme_total(self):
        # Ep12 $84 + Ep13 $72 = $156  (the README banner example)
        ep12 = round(billable_minutes(2505.0, "nearest") * 2.00, 2)
        ep13 = round(billable_minutes(2136.0, "nearest") * 2.00, 2)
        assert ep12 + ep13 == 156.00


# ---------------------------------------------------------------------------
# mmss — time formatting
# ---------------------------------------------------------------------------

class TestMmss:
    def test_zero(self):
        assert mmss(0.0) == "0:00"

    def test_one_minute(self):
        assert mmss(60.0) == "1:00"

    def test_full_episode(self):
        # 41:45 from README example
        assert mmss(2505.0) == "41:45"

    def test_seconds_padding(self):
        # 1:05 not 1:5
        assert mmss(65.0) == "1:05"

    def test_hour_plus(self):
        # 90 minutes = 1:30:00 → displayed as 90:00 (no hours column)
        assert mmss(5400.0) == "90:00"

    def test_rounding_at_boundary(self):
        # 59.5 s → round → 60 s → 1:00
        assert mmss(59.5) == "1:00"


# ---------------------------------------------------------------------------
# collect_files — directory scanning + --since filter
# ---------------------------------------------------------------------------

class TestCollectFiles:
    def test_collects_audio_files(self, tmp_path):
        (tmp_path / "ep01.mp3").touch()
        (tmp_path / "ep02.wav").touch()
        (tmp_path / "notes.txt").touch()  # should be skipped
        from podbill.invoice_minutes import AUDIO_EXTS
        files = collect_files([str(tmp_path)], since=None, exts=AUDIO_EXTS)
        names = {f.name for f in files}
        assert names == {"ep01.mp3", "ep02.wav"}

    def test_skips_macos_dot_underscore_files(self, tmp_path):
        (tmp_path / "._ep01.mp3").touch()
        (tmp_path / "ep01.mp3").touch()
        from podbill.invoice_minutes import AUDIO_EXTS
        files = collect_files([str(tmp_path)], since=None, exts=AUDIO_EXTS)
        assert all(not f.name.startswith("._") for f in files)

    def test_since_filter_excludes_old_files(self, tmp_path):
        old_file = tmp_path / "old.mp3"
        new_file = tmp_path / "new.mp3"
        old_file.touch()
        new_file.touch()
        # Backdate old_file to yesterday
        yesterday = (datetime.now() - timedelta(days=1)).timestamp()
        import os
        os.utime(old_file, (yesterday, yesterday))

        since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from podbill.invoice_minutes import AUDIO_EXTS
        files = collect_files([str(tmp_path)], since=since, exts=AUDIO_EXTS)
        names = {f.name for f in files}
        assert "new.mp3" in names
        assert "old.mp3" not in names

    def test_explicit_file_path(self, tmp_path):
        ep = tmp_path / "ep01.mp3"
        ep.touch()
        from podbill.invoice_minutes import AUDIO_EXTS
        files = collect_files([str(ep)], since=None, exts=AUDIO_EXTS)
        assert len(files) == 1
        assert files[0].name == "ep01.mp3"

    def test_nonexistent_path_is_skipped(self, tmp_path, capsys):
        from podbill.invoice_minutes import AUDIO_EXTS
        files = collect_files([str(tmp_path / "ghost.mp3")], since=None, exts=AUDIO_EXTS)
        assert files == []


# ---------------------------------------------------------------------------
# Full CLI integration (main()) — ffprobe patched, no real media files needed
# ---------------------------------------------------------------------------

FAKE_FILES = [
    # (filename, duration_seconds)  — from the README banner example
    ("Acme Ep 12 - Burnout.mp3",  2505.0),   # 41:45 → 42 min → $84.00
    ("Acme Ep 13 - Hiring.mp3",   2136.0),   # 35:36 → 36 min → $72.00
]


def _fake_probe(path):
    """Return a canned duration keyed by filename."""
    durations = dict(FAKE_FILES)
    return durations.get(Path(path).name)


class TestMainSummaryOutput:
    def test_summary_totals(self, tmp_path, capsys, monkeypatch):
        """Main prints the right total for the README example."""
        for name, _ in FAKE_FILES:
            (tmp_path / name).touch()

        monkeypatch.setattr("podbill.invoice_minutes.probe_duration_seconds", _fake_probe)

        rc = main.__wrapped__ if hasattr(main, "__wrapped__") else main
        # Call via sys.argv patch
        with patch("sys.argv", ["podbill", str(tmp_path), "--rate", "2.00"]):
            exit_code = main()

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "$156.00" in out
        assert "42" in out   # Ep 12 rounded minutes
        assert "36" in out   # Ep 13 rounded minutes

    def test_html_rows_output(self, tmp_path, capsys, monkeypatch):
        """--html-rows produces <tr> markup and an HTML comment with the subtotal."""
        for name, _ in FAKE_FILES:
            (tmp_path / name).touch()

        monkeypatch.setattr("podbill.invoice_minutes.probe_duration_seconds", _fake_probe)

        with patch("sys.argv", ["podbill", str(tmp_path), "--rate", "2.00", "--html-rows"]):
            exit_code = main()

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "<tr>" in out
        assert "$84.00" in out
        assert "$72.00" in out
        assert "<!-- Subtotal: $156.00" in out

    def test_round_up_mode(self, tmp_path, capsys, monkeypatch):
        """--round up should ceil every duration."""
        (tmp_path / "ep.mp3").touch()
        monkeypatch.setattr(
            "podbill.invoice_minutes.probe_duration_seconds",
            lambda p: 61.0  # 1.017 min → ceil = 2
        )

        with patch("sys.argv", ["podbill", str(tmp_path), "--rate", "1.00", "--round", "up"]):
            exit_code = main()

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "$2.00" in out

    def test_custom_rate(self, tmp_path, capsys, monkeypatch):
        """--rate 2.50 × 36 min = $90.00."""
        (tmp_path / "ep.mp3").touch()
        monkeypatch.setattr(
            "podbill.invoice_minutes.probe_duration_seconds",
            lambda p: 2136.0  # → 36 min nearest
        )

        with patch("sys.argv", ["podbill", str(tmp_path), "--rate", "2.50"]):
            exit_code = main()

        assert exit_code == 0
        out = capsys.readouterr().out
        assert "$90.00" in out

    def test_no_files_returns_nonzero(self, tmp_path, monkeypatch):
        """Empty folder should exit non-zero."""
        # no files created
        with patch("sys.argv", ["podbill", str(tmp_path)]):
            exit_code = main()
        assert exit_code != 0

    def test_bad_since_flag_returns_nonzero(self, tmp_path):
        """--since with a bad date should exit 2."""
        with patch("sys.argv", ["podbill", str(tmp_path), "--since", "not-a-date"]):
            exit_code = main()
        assert exit_code == 2


# ---------------------------------------------------------------------------
# CLI subprocess — --help smoke test
# ---------------------------------------------------------------------------

class TestCLIHelp:
    def test_help_exits_cleanly(self):
        result = subprocess.run(
            [sys.executable, "podbill/invoice_minutes.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode == 0
        assert "usage" in result.stdout.lower()
        assert "--rate" in result.stdout
        assert "--round" in result.stdout
        assert "--since" in result.stdout
