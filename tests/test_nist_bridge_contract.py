#!/usr/bin/env python3
"""Test the licensed NIST bridge contract without launching licensed software.

The test exercises the public HTTP endpoints with a stubbed search backend. It
checks that the released app is served, ``max_candidates`` is propagated to the
backend, and parsed candidate fields keep the response shape expected by the
browser. It does not claim to validate NIST MS Search itself.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import nist_mssearch_bridge as bridge  # noqa: E402
import nist_mssearch_bridge_server as server  # noqa: E402

MSP = "\r\n".join([
    "Name: PGCMS_0007_RT_5.120_SCAN_614",
    "Comment: PyGCMS_Index=7 RT_min=5.120 Scan=614",
    "Num Peaks: 3",
    "39 210; 95 999; 96 610",
    "",
])

SRCRESLT = "\n".join([
    "Unknown: PGCMS_0007_RT_5.120_SCAN_614 Compound in Library Factor = 0.9",
    "Hit 1 : <<Phenol>>; <<C6H6O>>; MF: 874; RMF: 921; Prob: 62.4; CAS: 108-95-2; Mw: 94; Lib: <<mainlib>>; Id: 12345; RI: 980.",
    "Hit 2 : <<2-Methylphenol>>; <<C7H8O>>; MF: 852; RMF: 904; Prob: 23.1; CAS: 95-48-7; Mw: 108; Lib: <<mainlib>>; Id: 23456; RI: 1015.",
])


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parsed = bridge.parse_srcreslt_text(SRCRESLT)
    assert len(parsed) == 2, parsed
    assert parsed[0].name == "Phenol"
    assert parsed[0].mf == 874
    assert parsed[1].rank == 2
    assert parsed[1].cas == "95-48-7"

    captured: dict[str, int] = {}
    original_search_hits = server.search_hits

    def fake_search_hits(*, msp: Path, nistms: Path, backend: str, n_hits: int, **kwargs):
        assert msp.exists(), "bridge did not stage the MSP payload"
        assert nistms.exists(), "test NIST executable placeholder missing"
        captured["n_hits"] = n_hits
        return parsed[:n_hits], "dll"

    with tempfile.TemporaryDirectory() as tmp_text:
        tmp = Path(tmp_text)
        fake_nist = tmp / "NISTMS$.EXE"
        fake_nist.write_bytes(b"test placeholder")
        work = tmp / "bridge_work"
        work.mkdir()

        server.STATE = server.AppState(
            nistms=fake_nist,
            nist_workdir=tmp,
            port=0,
            host="127.0.0.1",
            bridge_workdir=work,
            create_autoimp=False,
            default_timeout=5.0,
        )
        server.search_hits = fake_search_hits
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        try:
            health = request_json(base + "/health")
            assert health["ok"] is True
            assert health["service"] == "PyGCMS Pipeline"
            assert health["version"] == "1.3.0"
            assert health["nistms_exists"] is True

            with urllib.request.urlopen(base + "/app", timeout=15) as response:
                html = response.read().decode("utf-8")
            assert "PyGCMS Pipeline" in html
            assert "softwareVersion:'1.3.0'" in html

            data = request_json(base + "/search", {
                "msp": MSP,
                "filename": "contract_test.msp",
                "source_name": "contract_test",
                "max_candidates": 7,
                "reset_csv": True,
            })
            assert data["ok"] is True, data
            assert captured.get("n_hits") == 7, captured
            assert data["n_hits"] == 2
            assert len(data["groups"]) == 1
            hits = data["groups"][0]["hits"]
            assert [h["rank"] for h in hits] == [1, 2]
            assert hits[0]["name"] == "Phenol"
            assert hits[0]["lib"] == "mainlib"
            assert Path(data["csv_path"]).exists()
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            server.search_hits = original_search_hits
            server.STATE = None

    print("PASS: licensed NIST bridge HTTP contract and max-candidate propagation verified with a stub backend.")
    print("NOTE: licensed NIST MS Search itself was not launched by this test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
