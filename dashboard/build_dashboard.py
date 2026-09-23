"""
build_dashboard.py -- inline data.json into template.html to produce ONE
self-contained file that opens offline with a double-click.

    python build_data.py        # read both studies -> data.json
    python build_dashboard.py   # data.json + template.html -> index.html

No build step, no bundler, no CDN for the data: the payload ships inside the
page. The only network request the page makes is the Google Fonts stylesheet,
and it degrades to the system sans stack without it.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
DATA = HERE / "data.json"
OUT = HERE / "index.html"

PLACEHOLDER = "__DATA__"


def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    raw = DATA.read_text(encoding="utf-8")

    # Validate before inlining -- a malformed payload should fail here, not in
    # the browser with a blank page.
    payload = json.loads(raw)
    n_ports = len(payload["portfolios"])
    n_wins = len(payload["windows"])
    n_months = len(payload["panel"]["dates"])

    if PLACEHOLDER not in html:
        raise SystemExit(f"template.html has no {PLACEHOLDER} placeholder")

    # `</script>` cannot appear inside a <script> element, and a lone `<!--`
    # would open an HTML comment. Neither occurs in this data, but the escape
    # is free and makes the step safe for any future field.
    safe = raw.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")

    OUT.write_text(html.replace(PLACEHOLDER, safe), encoding="utf-8")

    kb = OUT.stat().st_size / 1024
    print(f"[ok] {OUT}")
    print(f"     {n_ports} portfolios | {n_wins} windows | {n_months} months | {kb:,.0f} KB")


if __name__ == "__main__":
    main()
