#!/usr/bin/env python3
"""
invoice_minutes.py — read audio durations from files and emit invoice-ready
billable-minute line items. Works on any folder of finished episodes, so you
never read a runtime off a dashboard to bill a client again.

Examples:
    # Whole folder, default $2.00/min, nearest-minute rounding:
    python3 invoice_minutes.py "/path/to/finished episodes"

    # Specific files:
    python3 invoice_minutes.py ep01.wav ep02.wav ep03.wav

    # Only files modified on/after a billing-period start, round UP, $2.50/min:
    python3 invoice_minutes.py <folder> --since 2026-06-01 --round up --rate 2.50

    # Emit <tr> rows ready to paste into templates/invoice.html:
    python3 invoice_minutes.py <folder> --html-rows

Reads durations via ffprobe (already a pipeline dependency). Pure read-only —
it never modifies, moves, or deletes any audio file.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


def probe_duration_seconds(path: Path) -> float | None:
    """Return media duration in seconds via ffprobe, or None if unreadable."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=60,
        )
        val = out.stdout.strip()
        return float(val) if val else None
    except (subprocess.SubprocessError, ValueError):
        return None


def billable_minutes(seconds: float, mode: str) -> int:
    minutes = seconds / 60.0
    if mode == "up":
        import math
        return max(1, math.ceil(minutes))
    if mode == "down":
        return max(1, int(minutes))
    return max(1, round(minutes))  # nearest


def mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def collect_files(inputs, since: datetime | None, exts: set[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        p = Path(os.path.expanduser(raw))
        if p.is_dir():
            files.extend(c for c in sorted(p.iterdir())
                         if c.suffix.lower() in exts and not c.name.startswith("._"))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  (skipped, not found: {p})", file=sys.stderr)
    if since:
        files = [f for f in files
                 if datetime.fromtimestamp(f.stat().st_mtime) >= since]
    return files


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit invoice-ready billable minutes from audio files.")
    ap.add_argument("inputs", nargs="+", help="audio file(s) and/or folder(s)")
    ap.add_argument("--rate", type=float, default=2.00, help="per-minute rate (default 2.00)")
    ap.add_argument("--round", dest="rounding", choices=["nearest", "up", "down"],
                    default="nearest", help="minute rounding (default nearest)")
    ap.add_argument("--since", help="only files modified on/after YYYY-MM-DD")
    ap.add_argument("--html-rows", action="store_true",
                    help="print <tr> rows for the Invoice-XX HTML template")
    ap.add_argument("--include-video", action="store_true",
                    help="also count video files (.mp4/.mov); off by default to avoid double-billing the audio+video of one episode")
    args = ap.parse_args()

    exts = set(AUDIO_EXTS) | (VIDEO_EXTS if args.include_video else set())

    since = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            print(f"error: --since must be YYYY-MM-DD, got {args.since!r}", file=sys.stderr)
            return 2

    files = collect_files(args.inputs, since, exts)
    if not files:
        print("No audio files found.", file=sys.stderr)
        return 1

    rows = []
    total_amount = 0.0
    unreadable = []
    for f in files:
        secs = probe_duration_seconds(f)
        if secs is None:
            unreadable.append(f.name)
            continue
        mins = billable_minutes(secs, args.rounding)
        amount = round(mins * args.rate, 2)
        total_amount += amount
        rows.append((f.name, mmss(secs), mins, amount))

    if args.html_rows:
        for name, dur, mins, amount in rows:
            label = Path(name).stem.replace("&", "&amp;")
            print(f'      <tr>\n        <td>{label} ({dur})</td>\n'
                  f'        <td>{mins}</td>\n        <td>${args.rate:.2f}</td>\n'
                  f'        <td>${amount:.2f}</td>\n      </tr>')
        print(f"\n<!-- Subtotal: ${total_amount:.2f}  (rate ${args.rate:.2f}/min, "
              f"{args.rounding} rounding) -->")
    else:
        print(f"\n{'File':<52} {'Runtime':>8} {'Min':>4} {'Amount':>9}")
        print("-" * 76)
        for name, dur, mins, amount in rows:
            disp = (name[:49] + "…") if len(name) > 50 else name
            print(f"{disp:<52} {dur:>8} {mins:>4} {'$'+format(amount,'.2f'):>9}")
        print("-" * 76)
        print(f"{'TOTAL ('+str(len(rows))+' items, $'+format(args.rate,'.2f')+'/min, '+args.rounding+')':<66} "
              f"{'$'+format(total_amount,'.2f'):>9}")

    if unreadable:
        print(f"\n⚠️  Unreadable (skipped): {', '.join(unreadable)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
