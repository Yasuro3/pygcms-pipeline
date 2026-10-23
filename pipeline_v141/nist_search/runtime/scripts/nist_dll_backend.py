#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
In-process NIST search backend for PyGCMS Pipeline.

Instead of driving the NIST MS Search GUI through AUTOIMP.MSD + /PAR=2 +
SRCRESLT.TXT (the "file" backend), this module calls NIST's own search engine
DLL directly via `pyms-nist-search`.  The scoring engine is identical, so
MF / RMF / Prob are the same values NIST MS Search would report -- but the
per-spectrum cost drops from a process launch + file handshake (~0.4 s) to a
plain function call (~1 ms).

Requirements (checked by `preflight()`):
  1. pip install pyms-nist-search
  2. The NIST search engine DLL must be present and loadable.
  3. A licensed NIST library (mainlib / replib) on disk.

The engine is expensive to construct (it memory-maps the library indices), so
it is cached per (libraries, work_dir) for the lifetime of the process.  This
is what makes a 439-spectrum batch fast.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

try:  # Hit is shared with the file backend so downstream code is unchanged.
    from nist_mssearch_bridge import Hit
except ImportError:  # pragma: no cover - allows standalone import
    @dataclass
    class Hit:  # type: ignore[no-redef]
        query_index: int
        query_name: str
        header: str
        rank: int
        name: str
        formula: str
        mf: float = 0.0
        rmf: float = 0.0
        prob: float = 0.0
        cas: str = ""
        mw: float = 0.0
        lib: str = ""
        id: str = ""
        ri: str = ""


class DllBackendUnavailable(RuntimeError):
    """Raised when the DLL backend cannot be used; caller should fall back."""


# --------------------------------------------------------------------------
# MSP parsing (same shape the file backend feeds to NIST)
# --------------------------------------------------------------------------

@dataclass
class MspSpectrum:
    name: str
    comment: str
    mz: List[float]
    intensity: List[float]


def parse_msp(text: str) -> List[MspSpectrum]:
    """Parse an MSP file into spectra. Tolerates the two common peak layouts:
    one peak per line ("57 999") and semicolon-packed lines ("43 999; 57 760;")."""
    spectra: List[MspSpectrum] = []
    name = comment = ""
    mz: List[float] = []
    inten: List[float] = []
    in_peaks = False

    def flush() -> None:
        if name and mz:
            spectra.append(MspSpectrum(name, comment, list(mz), list(inten)))

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("name:"):
            flush()
            name, comment, mz, inten, in_peaks = line[5:].strip(), "", [], [], False
            continue
        if low.startswith("comment:"):
            comment = line[8:].strip()
            continue
        if low.startswith("num peaks:"):
            in_peaks = True
            continue
        if not in_peaks:
            continue
        for chunk in line.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = re.split(r"[\s,]+", chunk)
            if len(parts) < 2:
                continue
            try:
                mz.append(float(parts[0]))
                inten.append(float(parts[1]))
            except ValueError:
                continue
    flush()
    return spectra


# --------------------------------------------------------------------------
# Engine discovery / caching
# --------------------------------------------------------------------------

_ENGINE_CACHE: dict = {}
_ENGINE_LOCK = threading.Lock()

# NIST library directory names, in the order they should be searched.
DEFAULT_LIB_NAMES = ("mainlib", "replib")


def discover_libraries(mssearch_dir: Path,
                       names: Sequence[str] = DEFAULT_LIB_NAMES) -> List[Tuple[Path, str]]:
    """Return [(library_path, lib_type_name)] for libraries that exist on disk."""
    found: List[Tuple[Path, str]] = []
    for n in names:
        p = mssearch_dir / n
        if p.is_dir():
            kind = "REP" if n.lower().startswith("rep") else ("USER" if n.lower().startswith("user") else "MAIN")
            found.append((p, kind))
    return found


def _lib_type_const(mod: Any, kind: str) -> Any:
    return {
        "MAIN": mod.NISTMS_MAIN_LIB,
        "REP": mod.NISTMS_REP_LIB,
        "USER": mod.NISTMS_USER_LIB,
    }[kind]


def _import_pyms() -> Any:
    try:
        import pyms_nist_search  # type: ignore
    except ImportError as e:
        raise DllBackendUnavailable(
            "pyms-nist-search is not installed. Run:  pip install pyms-nist-search"
        ) from e
    except OSError as e:
        # Typical when the NIST engine DLL is missing or is the wrong bitness.
        raise DllBackendUnavailable(
            f"pyms-nist-search imported but the NIST engine DLL could not be loaded: {e}"
        ) from e
    return pyms_nist_search


def get_engine(libraries: Sequence[Tuple[Path, str]], work_dir: Path) -> Any:
    """Construct (or reuse) a NIST search Engine. Cached: construction is slow."""
    if not libraries:
        raise DllBackendUnavailable(
            "No NIST library directory found. Expected e.g. C:\\NIST20\\MSSEARCH\\mainlib"
        )
    key = (tuple((str(p).lower(), k) for p, k in libraries), str(work_dir).lower())
    with _ENGINE_LOCK:
        eng = _ENGINE_CACHE.get(key)
        if eng is not None:
            return eng
        mod = _import_pyms()
        work_dir.mkdir(parents=True, exist_ok=True)
        spec = [(str(p), _lib_type_const(mod, k)) for p, k in libraries]
        try:
            eng = mod.Engine(spec, work_dir=str(work_dir))
        except Exception as e:
            raise DllBackendUnavailable(f"Could not initialise the NIST search engine: {e}") from e
        _ENGINE_CACHE[key] = eng
        return eng


# --------------------------------------------------------------------------
# Result mapping
# --------------------------------------------------------------------------

def _g(obj: Any, *names: str, default: Any = "") -> Any:
    """pyms-nist-search attribute names have drifted across releases; try several."""
    for n in names:
        if hasattr(obj, n):
            v = getattr(obj, n)
            if v is not None:
                return v
    return default


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_hit(qidx: int, qname: str, rank: int, result: Any, ref: Any) -> Hit:
    name = str(_g(result, "name", default="") or _g(ref, "name", default=""))
    return Hit(
        query_index=qidx,
        query_name=qname,
        header=qname,
        rank=rank,
        name=name,
        formula=str(_g(ref, "formula", default="")),
        mf=_num(_g(result, "match_factor", "mf", default=0)),
        rmf=_num(_g(result, "reverse_match_factor", "rmf", default=0)),
        prob=_num(_g(result, "hit_prob", "prob", default=0)),
        cas=str(_g(result, "cas", default="") or _g(ref, "cas", default="")),
        mw=_num(_g(ref, "mw", "molecular_weight", default=0)),
        lib="NIST (DLL)",
        id=str(_g(ref, "id", "spec_loc", default="")),
        ri="",
    )


# --------------------------------------------------------------------------
# Public API -- mirrors the file backend's contract
# --------------------------------------------------------------------------

def search_msp_file(msp: Path,
                    mssearch_dir: Path,
                    work_dir: Optional[Path] = None,
                    n_hits: int = 15,
                    libraries: Optional[Sequence[Tuple[Path, str]]] = None) -> List[Hit]:
    """Search every spectrum in `msp` and return Hit objects, ranked per spectrum."""
    msp = Path(msp)
    mssearch_dir = Path(mssearch_dir)
    work_dir = Path(work_dir) if work_dir else (mssearch_dir.parent / "pygcms_dll_work")
    libs = list(libraries) if libraries else discover_libraries(mssearch_dir)
    eng = get_engine(libs, work_dir)

    mod = _import_pyms()
    spectra = parse_msp(msp.read_text(encoding="utf-8", errors="replace"))
    if not spectra:
        return []

    hits: List[Hit] = []
    for qidx, sp in enumerate(spectra, start=1):
        ms = mod.MassSpectrum(sp.mz, sp.intensity) if hasattr(mod, "MassSpectrum") else _pyms_spectrum(sp)
        try:
            pairs = eng.full_search_with_ref_data(ms, n_hits=n_hits)
        except Exception as e:
            raise DllBackendUnavailable(f"NIST DLL search failed on '{sp.name}': {e}") from e
        for rank, (result, ref) in enumerate(pairs, start=1):
            hits.append(_to_hit(qidx, sp.name, rank, result, ref))
    return hits


def _pyms_spectrum(sp: MspSpectrum) -> Any:
    from pyms.Spectrum import MassSpectrum  # type: ignore
    return MassSpectrum(sp.mz, sp.intensity)


def preflight(mssearch_dir: Path, work_dir: Optional[Path] = None) -> dict:
    """Diagnose whether the DLL backend can run. Never raises."""
    mssearch_dir = Path(mssearch_dir)
    info: dict = {
        "ok": False,
        "mssearch_dir": str(mssearch_dir),
        "pyms_nist_search": None,
        "dlls_found": [],
        "libraries": [],
        "error": "",
    }
    for pat in ("nistdl32.dll", "nistdl64.dll", "ctnt66.dll", "NISTMSCLP.dll"):
        for p in mssearch_dir.parent.rglob(pat):
            info["dlls_found"].append(str(p))
    info["libraries"] = [f"{p} ({k})" for p, k in discover_libraries(mssearch_dir)]
    try:
        mod = _import_pyms()
        info["pyms_nist_search"] = getattr(mod, "__version__", "unknown")
    except DllBackendUnavailable as e:
        info["error"] = str(e)
        return info
    if not info["libraries"]:
        info["error"] = f"No mainlib/replib directory under {mssearch_dir}"
        return info
    try:
        wd = Path(work_dir) if work_dir else (mssearch_dir.parent / "pygcms_dll_work")
        get_engine(discover_libraries(mssearch_dir), wd)
        info["ok"] = True
    except DllBackendUnavailable as e:
        info["error"] = str(e)
    return info


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="NIST DLL backend preflight / search")
    ap.add_argument("--mssearch-dir", default=r"C:\NIST20\MSSEARCH")
    ap.add_argument("--msp", help="Optional MSP file to search")
    ap.add_argument("--n-hits", type=int, default=15)
    a = ap.parse_args()

    info = preflight(Path(a.mssearch_dir))
    print(json.dumps(info, indent=2, ensure_ascii=False))
    if not info["ok"]:
        raise SystemExit(2)
    if a.msp:
        import time
        t0 = time.time()
        hits = search_msp_file(Path(a.msp), Path(a.mssearch_dir), n_hits=a.n_hits)
        dt = time.time() - t0
        nq = len({h.query_index for h in hits})
        print(f"\n{len(hits)} hits for {nq} spectra in {dt:.2f} s ({dt/max(nq,1)*1000:.1f} ms/spectrum)")
        for h in hits[:5]:
            print(f"  Hit {h.rank}: {h.name}  MF={h.mf} RMF={h.rmf} Prob={h.prob}")
