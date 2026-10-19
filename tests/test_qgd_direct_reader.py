#!/usr/bin/env python3
"""Browser regression test for the direct Shimadzu-QGD reader.

Builds a tiny synthetic OLE2/QGD-shaped compound document at runtime with an
interleaved dense full-scan-like channel and a sparse secondary channel.  No
vendor data are redistributed by this test.
"""
from __future__ import annotations

import struct
import sys
import tempfile
from pathlib import Path

from browser_utils import launch_chromium

SKIP = 77
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("SKIP: playwright is not installed.")
    raise SystemExit(SKIP)

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "software" / "index.html"

FREE = 0xFFFFFFFF
END = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD


def directory_entry(name: str, typ: int, *, left=FREE, right=FREE, child=FREE, start=END, size=0) -> bytes:
    b = bytearray(128)
    enc = (name + "\0").encode("utf-16le") if name else b""
    if len(enc) > 64:
        raise ValueError(name)
    b[: len(enc)] = enc
    struct.pack_into("<H", b, 64, len(enc))
    b[66] = typ
    b[67] = 1  # black; the test parser does not depend on tree color
    struct.pack_into("<III", b, 68, left, right, child)
    struct.pack_into("<I", b, 116, start)
    struct.pack_into("<Q", b, 120, size)
    return bytes(b)


def point(mz: float, intensity: int) -> bytes:
    return struct.pack("<HH", round(mz * 20), intensity)


def qgd_record(scan_no: int, rt_ms: int, channel: int, mz_i: list[tuple[float, int]], *, alt_header=False) -> bytes:
    n = len(mz_i)
    rec = bytearray(32 + 4 * n)
    struct.pack_into("<II", rec, 0, scan_no, rt_ms)
    struct.pack_into("<H", rec, 8, channel)
    if alt_header:
        struct.pack_into("<HH", rec, 24, 2, n)
    else:
        struct.pack_into("<HH", rec, 20, 2, n)
    p = 32
    for mz, inten in mz_i:
        rec[p : p + 4] = point(mz, inten)
        p += 4
    return bytes(rec)


def build_synthetic_qgd(path: Path) -> None:
    rts_ms = [60000, 60000, 66000, 66000, 72000, 72000]
    specs = [
        qgd_record(0, rts_ms[0], 0, [(50, 10), (51, 20), (52, 30), (53, 40)]),
        qgd_record(1, rts_ms[1], 1, [(70, 5), (71, 7)], alt_header=True),
        qgd_record(2, rts_ms[2], 0, [(50, 15), (51, 25), (52, 35), (53, 45)]),
        qgd_record(3, rts_ms[3], 1, [(70, 6), (71, 8)], alt_header=True),
        qgd_record(4, rts_ms[4], 0, [(50, 12), (51, 22), (52, 32), (53, 42)]),
        qgd_record(5, rts_ms[5], 1, [(70, 9), (71, 11)], alt_header=True),
    ]
    offsets = []
    raw = bytearray()
    for rec in specs:
        offsets.append(len(raw))
        raw.extend(rec)
    tics = []
    for i, rec in enumerate(specs):
        n = 4 if i % 2 == 0 else 2
        tics.append(sum(struct.unpack_from("<H", rec, 32 + j * 4 + 2)[0] for j in range(n)))

    streams = {
        "Retention Time": b"".join(struct.pack("<i", x) for x in rts_ms),
        "Spectrum Index": b"".join(struct.pack("<I", x) for x in offsets),
        "TIC Data": b"".join(struct.pack("<Q", x) for x in tics),
        "MS Raw Data": bytes(raw),
    }

    # Sector layout: 0-1 directory, 2 RT, 3 index, 4 TIC, 5 raw, 6 FAT.
    sectors = [bytearray(512) for _ in range(7)]
    entries = [
        directory_entry("Root Entry", 5, child=1, start=END, size=0),
        directory_entry("GCMS Raw Data", 1, child=2, start=END, size=0),
        directory_entry("Retention Time", 2, right=3, start=2, size=len(streams["Retention Time"])),
        directory_entry("Spectrum Index", 2, right=4, start=3, size=len(streams["Spectrum Index"])),
        directory_entry("TIC Data", 2, right=5, start=4, size=len(streams["TIC Data"])),
        directory_entry("MS Raw Data", 2, start=5, size=len(streams["MS Raw Data"])),
    ]
    directory = b"".join(entries).ljust(1024, b"\0")
    sectors[0][:] = directory[:512]
    sectors[1][:] = directory[512:1024]
    sectors[2][: len(streams["Retention Time"])] = streams["Retention Time"]
    sectors[3][: len(streams["Spectrum Index"])] = streams["Spectrum Index"]
    sectors[4][: len(streams["TIC Data"])] = streams["TIC Data"]
    sectors[5][: len(streams["MS Raw Data"])] = streams["MS Raw Data"]

    fat = [FREE] * 128
    fat[0] = 1
    fat[1] = END
    for i in range(2, 6):
        fat[i] = END
    fat[6] = FATSECT
    sectors[6][:] = struct.pack("<" + "I" * 128, *fat)

    h = bytearray(512)
    h[:8] = bytes.fromhex("D0CF11E0A1B11AE1")
    struct.pack_into("<H", h, 24, 0x003E)  # minor version
    struct.pack_into("<H", h, 26, 3)       # major version, 512-byte sectors
    struct.pack_into("<H", h, 28, 0xFFFE)  # little endian
    struct.pack_into("<H", h, 30, 9)
    struct.pack_into("<H", h, 32, 6)
    struct.pack_into("<I", h, 40, 0)       # directory sector count (v3)
    struct.pack_into("<I", h, 44, 1)       # FAT sector count
    struct.pack_into("<I", h, 48, 0)       # first directory sector
    struct.pack_into("<I", h, 56, 0)       # mini cutoff forced to 0 for this test fixture
    struct.pack_into("<I", h, 60, END)
    struct.pack_into("<I", h, 64, 0)
    struct.pack_into("<I", h, 68, END)
    struct.pack_into("<I", h, 72, 0)
    for i in range(109):
        struct.pack_into("<I", h, 76 + 4 * i, 6 if i == 0 else FREE)

    path.write_bytes(bytes(h) + b"".join(bytes(x) for x in sectors))


def patch_session_storage(html: str) -> str:
    shim = (
        "<script>window.__sessionStore={};window.__session={"
        "getItem:k=>(k in __sessionStore?__sessionStore[k]:null),"
        "setItem:(k,v)=>{__sessionStore[k]=String(v)},"
        "removeItem:k=>{delete __sessionStore[k]}};</script>"
    )
    return html.replace("<head>", "<head>" + shim, 1).replace("sessionStorage", "__session")


def main() -> int:
    html = patch_session_storage(INDEX.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        qgd = Path(td) / "synthetic_interleaved.qgd"
        build_synthetic_qgd(qgd)
        with sync_playwright() as pw:
            try:
                browser = launch_chromium(pw)
            except Exception as exc:
                print(f"SKIP: chromium is unavailable ({exc.__class__.__name__}).")
                return SKIP
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.set_default_timeout(120000)
            page.set_content(html, wait_until="load")
            page.evaluate("()=>{const x=document.createElement('input');x.type='file';x.id='qgdValidationFile';document.body.appendChild(x)}")
            page.set_input_files("#qgdValidationFile", str(qgd))
            result = page.evaluate(
                """async()=>{const f=document.getElementById('qgdValidationFile').files[0];
                const d=await readRawFile(f);applyRawData(d);buildEIC();
                return {format:d.format,n:d.n,rt:[...d.rt],tic:[...d.tic],info:d.inputInfo,
                nMZ:G.nMZ,mz:[...G.mzList],first:[...d.scanMaps[0].entries()]};}"""
            )
            browser.close()
    if errors:
        raise SystemExit(f"browser page errors: {errors}")
    info = result["info"]
    assert result["format"] == "Shimadzu QGD", result
    assert result["n"] == 3, result
    assert result["rt"] == [1, 1.1, 1.2], result
    assert result["tic"] == [100, 120, 108], result
    assert info["sourceRecords"] == 6 and info["selectedRecords"] == 3, info
    assert info["selectedChannel"] == 0 and info["skippedRecords"] == 3, info
    assert info["ticMismatches"] == 0, info
    assert result["nMZ"] == 4 and result["mz"] == [50, 51, 52, 53], result
    assert result["first"] == [[50, 10], [51, 20], [52, 30], [53, 40]], result
    print("PASS: direct QGD reader selected the dense channel, excluded interleaved secondary records, and preserved TIC exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
