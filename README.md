# podbill

**Bill your podcast clients by the finished minute — without reading runtimes off a dashboard.**

`podbill` is a tiny, dependency-light CLI for freelance podcast editors and producers. Point it
at a folder of finished episodes and it reads each file's exact duration, applies your per-minute
rate, and hands you a clean billable-minutes table — or paste-ready invoice rows.

No accounts, no SaaS, no telemetry. Just one Python file and `ffmpeg`.

```
$ podbill "~/Clients/Acme Pod/finished" --since 2026-06-01 --rate 2.00

File                                                  Runtime  Min    Amount
----------------------------------------------------------------------------
Acme Ep 12 - Burnout.mp3                                41:45   42    $84.00
Acme Ep 13 - Hiring.mp3                                 35:36   36    $72.00
----------------------------------------------------------------------------
TOTAL (2 items, $2.00/min, nearest)                                  $156.00
```

## Why

Editors who bill by audio minute usually do this by hand: open each file, read the runtime,
round it, multiply, retype it into an invoice. `podbill` removes that whole step. It reads the
*actual* duration straight from the files you already organize, so the number is always right.

## Install

```bash
# Requires Python 3.10+ and ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`)
git clone https://github.com/<you>/podbill && cd podbill
python3 podbill/invoice_minutes.py --help
```

## Usage

```bash
# A whole folder, default $2.00/min, nearest-minute rounding:
podbill "/path/to/finished episodes"

# Only this billing period, round up, custom rate:
podbill ./episodes --since 2026-06-01 --round up --rate 2.50

# Emit ready-to-paste invoice <tr> rows (drop into templates/invoice.html):
podbill ./episodes --html-rows
```

| Flag | Default | Does |
|---|---|---|
| `--rate` | `2.00` | Per-minute rate |
| `--round` | `nearest` | `nearest` \| `up` \| `down` |
| `--since` | — | Only files modified on/after `YYYY-MM-DD` (one billing period) |
| `--html-rows` | off | Print invoice table rows instead of a summary |
| `--include-video` | off | Also count `.mp4/.mov` (off by default so audio+video of one episode aren't double-billed) |

It's **read-only** — it never moves, renames, or deletes a file.

## Turn it into an invoice

`templates/invoice.html` is a clean, self-contained invoice you can drop the `--html-rows`
output into, then print to PDF from any browser (or render headlessly with
[WeasyPrint](https://weasyprint.org) / wkhtmltopdf). No design work required.

## Roadmap

- A one-command `podbill invoice` that goes folder → PDF in a single step
- Remembering what's already been billed, so it never double-counts

## Pairs with Showsmith

`podbill` is the billing sliver of a bigger toolkit. If you want the whole operator workflow —
ingest, transcribe, suggest cuts, generate show notes and social copy, master, and publish —
that's **Showsmith** (in the works). `podbill` is free, standalone, and always will be.

## License

MIT © Ian Phillip / Trilogy Works. Use it, fork it, bill with it.
