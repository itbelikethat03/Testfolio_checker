"""
manifest.py -- a record of which script produced the outputs in a folder, when,
and under which data configuration.

Every study script calls `record()` after writing its outputs. The dashboard
build reads the manifests and refuses to mix outputs produced under different
configurations (for example one phase run on the Ken French small-value series
and another on testfolio's), which is how stale outputs are caught instead of
silently combined.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

NAME = "_manifest.json"


def read(outdir) -> dict:
    p = Path(outdir) / NAME
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def record(outdir, script: str, **config) -> None:
    """Add or replace `script`'s entry in `outdir`'s manifest."""
    p = Path(outdir) / NAME
    m = read(outdir)
    m[script] = dict(run_at=datetime.now().isoformat(timespec="seconds"),
                     **{k: v for k, v in config.items()})
    p.write_text(json.dumps(m, indent=2, sort_keys=True, default=str), encoding="utf-8")


def check(outdir, scripts: list[str], **expected) -> list[str]:
    """Problems with `outdir`'s outputs: a script that never recorded a run, or
    one whose recorded config differs from `expected`. Empty list = consistent."""
    m = read(outdir)
    out = []
    for s in scripts:
        if s not in m:
            out.append(f"{s}: no manifest entry (outputs predate the manifest -- re-run it)")
            continue
        for k, v in expected.items():
            if m[s].get(k) != v:
                out.append(f"{s}: ran with {k}={m[s].get(k)!r}, current config is {v!r}")
    return out
