#!/usr/bin/env python3
"""Offline mock of the local NIST MS Search bridge (interface conformance only).

PURPOSE
-------
PyGCMS Pipeline delegates library searching to a separately licensed local NIST
MS Search installation. Reviewers and readers without that licence therefore
cannot exercise the candidate-preserving stage of the workflow.

This module is a TEST DOUBLE. It re-implements the *interface contract* of the
real bridge (the endpoints, the request payload, and the shape of the returned
ranked hit list) and returns SYNTHETIC candidates from a fictitious library
named MOCKLIB. It allows the complete workflow

    mzML -> deconvolution -> spectrum export -> ranked candidate import
         -> deterministic review -> candidate-preserving export

to be executed end-to-end with no NIST software, no NIST library, no NIST
spectra, and no vendor-native file.

WHAT THIS DOES AND DOES NOT ESTABLISH
-------------------------------------
This mock verifies SOFTWARE behaviour: that every returned candidate, with its
original rank, scores, and identifiers, survives selection, review, and export.

It does NOT establish, and must never be reported as establishing, any chemical
identification, any match-factor accuracy, or any equivalence with real NIST MS
Search output. MOCKLIB scores are fabricated constants chosen to probe software
behaviour. Results produced with --mode adversarial or --mode demo are stamped
"SYNTHETIC" in the library field of every hit and must not be used as
analytical results.

The adversarial fixture is deliberately constructed so that a naive
implementation FAILS it (see docs/MOCK_BRIDGE.md). A mock that could only pass
would demonstrate nothing.

USAGE
-----
    python scripts/mock_nist_bridge.py                     # demo mode, port 18789
    python scripts/mock_nist_bridge.py --mode adversarial  # edge-case fixture
    python scripts/mock_nist_bridge.py --port 18789 --host 127.0.0.1

Then open software/index.html, leave the bridge URL at http://127.0.0.1:18789,
press "Check bridge", run the analysis, and press "Run NIST search".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MOCK_LIBRARY_TAG = "MOCKLIB-SYNTHETIC-1.0"
MOCK_BANNER = "SYNTHETIC MOCK OUTPUT - NOT NIST MS SEARCH - NOT AN IDENTIFICATION"

# ---------------------------------------------------------------------------
# Fictitious library used in demo mode.
#
# Names are real pyrolysis-product names because compound names are facts and
# because the deterministic class rules must be exercised. The SCORES, RANKS,
# and the LIBRARY are fabricated. No NIST spectrum, no NIST match factor, and
# no NIST library record is reproduced here.
# ---------------------------------------------------------------------------
DEMO_POOL: list[dict[str, Any]] = [
    {"name": "Furfural", "formula": "C5H4O2", "cas": "98-01-1", "mw": 96},
    {"name": "2-Methylfuran", "formula": "C5H6O", "cas": "534-22-5", "mw": 82},
    {"name": "Pyrrole", "formula": "C4H5N", "cas": "109-97-7", "mw": 67},
    {"name": "Pyridine", "formula": "C5H5N", "cas": "110-86-1", "mw": 79},
    {"name": "Phenol", "formula": "C6H6O", "cas": "108-95-2", "mw": 94},
    {"name": "Guaiacol", "formula": "C7H8O2", "cas": "90-05-1", "mw": 124},
    {"name": "Toluene", "formula": "C7H8", "cas": "108-88-3", "mw": 92},
    {"name": "Naphthalene", "formula": "C10H8", "cas": "91-20-3", "mw": 128},
    {"name": "Benzaldehyde", "formula": "C7H6O", "cas": "100-52-7", "mw": 106},
    {"name": "Indole", "formula": "C8H7N", "cas": "120-72-9", "mw": 117},
    {"name": "Alkane-C16", "formula": "C16H34", "cas": "544-76-3", "mw": 226},
    {"name": "Hexadecanenitrile", "formula": "C16H31N", "cas": "629-79-8", "mw": 237},
    {"name": "Levoglucosan", "formula": "C6H10O5", "cas": "498-07-7", "mw": 162},
    {"name": "Acetophenone", "formula": "C8H8O", "cas": "98-86-2", "mw": 120},
    {"name": "Styrene", "formula": "C8H8", "cas": "100-42-5", "mw": 104},
    {"name": "MOCK-Unknown-Component", "formula": "", "cas": "", "mw": 0},
]

# ---------------------------------------------------------------------------
# Adversarial fixture. Each entry targets one preservation invariant.
# Keyed by 1-based query index.
# ---------------------------------------------------------------------------
ADVERSARIAL: dict[int, dict[str, Any]] = {
    1: {
        "probe": "near-tie: rank-2 must not be dropped or silently promoted",
        "hits": [
            {"name": "Furfural", "formula": "C5H4O2", "cas": "98-01-1", "mw": 96, "mf": 912, "rmf": 921, "prob": 41.2},
            {"name": "2-Furancarboxaldehyde, 5-methyl-", "formula": "C6H6O2", "cas": "620-02-0", "mw": 110, "mf": 909, "rmf": 917, "prob": 39.8},
            {"name": "2-Acetylfuran", "formula": "C6H6O2", "cas": "1192-62-7", "mw": 110, "mf": 874, "rmf": 880, "prob": 11.0},
        ],
    },
    2: {
        "probe": "class conflict: rank-1 and rank-2 belong to different NOM classes",
        "hits": [
            {"name": "Pyridine", "formula": "C5H5N", "cas": "110-86-1", "mw": 79, "mf": 886, "rmf": 890, "prob": 33.1},
            {"name": "Furfural", "formula": "C5H4O2", "cas": "98-01-1", "mw": 96, "mf": 883, "rmf": 888, "prob": 31.7},
            {"name": "Toluene", "formula": "C7H8", "cas": "108-88-3", "mw": 92, "mf": 810, "rmf": 815, "prob": 12.0},
        ],
    },
    3: {
        "probe": "all-weak: no candidate is defensible; component must stay unassigned",
        "hits": [
            {"name": "MOCK-Weak-Candidate-A", "formula": "", "cas": "", "mw": 0, "mf": 421, "rmf": 430, "prob": 3.1},
            {"name": "MOCK-Weak-Candidate-B", "formula": "", "cas": "", "mw": 0, "mf": 418, "rmf": 425, "prob": 2.9},
        ],
    },
    4: {
        "probe": "zero-hit: component must be retained as unidentified, not deleted",
        "hits": [],
    },
    5: {
        "probe": "missing CAS / missing formula fields must not corrupt the record",
        "hits": [
            {"name": "MOCK-NoCAS-Compound", "formula": "", "cas": "", "mw": 0, "mf": 795, "rmf": 800, "prob": 22.0},
            {"name": "Phenol", "formula": "C6H6O", "cas": "108-95-2", "mw": 94, "mf": 780, "rmf": 788, "prob": 19.5},
        ],
    },
    6: {
        "probe": "duplicate name at different ranks must both survive",
        "hits": [
            {"name": "Alkane-C16", "formula": "C16H34", "cas": "544-76-3", "mw": 226, "mf": 900, "rmf": 905, "prob": 30.0},
            {"name": "Alkane-C16", "formula": "C16H34", "cas": "544-76-3", "mw": 226, "mf": 899, "rmf": 904, "prob": 29.5},
        ],
    },
    7: {
        "probe": "deep list: max_candidates must be honoured without reordering",
        "hits": [
            {"name": f"MOCK-Depth-Probe-{i:02d}", "formula": "", "cas": "", "mw": 0,
             "mf": 950 - i * 7, "rmf": 955 - i * 7, "prob": max(0.1, 25.0 - i)}
            for i in range(1, 21)
        ],
    },
}


def _parse_msp(msp_text: str) -> list[dict[str, Any]]:
    """Split an MSP payload into query records, recovering the global index."""
    queries: list[dict[str, Any]] = []
    for raw_block in re.split(r"(?:\r?\n){2,}", msp_text.strip()):
        block = raw_block.strip()
        if not block:
            continue
        name_m = re.search(r"^Name:\s*(.+)$", block, re.M)
        if not name_m:
            continue
        header = name_m.group(1).strip()
        idx = None
        m = re.search(r"PyGCMS_Index\s*[=:]\s*(\d+)", block, re.I)
        if m:
            idx = int(m.group(1))
        if idx is None:
            m = re.search(r"PGCMS[_-]0*(\d+)", header, re.I)
            if m:
                idx = int(m.group(1))
        peaks = re.findall(r"(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)", block.split("Num Peaks:")[-1]) if "Num Peaks:" in block else []
        queries.append({"header": header, "query_index": idx, "n_peaks": len(peaks), "block": block})
    return queries


def _stable_pick(header: str, n_peaks: int, k: int) -> list[dict[str, Any]]:
    """Deterministically choose k demo candidates from a hash of the query."""
    digest = hashlib.sha256(f"{header}|{n_peaks}".encode("utf-8")).digest()
    start = digest[0] % len(DEMO_POOL)
    picks: list[dict[str, Any]] = []
    for i in range(k):
        base = DEMO_POOL[(start + i * 3) % len(DEMO_POOL)]
        mf = 940 - i * 23 - (digest[(i + 1) % len(digest)] % 17)
        mf = max(300, min(999, mf))
        picks.append({
            **base,
            "mf": mf,
            "rmf": min(999, mf + 6),
            "prob": round(max(0.1, 45.0 / (i + 1) - (digest[i % len(digest)] % 5)), 1),
        })
    return picks


def _build_groups(queries: list[dict[str, Any]], max_candidates: int, mode: str,
                  index_offset: int) -> tuple[list[dict[str, Any]], int]:
    groups: list[dict[str, Any]] = []
    total_hits = 0
    for pos, q in enumerate(queries):
        gidx = q["query_index"] if q["query_index"] else index_offset + pos + 1

        if mode == "adversarial":
            spec = ADVERSARIAL.get(gidx)
            if spec is None:
                continue  # unmapped indices deliberately return nothing
            raw = spec["hits"]
        else:
            raw = _stable_pick(q["header"], q["n_peaks"], max_candidates)

        hits = []
        for rank, h in enumerate(raw[:max_candidates], start=1):
            hits.append({
                "rank": rank,
                "name": h["name"],
                "formula": h.get("formula", ""),
                "mf": h["mf"],
                "rmf": h["rmf"],
                "prob": h["prob"],
                "cas": h.get("cas", ""),
                "mw": h.get("mw", 0),
                "lib": MOCK_LIBRARY_TAG,
                "id": f"MOCK{gidx:04d}{rank:02d}",
                "ri": "",
            })
        total_hits += len(hits)
        groups.append({"query_index": gidx, "header": q["header"], "hits": hits})
    return groups, total_hits


class MockBridgeHandler(BaseHTTPRequestHandler):
    server_version = "MockNISTBridge/1.0"
    mode = "demo"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[mock-bridge] " + (fmt % args) + "\n")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/health"):
            self._json({
                "ok": True,
                "mock": True,
                "mode": self.mode,
                "banner": MOCK_BANNER,
                "nistms_exists": True,
                "nistms": "<MOCK> no NIST MS Search executable is present",
                "nist_workdir": "<MOCK> no NIST working directory is present",
            })
            return
        self._json({"ok": False, "error": f"unknown endpoint {self.path}"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self._json({"ok": False, "error": f"invalid JSON: {exc}"}, 400)
            return

        path = self.path.rstrip("/")

        if path.endswith("/launch"):
            self._json({"ok": True, "mock": True, "banner": MOCK_BANNER,
                        "nistms": "<MOCK> launch is a no-op; no NIST software is invoked"})
            return

        if path.endswith("/search"):
            msp = payload.get("msp") or ""
            if not msp.strip():
                self._json({"ok": False, "error": "No MSP text supplied"}, 400)
                return
            max_candidates = int(payload.get("max_candidates") or 5)
            index_offset = int(payload.get("index_offset") or 0)
            queries = _parse_msp(msp)
            groups, n_hits = _build_groups(queries, max_candidates, self.mode, index_offset)
            self._json({
                "ok": True,
                "mock": True,
                "mode": self.mode,
                "banner": MOCK_BANNER,
                "groups": groups,
                "n_hits": n_hits,
                "srcready_count": len(queries),
                "raw_hit_lines": n_hits,
                "srcreslt": f"<MOCK> {len(queries)} query spectra, {n_hits} synthetic hits",
                "warning": None if groups else "Mock bridge returned no hits for this batch (expected in adversarial mode).",
            })
            return

        if path.endswith("/save_outputs"):
            files = payload.get("files") or []
            outdir = Path(payload.get("output_dir") or "mock_bridge_outputs")
            run_id = payload.get("run_id") or "mock_run"
            target = outdir / run_id if payload.get("make_run_subdir") else outdir
            target.mkdir(parents=True, exist_ok=True)
            saved = []
            for f in files:
                fp = target / Path(str(f.get("filename") or "output.csv")).name
                fp.write_text(str(f.get("content") or ""), encoding="utf-8")
                saved.append(str(fp))
            self._json({"ok": True, "mock": True, "saved_paths": saved})
            return

        self._json({"ok": False, "error": f"unknown endpoint {self.path}"}, 404)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=18789)
    ap.add_argument("--mode", choices=["demo", "adversarial"], default="demo",
                    help="demo: synthetic candidates for every spectrum. "
                         "adversarial: engineered edge cases for invariant testing.")
    args = ap.parse_args()

    MockBridgeHandler.mode = args.mode
    httpd = ThreadingHTTPServer((args.host, args.port), MockBridgeHandler)
    sys.stderr.write(
        f"\n{MOCK_BANNER}\n"
        f"[mock-bridge] mode={args.mode} listening on http://{args.host}:{args.port}\n"
        f"[mock-bridge] endpoints: /health /launch /search /save_outputs\n"
        f"[mock-bridge] No NIST software, library, or spectrum is used or reproduced.\n"
        f"[mock-bridge] Ctrl+C to stop.\n\n"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write("\n[mock-bridge] stopped.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
