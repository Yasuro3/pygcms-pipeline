#!/usr/bin/env python3
"""Verify that the mock NIST bridge honours the bridge interface contract.

This test requires no browser, no NIST software, and no network access beyond
the local loopback interface. It checks that the mock returns the exact
structure the application's importer expects, and that the adversarial fixture
really does contain the edge cases it claims to contain.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "mock_nist_bridge.py"
PORT = 18991
BASE = f"http://127.0.0.1:{PORT}"

MSP = "\r\n".join([
    "Name: PGCMS_0001_RT_5.120_SCAN_614",
    "Comment: PyGCMS_Index=1 RT_min=5.120 Scan=614 TIC=120345 PureIons=12",
    "Num Peaks: 3",
    "39 210; 95 999; 96 610",
    "",
    "Name: PGCMS_0002_RT_6.480_SCAN_778",
    "Comment: PyGCMS_Index=2 RT_min=6.480 Scan=778 TIC=98110 PureIons=9",
    "Num Peaks: 3",
    "52 300; 79 999; 80 120",
    "",
    "Name: PGCMS_0004_RT_8.900_SCAN_1068",
    "Comment: PyGCMS_Index=4 RT_min=8.900 Scan=1068 TIC=41000 PureIons=5",
    "Num Peaks: 2",
    "57 999; 71 480",
    "",
])

REQUIRED_HIT_KEYS = {"rank", "name", "formula", "mf", "rmf", "prob", "cas", "mw", "lib", "id", "ri"}


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_up(proc: subprocess.Popen, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise SystemExit("mock bridge exited prematurely")
        try:
            get("/health")
            return
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.15)
    raise SystemExit("mock bridge did not start in time")


def check_demo() -> None:
    health = get("/health")
    assert health.get("ok") is True, health
    assert health.get("mock") is True, "health must self-identify as a mock"
    assert "SYNTHETIC" in health.get("banner", ""), "health must carry the synthetic banner"

    data = post("/search", {"msp": MSP, "max_candidates": 5, "index_offset": 0,
                            "filename": "t.msp", "source_name": "t"})
    assert data.get("ok") is True, data
    groups = data.get("groups") or []
    assert len(groups) == 3, f"expected 3 groups, got {len(groups)}"

    seen = sorted(g["query_index"] for g in groups)
    assert seen == [1, 2, 4], f"query indices must be recovered from the MSP Comment: {seen}"

    for g in groups:
        hits = g["hits"]
        assert 1 <= len(hits) <= 5, f"max_candidates not honoured: {len(hits)}"
        ranks = [h["rank"] for h in hits]
        assert ranks == sorted(ranks) and ranks[0] == 1, f"ranks must be 1..N ascending: {ranks}"
        for h in hits:
            missing = REQUIRED_HIT_KEYS - set(h)
            assert not missing, f"hit is missing contract keys: {missing}"
            assert h["lib"].startswith("MOCKLIB"), "every hit must be labelled as mock library output"
            assert 0 <= h["mf"] <= 999, f"MF out of range: {h['mf']}"
    print("PASS: demo mode conforms to the bridge contract and is labelled synthetic.")


def check_adversarial() -> None:
    data = post("/search", {"msp": MSP, "max_candidates": 15, "index_offset": 0,
                            "filename": "t.msp", "source_name": "t"})
    assert data.get("ok") is True, data
    by_idx = {g["query_index"]: g["hits"] for g in (data.get("groups") or [])}

    assert 1 in by_idx, "adversarial fixture must map query 1 (near-tie probe)"
    near = by_idx[1]
    assert len(near) >= 2, "near-tie probe must supply at least two candidates"
    gap = near[0]["mf"] - near[1]["mf"]
    assert 0 <= gap <= 5, f"near-tie probe must be a genuine near-tie, gap={gap}"

    assert 2 in by_idx, "adversarial fixture must map query 2 (class-conflict probe)"
    names = [h["name"] for h in by_idx[2]]
    assert "Pyridine" in names[0] and "Furfural" in names[1], \
        "class-conflict probe must place different NOM classes at rank 1 and 2"

    assert 4 in by_idx, "zero-hit probe must still return a group"
    assert by_idx[4] == [], "zero-hit probe must return an empty hit list, not a fabricated hit"

    print("PASS: adversarial fixture contains genuine near-tie, class-conflict, and zero-hit probes.")


def main() -> int:
    for mode, check in (("demo", check_demo), ("adversarial", check_adversarial)):
        proc = subprocess.Popen(
            [sys.executable, str(BRIDGE), "--port", str(PORT), "--mode", mode],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            wait_up(proc)
            check()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    print("PASS: mock NIST bridge contract verified without NIST software or a browser.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
