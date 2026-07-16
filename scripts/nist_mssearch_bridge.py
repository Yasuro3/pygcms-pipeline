#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bridge between the Py-GC/MS browser app and a locally licensed NIST MS Search installation.

This script does NOT read, copy, extract, or redistribute NIST library spectra.
It only passes user spectra in MSP/NIST text format to NISTMS$.EXE and parses NIST's
own text search output (SRCRESLT.TXT) into CSV/JSON for import back into the app.

Automation model (see NIST MS Search manual, Appendix 1)
--------------------------------------------------------
* AUTOIMP.MSD lives in the NIST *work* directory (WIN.INI [NISTMS] WorkDir32) and
  contains one line: the full path of a *secondary* locator file.
* The secondary locator file contains: "<full path to spectrum file> OVERWRITE|APPEND".
* Launching  NISTMS$.EXE /INSTRUMENT /PAR=2  makes NIST import the spectrum and run the search,
  writing SRCRESLT.TXT (+ SRCREADY.TXT flag) into the work directory.
  IMPORTANT: /PAR=2 is the switch that triggers the search. For NIST20/NIST23,
  /INSTRUMENT is enabled by default in PyGCMS Pipeline because some installations
  display hits in the GUI but do not create SRCREADY/SRCRESLT reliably without it.
* NIST MS Search's Automation tab must be enabled and "Number of hits to print" > 0,
  otherwise SRCRESLT.TXT is written empty (or not at all).

Typical use on Windows:
  py -3 nist_mssearch_bridge.py launch --nistms "C:\\NIST23\\MSSEARCH\\NISTMS$.EXE"
  py -3 nist_mssearch_bridge.py search --msp sample.msp \
    --nistms "C:\\NIST23\\MSSEARCH\\NISTMS$.EXE" --csv nist_hits.csv
  py -3 nist_mssearch_bridge.py doctor --nistms "C:\\NIST23\\MSSEARCH\\NISTMS$.EXE"
"""
from __future__ import annotations

import argparse
import csv
import json
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class Hit:
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


def native_text_encoding() -> str:
    """Encoding used by legacy NIST locator/result text files on Windows."""
    return "mbcs" if os.name == "nt" else "utf-8"


def clean_path_text(value: object) -> str:
    """Trim quotes, BOM, CR/LF, and environment variables from a path-like string."""
    s = str(value or "").strip().lstrip("\ufeff").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "'"}:
        s = s[1:-1].strip()
    return os.path.expandvars(s)


def path_from_dir_or_file(value: object, exe_name: str = "NISTMS$.EXE") -> Optional[Path]:
    s = clean_path_text(value)
    if not s:
        return None
    p = Path(s)
    if p.name.lower() == exe_name.lower():
        return p
    return p / exe_name


def win_ini_value(section: str, key: str) -> str:
    """Read a value from WIN.INI on Windows, returning '' on other platforms/errors."""
    if os.name != "nt":
        return ""
    try:
        import ctypes  # Windows only
        buf = ctypes.create_unicode_buffer(4096)
        ctypes.windll.kernel32.GetPrivateProfileStringW(section, key, "", buf, len(buf), "win.ini")
        return clean_path_text(buf.value)
    except Exception:
        return ""


def discover_nistms() -> Optional[Path]:
    """Try to find NISTMS$.EXE without hard-coding a single version.

    Order: WIN.INI [NISTMS] Path32/WorkDir32/Path16/WorkDir16, then a broad set of
    common install roots (including Shimadzu-style and Program Files locations)."""
    candidates: List[Path] = []
    for key in ("Path32", "WorkDir32", "Path16", "WorkDir16"):
        p = path_from_dir_or_file(win_ini_value("NISTMS", key))
        if p:
            candidates.append(p)
    roots = [
        "C:/NIST23", "C:/NIST20", "C:/NIST17", "C:/NIST14", "C:/NIST11",
        "C:/NIST08", "C:/NIST05", "C:/NIST02", "C:/NIST", "C:/NISTMS",
        # Shimadzu / vendor and Program Files style installs sometimes differ.
        "C:/Database/NIST23", "C:/Database/NIST20", "C:/GCMSsolution/NIST23",
        "C:/Program Files/NISTMS", "C:/Program Files (x86)/NISTMS",
        "C:/Program Files/NIST23", "C:/Program Files (x86)/NIST23",
    ]
    for root in roots:
        candidates.append(Path(root) / "MSSEARCH" / "NISTMS$.EXE")
    seen = set()
    for c in candidates:
        cs = str(c).lower()
        if cs in seen:
            continue
        seen.add(cs)
        try:
            if c.exists():
                return c
        except Exception:
            continue
    return None


def discover_nist_workdir(nistms: Optional[Path] = None) -> Path:
    """Return NIST MS Search WorkDir32/WorkDir16, falling back to NISTMS$.EXE's folder."""
    for key in ("WorkDir32", "WorkDir16", "Path32", "Path16"):
        s = win_ini_value("NISTMS", key)
        if s:
            p = Path(s)
            if p.name.lower() == "nistms$.exe":
                p = p.parent
            if p.exists():
                return p
    if nistms:
        return nistms.resolve().parent
    found = discover_nistms()
    if found:
        return found.resolve().parent
    return Path.cwd()


def default_bridge_tempdir() -> Path:
    """ASCII-friendly writable directory for MSP and secondary locator files."""
    if os.name == "nt":
        candidates = [
            Path(os.environ.get("ProgramData") or "C:/ProgramData") / "PyGCMS_NIST_Bridge",
            Path("C:/PyGCMS_NIST_Bridge"),
            Path(tempfile.gettempdir()) / "pygcms_nist_bridge",
        ]
    else:
        candidates = [Path(tempfile.gettempdir()) / "pygcms_nist_bridge"]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            continue
    return Path(tempfile.gettempdir()) / "pygcms_nist_bridge"


def nist_safe_tempdir() -> Path:
    """Short ASCII path used for MSP files passed to NIST MS Search.

    Some NIST20/NIST23 installations fail silently when AUTOIMP points to an
    MSP file under a long application folder or a non-system drive.  Keep the
    spectrum file in a short, writable ASCII-only directory.
    """
    return default_bridge_tempdir()

def secondary_locator_candidates(workdir: Path) -> List[Path]:
    """Candidate secondary locator paths for AUTOIMP.MSD.

    NIST17 often accepts a ProgramData locator, but some NIST20 installations
    only respond reliably when PYGCMS_AUTOIMP.FIL is in the NIST work folder
    itself.  Try the local work-folder locator first and fall back to ProgramData.
    """
    candidates = [workdir / "PYGCMS_AUTOIMP.FIL", default_bridge_tempdir() / "PYGCMS_AUTOIMP.FIL"]
    return unique_paths(candidates)


def ensure_autoimp(workdir: Path, secondary: Path, create: bool = True, force: bool = False) -> Path:
    """Return the secondary locator path used by AUTOIMP.MSD.

    NIST MS Search reads AUTOIMP.MSD from its effective work directory.  In
    practice, stale AUTOIMP.MSD files are a common cause of "NIST bridge is
    connected but no SRCREADY.TXT is written".  Therefore, when force=True we
    refresh AUTOIMP.MSD so it points to the PyGCMS secondary locator for the
    current run.  If the folder is not writable but AUTOIMP.MSD already exists,
    we fall back to the existing locator instead of failing immediately.
    """
    autoimp = workdir / "AUTOIMP.MSD"

    def read_existing() -> Optional[Path]:
        if not autoimp.exists():
            return None
        lines = autoimp.read_text(encoding=native_text_encoding(), errors="replace").strip().splitlines()
        first = clean_path_text(lines[0].strip()) if lines else ""
        if not first:
            raise RuntimeError(f"{autoimp} exists but is empty")
        p = Path(first)
        if not p.is_absolute():
            p = workdir / p
        return p

    if autoimp.exists() and not force:
        p = read_existing()
        if p:
            return p

    if not autoimp.exists() and not create:
        raise RuntimeError(f"AUTOIMP.MSD not found in {workdir}. Create it manually or rerun without --no-create-autoimp.")

    try:
        workdir.mkdir(parents=True, exist_ok=True)
        # NIST manual: the AUTOIMP.MSD line must end with CR + LF.
        with open(str(autoimp), "w", encoding=native_text_encoding(), errors="replace", newline="") as fh:
            fh.write(str(secondary) + "\r\n")
        return secondary
    except PermissionError as e:
        existing = read_existing()
        if existing:
            return existing
        raise PermissionError(
            f"Cannot create {autoimp}. Start the terminal as Administrator once, or manually create "
            f"AUTOIMP.MSD (in {workdir}) containing this single line:\n{secondary}\r\n"
        ) from e


def normalise_append_mode(append_mode: str) -> str:
    s = str(append_mode or "").strip().upper()
    return "APPEND" if s.startswith("APP") else "OVERWRITE"


def write_secondary_locator(secondary: Path, msp: Path, append_mode: str = "OVERWRITE") -> None:
    secondary.parent.mkdir(parents=True, exist_ok=True)
    mode = normalise_append_mode(append_mode)
    line = f"{msp.resolve()} {mode}\r\n"
    secondary.write_text(line, encoding=native_text_encoding(), errors="replace")


def remove_if_exists(path: Path) -> bool:
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
    except PermissionError:
        return False


def file_state(path: Path) -> str:
    try:
        st = path.stat()
        return f"exists size={st.st_size} mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}"
    except FileNotFoundError:
        return "missing"
    except Exception as e:
        return f"stat-error={e}"


def unique_paths(paths: Iterable[Path]) -> List[Path]:
    """Deduplicate paths while preserving order."""
    out: List[Path] = []
    seen = set()
    for p in paths:
        if p is None:
            continue
        try:
            q = Path(p).expanduser()
        except Exception:
            q = Path(str(p))
        key = str(q).lower()
        if key not in seen:
            seen.add(key)
            out.append(q)
    return out


def file_signature(path: Path) -> Optional[tuple[int, int, str]]:
    """Return a small signature used to reject stale SRCRESLT/SRCREADY files."""
    try:
        st = path.stat()
        h = hashlib.sha1()
        with path.open("rb") as f:
            h.update(f.read(64 * 1024))
        return (st.st_size, int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9))), h.hexdigest())
    except Exception:
        return None


def stat_mtime_ns(path: Path) -> int:
    try:
        st = path.stat()
        return int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
    except Exception:
        return -1


def read_text_if_exists(path: Path, limit: int = 0) -> str:
    try:
        txt = path.read_text(encoding=native_text_encoding(), errors="replace")
        return txt[:limit] if limit and len(txt) > limit else txt
    except Exception:
        return ""


def read_srcready_count(path: Path) -> int:
    txt = read_text_if_exists(path, limit=200)
    m = re.search(r"[-+]?\d+", txt)
    return int(m.group(0)) if m else 0


# The official NIST manual (Ver.20/2.2/2.4) names these SRCREADY.TXT / SRCRESLT.TXT.
# Some third-party automation notes contain the typos SCREADY.TXT / SCRESLT.TXT.
# We accept both so a non-standard build cannot stall the bridge; the canonical
# names are always tried first.
READY_NAMES = ("SRCREADY.TXT", "SCREADY.TXT")
RESLT_NAMES = ("SRCRESLT.TXT", "SCRESLT.TXT")


def find_named(result_dir: Path, names: Iterable[str]) -> Optional[Path]:
    """Return the first existing file among `names` inside result_dir."""
    for n in names:
        p = result_dir / n
        if p.exists():
            return p
    return None


def ready_path(result_dir: Path) -> Optional[Path]:
    return find_named(result_dir, READY_NAMES)


def reslt_path(result_dir: Path) -> Optional[Path]:
    return find_named(result_dir, RESLT_NAMES)


def virtualstore_twin(path: Path) -> Optional[Path]:
    """Map C:\\Program Files (x86)\\... to the per-user VirtualStore copy.

    When NISTMS$.EXE lives under Program Files and runs unelevated, Windows
    UAC file virtualization silently redirects SRCREADY/SRCRESLT writes to
    %LOCALAPPDATA%\\VirtualStore\\<same relative path>.  The bridge then sees
    an "empty" work directory even though NIST searched successfully.
    """
    if os.name != "nt":
        return None
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    try:
        s = str(path.resolve())
        drive, rest = os.path.splitdrive(s)
        if not rest:
            return None
        low = rest.lower()
        if not (low.startswith("\\program files") or low.startswith("\\windows")):
            return None
        return Path(local) / "VirtualStore" / rest.lstrip("\\/")
    except Exception:
        return None


def count_msp_spectra_text(text: str) -> int:
    return len(re.findall(r"^Name:\s*", text or "", flags=re.I | re.M))


def count_msp_spectra_file(path: Path) -> int:
    return count_msp_spectra_text(path.read_text(encoding="utf-8", errors="replace"))


def win_ini_workdir_path() -> Optional[Path]:
    v = win_ini_value("NISTMS", "WorkDir32") or win_ini_value("NISTMS", "WorkDir16")
    if not v:
        return None
    try:
        p = Path(clean_path_text(v)).expanduser()
        if p.name.lower() == "nistms$.exe":
            p = p.parent
        return p
    except Exception:
        return None


def result_directories(nistms: Path, primary_workdir: Path) -> List[Path]:
    """Directories where NIST automation may read AUTOIMP.MSD and write SRCRESLT/SRCREADY.

    NIST installations vary: most use the NISTMS$.EXE folder; some manuals/settings refer
    to WIN.INI [NISTMS] WorkDir32. We keep both synchronized and accept a fresh result
    from either directory.
    """
    paths = [primary_workdir, nistms.resolve().parent]
    ini = win_ini_workdir_path()
    if ini:
        paths.append(ini)
    # UAC file virtualization: if NIST lives under Program Files, an unelevated
    # NISTMS$.EXE writes SRCREADY/SRCRESLT into the per-user VirtualStore instead.
    for p in list(paths):
        vs = virtualstore_twin(p)
        if vs and vs.is_dir():
            paths.append(vs)
    return unique_paths(paths)


def fresh_result_ready(result_dir: Path, old_sigs: dict[str, Optional[tuple[int, int, str]]], launch_ns: int) -> bool:
    srcready = ready_path(result_dir)
    if srcready is None:
        return False
    srcreslt = reslt_path(result_dir) or (result_dir / "SRCRESLT.TXT")
    res_sig = file_signature(srcreslt)
    ready_sig = file_signature(srcready)
    if not ready_sig:
        return False
    old_res = old_sigs.get(str(srcreslt.resolve()).lower())
    old_ready = old_sigs.get(str(srcready.resolve()).lower())
    res_changed = (res_sig is not None and res_sig != old_res)
    ready_changed = ready_sig != old_ready
    # File timestamps can have coarse resolution on older Windows filesystems, so we accept
    # either a changed signature or a timestamp close to the launch time. SRCREADY is the
    # completion flag; SRCRESLT can be empty or absent when NIST has no printable hits.
    recent = ((res_sig is not None and res_sig[1] >= launch_ns - 3_000_000_000) or
              (ready_sig[1] >= launch_ns - 3_000_000_000))
    return (res_changed or ready_changed) and recent

def result_files_diagnostics(result_dirs: Iterable[Path]) -> str:
    lines: List[str] = []
    for d in result_dirs:
        lines.append(f"Result directory: {d}")
        lines.append(f"  AUTOIMP.MSD: {file_state(d / 'AUTOIMP.MSD')}")
        for n in READY_NAMES + RESLT_NAMES:
            lines.append(f"  {n}: {file_state(d / n)}")
    return "\n".join(lines)


def make_run_token() -> str:
    return "PYGCMSRUN" + time.strftime("%Y%m%d%H%M%S") + uuid.uuid4().hex[:8].upper()


def create_demo_msp(path: Path, token: Optional[str] = None) -> str:
    """Create a tiny EI-like spectrum for background automation testing."""
    token = token or make_run_token()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"Name: PGCMS_BACKGROUND_TEST_RT_1.000_{token}\r\n"
        f"Comment: PyGCMS NIST automation self-test; token={token}\r\n"
        "Num Peaks: 8\r\n"
        "43 999; 57 760; 71 520; 85 300; 99 210; 114 180; 128 90; 142 60\r\n\r\n"
    )
    path.write_text(text, encoding="utf-8", errors="replace")
    return token


def build_search_command(nistms: Path, par: int = 2, instrument: bool = True,
                        instrument_last: bool = False) -> List[str]:
    """Build the NISTMS$.EXE command line that triggers an automated search.

    /PAR=<n> is the switch that actually runs the search (n=2 => background search,
    writes SRCRESLT.TXT/SRCREADY.TXT). /INSTRUMENT is enabled by default for
    NIST20/NIST23 compatibility; it must appear before /PAR=2.
    """
    cmd = [str(nistms)]
    if instrument and not instrument_last:
        cmd.append("/INSTRUMENT")
    cmd.append(f"/PAR={int(par)}")
    if instrument and instrument_last:
        cmd.append("/INSTRUMENT")
    return cmd


def launch_nist_gui(nistms: Path, instrument: bool = True) -> int:
    """Bring NIST MS Search up (no search) so the user can enable Automation and pick
    libraries. Returns the child PID. If an instance is already running, NIST typically
    re-focuses the existing window instead of starting a second copy."""
    nistms = nistms.resolve()
    if not nistms.exists():
        raise FileNotFoundError(f"NISTMS$.EXE not found: {nistms}")
    cmd = [str(nistms)] + (["/INSTRUMENT"] if instrument else [])
    proc = subprocess.Popen(cmd, cwd=str(nistms.parent),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.pid


_NIST_RUNNING_CACHE: dict = {"t": 0.0, "v": False}


def nist_is_running(ttl: float = 5.0) -> bool:
    """True if a NIST MS Search main window process (NISTMS.EXE) is alive.

    NISTMS$.EXE is only a messenger: it forwards /PAR switches to the running
    NISTMS.EXE main window.  When NISTMS.EXE is NOT running, `nistms$.exe /PAR=2`
    merely cold-starts the GUI and no background search is performed, so no
    SRCREADY/SRCRESLT is written.  The search must therefore always be issued
    against an already-running instance.
    """
    if os.name != "nt":
        return False
    now = time.time()
    if ttl > 0 and _NIST_RUNNING_CACHE["v"] and (now - _NIST_RUNNING_CACHE["t"]) < ttl:
        # Only a positive result is cached: a false "running" costs one wasted
        # /PAR=2, while a false "not running" would pop up a second GUI.
        return True
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq NISTMS.EXE", "/NH"],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout
    except Exception:
        return False
    v = "nistms.exe" in out.lower()
    _NIST_RUNNING_CACHE.update(t=now, v=v)
    return v


def ensure_nist_running(nistms: Path, instrument: bool = True,
                        wait: float = 20.0, settle: float = 3.0) -> bool:
    """Make sure NISTMS.EXE is up before any locator file is written.

    Returns True if it had to start NIST, False if it was already running.

    Ordering matters: NIST consumes (and deletes) the secondary locator file the
    moment it gains focus.  If the locator is written *before* the GUI starts,
    the cold-start focus event eats it, the spectra are imported and searched in
    the GUI only, and the subsequent /PAR=2 finds nothing left to search.
    """
    if nist_is_running():
        return False
    launch_nist_gui(nistms, instrument=instrument)
    deadline = time.time() + wait
    while time.time() < deadline:
        if nist_is_running():
            time.sleep(settle)  # let the main window finish initialising
            return True
        time.sleep(0.3)
    time.sleep(settle)
    return True


def run_nist_search(
    nistms: Path,
    msp: Path,
    timeout: float = 180.0,
    append_mode: str = "OVERWRITE",
    create_autoimp: bool = True,
    dry_run: bool = False,
    nist_workdir: Optional[Path] = None,
    par: int = 2,
    instrument: bool = False,
    prelaunch: bool = False,
    prelaunch_wait: float = 6.0,
    force_autoimp: bool = True,
    retry_with_prelaunch: bool = True,
    instrument_last: bool = False,
    poll_interval: float = 0.03,
) -> Path:
    nistms = nistms.resolve()
    msp = msp.resolve()
    if not nistms.exists():
        raise FileNotFoundError(f"NISTMS$.EXE not found: {nistms}")
    if not msp.exists():
        raise FileNotFoundError(f"MSP file not found: {msp}")

    # Primary effective work directory follows the selected exe. For robustness we also
    # synchronize/monitor WIN.INI WorkDir32 when it differs.
    if nist_workdir:
        primary_workdir = nist_workdir.expanduser().resolve()
    else:
        primary_workdir = nistms.parent.resolve()
    result_dirs = result_directories(nistms, primary_workdir)
    # The MSP itself is normally already staged in a short ASCII directory by
    # the server/CLI.  For the secondary locator, prefer a file in the NIST
    # work directory; this avoids NIST20 silently ignoring AUTOIMP.MSD on some PCs.
    tempdir = nist_safe_tempdir()
    secondary_fallback = tempdir / "PYGCMS_AUTOIMP.FIL"

    # STEP 0 -- remove any leftover locator from a previous run.  If NIST cold-starts
    # while a stale locator exists, its startup focus event consumes it and imports the
    # WRONG spectra, and the locator is then gone when /PAR=2 arrives.
    stale_locators = [d / "PYGCMS_AUTOIMP.FIL" for d in result_dirs] + [secondary_fallback]
    if not dry_run:
        for loc in unique_paths(stale_locators):
            remove_if_exists(loc)

    # STEP 1 -- NIST MS Search must already be running before we write the locator.
    # (See ensure_nist_running for why.)  dry_run skips this.
    started_nist = False
    if not dry_run:
        started_nist = ensure_nist_running(nistms, instrument=instrument,
                                           wait=max(15.0, prelaunch_wait * 3),
                                           settle=max(3.0, prelaunch_wait * 0.5))

    # STEP 2 -- write AUTOIMP.MSD + secondary locator into every plausible work folder.
    written_secondaries: List[Path] = []
    locator_errors: List[str] = []

    def write_locators() -> None:
        written_secondaries.clear()
        locator_errors.clear()
        for d in result_dirs:
            for sec_candidate in secondary_locator_candidates(d) + [secondary_fallback]:
                try:
                    sec = ensure_autoimp(d, sec_candidate, create=create_autoimp, force=force_autoimp)
                    write_secondary_locator(sec, msp, append_mode=append_mode)
                    written_secondaries.append(sec)
                    break
                except Exception as e:
                    locator_errors.append(f"{d} via {sec_candidate}: {e}")

    write_locators()
    if not written_secondaries and not dry_run:
        raise PermissionError(
            "Could not create/update AUTOIMP.MSD or the secondary locator in any NIST work directory.\n"
            + "\n".join(locator_errors)
        )

    # STEP 3 -- snapshot and clear stale result files.
    old_sigs: dict[str, Optional[tuple[int, int, str]]] = {}
    for d in result_dirs:
        for n in READY_NAMES + RESLT_NAMES:
            old_sigs[str((d / n).resolve()).lower()] = file_signature(d / n)
            remove_if_exists(d / n)

    cmd = build_search_command(nistms, par=par, instrument=instrument, instrument_last=instrument_last)

    if dry_run:
        print("DRY RUN")
        print("NISTMS:", nistms)
        print("Primary NIST WorkDir:", primary_workdir)
        print("All candidate result/work dirs:")
        for d in result_dirs:
            print(" ", d)
        print("Secondary locators written:")
        for sec in written_secondaries:
            print(" ", sec)
        if locator_errors:
            print("Locator warnings:")
            for e in locator_errors:
                print(" ", e)
        print("NIST MS Search currently running:", nist_is_running())
        print("Order: ensure NIST running -> write locator -> send /PAR=2")
        print("Force-refresh AUTOIMP.MSD:", force_autoimp)
        print("Search command:", " ".join(cmd))
        print("Expected result: SRCRESLT.TXT in one of the candidate dirs above")
        print("Expected ready flag: SRCREADY.TXT in the same dir")
        return result_dirs[0] / "SRCRESLT.TXT"

    def trigger_search_once(rewrite_locator: bool = False) -> tuple[int, float]:
        # NIST deletes the secondary locator the moment it imports the spectra, and
        # /PAR=2 only performs a background search when a locator is present.  So the
        # locator must exist at the exact instant the command is issued.
        if rewrite_locator:
            try:
                ensure_nist_running(nistms, instrument=instrument, wait=10.0, settle=1.0)
            except Exception:
                pass
        if rewrite_locator or not any(s.exists() for s in written_secondaries):
            write_locators()
        ns = time.time_ns()
        s = time.time()
        subprocess.Popen(cmd, cwd=str(nistms.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ns, s

    launch_ns, launch_s = trigger_search_once()
    last_note = ""
    retried_prelaunch = False
    while time.time() - launch_s < timeout:
        for d in result_dirs:
            if fresh_result_ready(d, old_sigs, launch_ns):
                # NIST may complete a query with SRCREADY but an empty/missing SRCRESLT
                # when no hits are printable. Treat this as a valid 0-hit result so the
                # caller can continue to later spectra instead of waiting until timeout.
                found = reslt_path(d)
                if found is None:
                    found = d / "SRCRESLT.TXT"
                    found.touch(exist_ok=True)
                return found
            srcready = ready_path(d)
            srcreslt = reslt_path(d)
            if srcready and srcreslt:
                if srcreslt.stat().st_size <= 0:
                    last_note = f"{d}: {srcready.name} exists; {srcreslt.name} is empty (will be accepted as 0-hit if fresh)"
                else:
                    last_note = f"{d}: result files exist but were not fresh enough yet"
        # If the first attempt produced nothing, the locator was probably consumed by a
        # focus event without a background search running.  Rewrite it and retry once.
        elapsed = time.time() - launch_s
        if (retry_with_prelaunch and not retried_prelaunch and elapsed > min(20.0, max(8.0, timeout * 0.25))):
            any_src = any(ready_path(d) or reslt_path(d) for d in result_dirs)
            if not any_src:
                retried_prelaunch = True
                try:
                    launch_ns, launch_s = trigger_search_once(rewrite_locator=True)
                    last_note = "Retried once after rewriting the secondary locator file."
                    continue
                except Exception:
                    pass
        # Poll fast at first (most searches finish in well under a second), then
        # back off so a long batch does not spin the CPU.
        time.sleep(min(0.25, poll_interval * (1.0 + elapsed)))

    stage = ""
    for d in result_dirs:
        if ready_path(d) or reslt_path(d):
            stage = (
                "SRCREADY/SRCRESLT appeared but a fresh result was not confirmed. "
                "This usually means NIST did not complete this batch, or stale files were locked. "
                "Open NIST MS Search > Options > Library Search Options > Automation, enable Automation, "
                "set Number of hits to print > 0, and select at least one library."
            )
            break
    if not stage:
        stage = (
            "NIST did not write SRCREADY.TXT. NISTMS.EXE running at launch: "
            f"{not started_nist} (bridge started it: {started_nist}). "
            "Confirm Automation is enabled with 'Number of Hits to Print' > 0 and at least one "
            "library selected, then leave NIST MS Search open and retry."
        )
    if last_note:
        stage += f" Last wait state: {last_note}."

    raise TimeoutError(
        "Timed out waiting for a fresh SRCREADY.TXT/SRCRESLT.TXT from the current run.\n"
        f"Search command: {' '.join(cmd)}\n"
        f"Primary NIST WorkDir: {primary_workdir}\n"
        f"MSP spectrum file: {msp} ({file_state(msp)})\n"
        f"Secondary locators written: {', '.join(str(x) for x in written_secondaries)}\n"
        f"Result files checked:\n{result_files_diagnostics(result_dirs)}\n"
        f"Diagnosis: {stage}"
    )


def search_via_dll(msp: Path, nistms: Path, n_hits: int = 15) -> List[Hit]:
    """In-process search through NIST's engine DLL. Raises DllBackendUnavailable."""
    from nist_dll_backend import search_msp_file  # local import: optional dependency
    return search_msp_file(msp, nistms.resolve().parent, n_hits=n_hits)


def search_hits(msp: Path, nistms: Path, backend: str = "auto",
                n_hits: int = 15, **file_kwargs) -> tuple[List[Hit], str]:
    """Return (hits, backend_actually_used).

    backend='dll'  -> DLL only; error if unavailable
    backend='file' -> the /PAR=2 + SRCRESLT.TXT path (always available)
    backend='auto' -> try DLL, fall back to file on any DllBackendUnavailable
    """
    backend = (backend or "auto").lower()
    if backend in ("dll", "auto"):
        try:
            return search_via_dll(msp, nistms, n_hits=n_hits), "dll"
        except Exception as e:
            if backend == "dll":
                raise
            print(f"[bridge] DLL backend unavailable ({e}); falling back to the file backend.")
    srcreslt = run_nist_search(nistms=nistms, msp=msp, **file_kwargs)
    return (parse_srcreslt_file(srcreslt) if srcreslt.exists() else []), "file"


def parse_srcreslt_text(text: str) -> List[Hit]:
    hits: List[Hit] = []
    current_header = ""
    current_query_name = ""
    qidx = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^Unknown:\s*(.*)$", line, flags=re.I)
        if m:
            qidx += 1
            current_header = m.group(1)
            current_query_name = current_header.split(" Compound in Library Factor")[0].strip()
            continue
        m = re.match(r"^Hit\s+(\d+)\s*:\s*<<([^>]*)>>\s*;\s*<<([^>]*)>>\s*;\s*(.*)$", line, flags=re.I)
        if not m or qidx == 0:
            continue
        rank = int(m.group(1))
        name = m.group(2).strip()
        formula = m.group(3).strip()
        rest = m.group(4)

        def field(key: str) -> str:
            mm = re.search(rf"\b{re.escape(key)}\s*:\s*([^;]+)", rest, flags=re.I)
            return mm.group(1).strip().rstrip(".") if mm else ""

        def num(x: str) -> float:
            try:
                return float(str(x).strip().rstrip("."))
            except Exception:
                return 0.0

        libm = re.search(r"\bLib\s*:\s*<<([^>]*)>>", rest, flags=re.I)
        idm = re.search(r"\bId\s*:\s*([^.;]+)", rest, flags=re.I)
        rim = re.search(r"\bRI\s*:?\s*([^;]+)", rest, flags=re.I)
        ri = rim.group(1).strip().rstrip(".") if rim else ""
        hits.append(Hit(
            query_index=qidx,
            query_name=current_query_name,
            header=current_header,
            rank=rank,
            name=name,
            formula=formula,
            mf=num(field("MF")),
            rmf=num(field("RMF")),
            prob=num(field("Prob")),
            cas=field("CAS"),
            mw=num(field("Mw")),
            lib=libm.group(1).strip() if libm else "",
            id=idm.group(1).strip() if idm else "",
            ri=ri,
        ))
    return hits


def parse_srcreslt_file(path: Path) -> List[Hit]:
    return parse_srcreslt_text(path.read_text(encoding=native_text_encoding(), errors="replace"))


CSV_HEADER_MAP = {
    "query_index": "QueryIndex", "query_name": "QueryName", "header": "Header", "rank": "Rank",
    "name": "Name", "formula": "Formula", "mf": "MF", "rmf": "RMF", "prob": "Prob",
    "cas": "CAS", "mw": "MW", "lib": "Lib", "id": "Id", "ri": "RI",
}


def _write_hits(hits: Iterable[Hit], path: Path, mode: str, write_header: bool) -> None:
    with path.open(mode, newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(CSV_HEADER_MAP.values()))
        if write_header:
            w.writeheader()
        for row in (asdict(h) for h in hits):
            w.writerow({CSV_HEADER_MAP[k]: v for k, v in row.items()})


def write_hits_csv(hits: Iterable[Hit], path: Path) -> None:
    _write_hits(hits, path, "w", True)


def append_hits_csv(hits: Iterable[Hit], path: Path, index_offset: int = 0) -> Path:
    """Append a batch of hits to ONE result CSV per analysis file.

    `index_offset` renumbers QueryIndex into the global spectrum numbering of the
    source run, so rows stay unique when a run is split into several batches.
    The header is written only when the file is created.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists() or path.stat().st_size == 0
    if index_offset:
        hits = [replace(h, query_index=h.query_index + index_offset) for h in hits]
    _write_hits(hits, path, "a", fresh)
    return path


def write_hits_json(hits: Iterable[Hit], path: Path) -> None:
    path.write_text(json.dumps([asdict(h) for h in hits], ensure_ascii=False, indent=2), encoding="utf-8")


def autoimp_writability(workdir: Path) -> str:
    """Report whether AUTOIMP.MSD can be created/updated in the NIST work directory."""
    autoimp = workdir / "AUTOIMP.MSD"
    if autoimp.exists():
        return f"AUTOIMP.MSD already present ({file_state(autoimp)}); its secondary locator will be reused."
    probe = workdir / "PYGCMS_WRITE_TEST.tmp"
    try:
        workdir.mkdir(parents=True, exist_ok=True)
        probe.write_text("test\r\n", encoding=native_text_encoding(), errors="replace")
        probe.unlink()
        return "OK: work directory is writable (AUTOIMP.MSD can be created)."
    except Exception as e:
        return f"NOT writable ({e}). Run once as Administrator or create AUTOIMP.MSD manually."


def cmd_search(args: argparse.Namespace) -> int:
    nistms = Path(clean_path_text(args.nistms)) if args.nistms else discover_nistms()
    if not nistms:
        raise FileNotFoundError("Could not discover NISTMS$.EXE. Pass --nistms explicitly.")
    nist_workdir = Path(clean_path_text(args.nist_workdir)) if getattr(args, "nist_workdir", None) else None
    srcreslt = run_nist_search(
        nistms=nistms,
        msp=Path(args.msp),
        timeout=args.timeout,
        append_mode=args.append_mode,
        create_autoimp=not args.no_create_autoimp,
        dry_run=args.dry_run,
        nist_workdir=nist_workdir,
        par=args.par,
        instrument=not getattr(args, "no_instrument", False),
        prelaunch=args.prelaunch,
    )
    if args.dry_run:
        return 0
    hits = parse_srcreslt_file(srcreslt)
    print(f"Parsed {len(hits)} hits from {srcreslt}")
    print(f"SRCREADY count: {read_srcready_count(ready_path(srcreslt.parent) or srcreslt.parent / 'SRCREADY.TXT')}")
    if not hits:
        print("WARNING: 0 Hit lines parsed. NIST may have imported spectra but printed no hits; check Automation and library selection.")
    if args.csv:
        write_hits_csv(hits, Path(args.csv))
        print(f"CSV written: {args.csv}")
    if args.json:
        write_hits_json(hits, Path(args.json))
        print(f"JSON written: {args.json}")
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    nistms = Path(clean_path_text(args.nistms)) if args.nistms else discover_nistms()
    if not nistms:
        raise FileNotFoundError("Could not discover NISTMS$.EXE. Pass --nistms explicitly.")
    pid = launch_nist_gui(nistms, instrument=not args.no_instrument)
    print(f"Launched NIST MS Search: {nistms} (pid {pid})")
    print("In NIST MS Search, open Options > Library Search Options > Automation and:")
    print("  1) enable Automation, 2) set 'Number of hits to print' > 0, 3) select at least one library.")
    return 0


def cmd_background_test(args: argparse.Namespace) -> int:
    nistms = Path(clean_path_text(args.nistms)) if args.nistms else discover_nistms()
    if not nistms:
        raise FileNotFoundError("Could not discover NISTMS$.EXE. Pass --nistms explicitly.")
    nist_workdir = Path(clean_path_text(args.nist_workdir)) if getattr(args, "nist_workdir", None) else None
    token = args.token or make_run_token()
    msp = default_bridge_tempdir() / f"pygcms_background_search_test_{token}.msp"
    create_demo_msp(msp, token)
    srcreslt = run_nist_search(
        nistms=nistms,
        msp=msp,
        timeout=args.timeout,
        append_mode="OVERWRITE",
        create_autoimp=not args.no_create_autoimp,
        dry_run=False,
        nist_workdir=nist_workdir,
        par=args.par,
        instrument=not getattr(args, "no_instrument", False),
        prelaunch=args.prelaunch,
    )
    hits = parse_srcreslt_file(srcreslt)
    print("Background NIST test completed.")
    print("SRCRESLT:", srcreslt)
    _rp = ready_path(srcreslt.parent) or srcreslt.parent / "SRCREADY.TXT"
    print("SRCREADY:", _rp, "count=", read_srcready_count(_rp))
    print("Token:", token)
    print("Hits parsed:", len(hits))
    if not hits:
        print("WARNING: NIST created SRCRESLT.TXT but no Hit lines were parsed.")
        print("Check Automation: enabled; Number of hits to print > 0; at least one library selected.")
        print(read_text_if_exists(srcreslt, limit=2000))
        return 2
    for h in hits[:5]:
        print(f"Hit {h.rank}: {h.name} MF={h.mf} RMF={h.rmf} Prob={h.prob} Lib={h.lib}")
    return 0


# NIST is always brought up first now (see ensure_nist_running), so the probe only
# needs to vary the switches themselves.
PROBE_VARIANTS = [
    # (label, instrument, instrument_last, prelaunch)
    ("A: /PAR=2 only (no /INSTRUMENT)",          False, False, False),
    ("B: /INSTRUMENT /PAR=2  (default)",         True,  False, False),
    ("C: /PAR=2 /INSTRUMENT  (reversed order)",  True,  True,  False),
]


def cmd_probe(args: argparse.Namespace) -> int:
    """Try every plausible NISTMS$.EXE command-line form and report which one
    actually makes NIST write SRCREADY.TXT / SRCRESLT.TXT.

    This exists because the correct switch combination differs between NIST
    builds and because a switch NIST does not recognise can make it ignore
    /PAR=2 entirely (spectra import and are searched in the GUI, but no
    automation files are written -- exactly the "15 hits on screen, no file"
    symptom).
    """
    nistms = Path(clean_path_text(args.nistms)) if args.nistms else discover_nistms()
    if not nistms:
        raise FileNotFoundError("Could not discover NISTMS$.EXE. Pass --nistms explicitly.")
    nist_workdir = Path(clean_path_text(args.nist_workdir)) if getattr(args, "nist_workdir", None) else None

    tempdir = nist_safe_tempdir()
    msp = tempdir / "PYGCMS_PROBE.MSP"
    create_demo_msp(msp)

    print("=" * 68)
    print("PyGCMS NIST automation PROBE")
    print("NISTMS$.EXE :", nistms)
    print("Work dir    :", nist_workdir or nistms.resolve().parent)
    print("Probe MSP   :", msp)
    print(f"Timeout per variant: {args.timeout:.0f} s")
    print("=" * 68)
    print()
    print("NIST MS Search will be started automatically if it is not running.")
    print("Make sure that in NIST:")
    print("  Options > Library Search Options > Automation  ->  Automation ON")
    print("  'Number of First Hits to Print' >= 15, and select >= 1 library.")
    print()

    winners: List[str] = []
    for label, instrument, instrument_last, prelaunch in PROBE_VARIANTS:
        cmd = build_search_command(nistms, par=2, instrument=instrument, instrument_last=instrument_last)
        print("-" * 68)
        print(label)
        print("  command:", " ".join(cmd))
        try:
            srcreslt = run_nist_search(
                nistms=nistms,
                msp=msp,
                timeout=args.timeout,
                nist_workdir=nist_workdir,
                par=2,
                instrument=instrument,
                instrument_last=instrument_last,
                prelaunch=prelaunch,
                retry_with_prelaunch=False,
            )
        except TimeoutError:
            print("  RESULT: no SRCREADY.TXT written  -> FAIL")
            continue
        except Exception as e:
            print(f"  RESULT: error -> {e}")
            continue
        hits = parse_srcreslt_file(srcreslt)
        rp = ready_path(srcreslt.parent)
        n = read_srcready_count(rp) if rp else 0
        print(f"  RESULT: ready file written ({rp.name if rp else '?'}), "
              f"spectra searched={n}, hits parsed={len(hits)}  -> PASS")
        winners.append(label)
        if hits:
            print(f"  top hit: {hits[0].name} (MF={hits[0].mf})")
        if not args.all:
            break

    print()
    print("=" * 68)
    if winners:
        print("WORKING VARIANT(S):")
        for w in winners:
            print("  ", w)
        print()
        print("If A works and B does not, rerun the search with --no-instrument")
        print("(the /INSTRUMENT switch is not accepted by this NIST build).")
        return 0

    print("NO VARIANT PRODUCED SRCREADY.TXT.")
    print()
    print("This means NISTMS$.EXE never ran a background search. Check, in order:")
    print("  1. Options > Library Search Options > Automation tab: the toggle button must")
    print("     read 'Automation' (enabled), not 'No Automation'. This is a DIFFERENT")
    print("     control from 'Automatic Search On' in the Search tab. Only the Automation")
    print("     toggle causes SRCREADY/SRCRESLT to be written.")
    print("  2. 'Number of First Hits to Print' must be > 0.")
    print("  3. At least one library must be selected for searching.")
    print("  4. C:\\NIST20\\MSSEARCH must be writable by this user account.")
    print("  5. No second NIST MS Search instance from another install is running.")
    print("=" * 68)
    return 2


def cmd_parse(args: argparse.Namespace) -> int:
    hits = parse_srcreslt_file(Path(args.srcreslt))
    print(f"Parsed {len(hits)} hits from {args.srcreslt}")
    if args.csv:
        write_hits_csv(hits, Path(args.csv))
        print(f"CSV written: {args.csv}")
    if args.json:
        write_hits_json(hits, Path(args.json))
        print(f"JSON written: {args.json}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    nistms = Path(clean_path_text(args.nistms)) if args.nistms else discover_nistms()
    print("PyGCMS NIST bridge doctor")
    print("OS:", os.name)
    print("NISTMS$.EXE:", nistms or "not found")
    if nistms:
        print("NISTMS exists:", nistms.exists())
        print("NISTMS is file:", nistms.is_file() if nistms.exists() else False)
    print("WIN.INI [NISTMS] Path32:", win_ini_value("NISTMS", "Path32") or "(none)")
    ini_workdir = win_ini_value("NISTMS", "WorkDir32")
    print("WIN.INI [NISTMS] WorkDir32:", ini_workdir or "(none)")
    if getattr(args, "nist_workdir", None):
        nist_workdir = Path(clean_path_text(args.nist_workdir))
    elif nistms:
        # Effective work directory follows the selected exe (handles multi-version installs).
        nist_workdir = nistms.resolve().parent
    else:
        nist_workdir = discover_nist_workdir(None)
    print("NIST WorkDir (primary/effective):", nist_workdir)
    if nistms:
        print("Candidate NIST result/work dirs:")
        for d in result_directories(nistms, nist_workdir):
            print("  ", d)
    if ini_workdir:
        try:
            ini_path = Path(ini_workdir)
            if ini_path.name.lower() == "nistms$.exe":
                ini_path = ini_path.parent
            if nistms and ini_path.exists() and ini_path.resolve() != nist_workdir.resolve():
                print(f"  [warning] WIN.INI WorkDir32 ({ini_path}) points to a DIFFERENT NIST folder than the "
                      f"selected exe. This usually means an older NIST install is still registered. The bridge "
                      f"uses the selected exe's folder; make sure nistms_path.txt points to the CURRENT version.")
        except Exception:
            pass
    print("AUTOIMP.MSD:", nist_workdir / "AUTOIMP.MSD", file_state(nist_workdir / "AUTOIMP.MSD"))
    print("AUTOIMP writability:", autoimp_writability(nist_workdir))
    for _n in READY_NAMES + RESLT_NAMES:
        print(f"{_n}:", nist_workdir / _n, file_state(nist_workdir / _n))
    print("Bridge tempdir:", default_bridge_tempdir())
    if nistms:
        print("Search command:", " ".join(build_search_command(nistms, par=2, instrument=True)))
    print("Note: PyGCMS Pipeline uses /INSTRUMENT /PAR=2 by default for NIST20/NIST23 background automation.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Bridge between Py-GC/MS MSP output and licensed NIST MS Search automation")
    sub = p.add_subparsers(required=True)

    s = sub.add_parser("search", help="Run NIST MS Search against an MSP file and parse SRCRESLT.TXT")
    s.add_argument("--msp", required=True, help="Input MSP file created by the browser app")
    s.add_argument("--nistms", help="Full path to NISTMS$.EXE, e.g. C:\\NIST23\\MSSEARCH\\NISTMS$.EXE")
    s.add_argument("--nist-workdir", help="Optional NIST MS Search WorkDir32. Usually auto-detected from WIN.INI.")
    s.add_argument("--timeout", type=float, default=180.0, help="Seconds to wait for SRCREADY/SRCRESLT")
    s.add_argument("--append-mode", default="OVERWRITE", choices=["OVERWRITE", "APPEND", "Overwrite", "Append"], help="How NIST imports spectra into Spec List")
    s.add_argument("--par", type=int, default=2, help="Value for the /PAR switch that triggers the search (default 2)")
    s.add_argument("--no-instrument", action="store_true", help="Do not pass /INSTRUMENT before /PAR=2 (not recommended for NIST20/NIST23)")
    s.add_argument("--prelaunch", action="store_true", help="Bring NIST up (NISTMS$.EXE /INSTRUMENT) before triggering the search")
    s.add_argument("--csv", help="Output CSV for browser import")
    s.add_argument("--json", help="Optional JSON output")
    s.add_argument("--no-create-autoimp", action="store_true", help="Do not create AUTOIMP.MSD if missing")
    s.add_argument("--dry-run", action="store_true", help="Show files/command without launching NIST")
    s.set_defaults(func=cmd_search)

    l = sub.add_parser("launch", help="Just start NIST MS Search (no search) so Automation can be configured")
    l.add_argument("--nistms", help="Full path to NISTMS$.EXE")
    l.add_argument("--no-instrument", action="store_true", help="Do not pass /INSTRUMENT when launching")
    l.set_defaults(func=cmd_launch)

    pr = sub.add_parser("probe", help="Try every NISTMS$.EXE switch combination and report which one writes SRCREADY.TXT")
    pr.add_argument("--nistms", help="Full path to NISTMS$.EXE")
    pr.add_argument("--nist-workdir", help="Optional NIST MS Search WorkDir32")
    pr.add_argument("--timeout", type=float, default=45.0, help="Seconds to wait per variant (default 45)")
    pr.add_argument("--all", action="store_true", help="Test every variant instead of stopping at the first success")
    pr.set_defaults(func=cmd_probe)

    q = sub.add_parser("parse", help="Parse an existing SRCRESLT.TXT into CSV/JSON")
    q.add_argument("--srcreslt", required=True, help="Path to SRCRESLT.TXT")
    q.add_argument("--csv", help="Output CSV for browser import")
    q.add_argument("--json", help="Optional JSON output")
    q.set_defaults(func=cmd_parse)

    bg = sub.add_parser("background-test", help="Run a tiny /PAR=2 background NIST automation self-test")
    bg.add_argument("--nistms", help="Full path to NISTMS$.EXE")
    bg.add_argument("--nist-workdir", help="Optional NIST MS Search WorkDir")
    bg.add_argument("--timeout", type=float, default=120.0)
    bg.add_argument("--token", default="", help="Optional token to put in the test spectrum name")
    bg.add_argument("--par", type=int, default=2, help="Value for the /PAR switch")
    bg.add_argument("--no-instrument", action="store_true", help="Do not pass /INSTRUMENT before /PAR=2 (not recommended for NIST20/NIST23)")
    bg.add_argument("--prelaunch", action="store_true", help="Bring NIST GUI up before the search")
    bg.add_argument("--no-create-autoimp", action="store_true", help="Do not create AUTOIMP.MSD if missing")
    bg.set_defaults(func=cmd_background_test)

    d = sub.add_parser("doctor", help="Print NIST automation paths and bridge diagnostics")
    d.add_argument("--nistms", help="Full path to NISTMS$.EXE")
    d.add_argument("--nist-workdir", help="Optional NIST MS Search WorkDir32")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)
