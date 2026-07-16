#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Local HTTP bridge for the PyGCMS Pipeline browser app and a legally licensed NIST MS Search installation.

This server listens only on localhost by default. It does NOT read, copy, extract,
or redistribute NIST library spectra. It accepts user-generated MSP spectra from
this app, launches the user's local NISTMS$.EXE through the documented automation
route, parses NIST's own SRCRESLT.TXT output, and returns hit lists to the browser.

Typical Windows use:
  python scripts\nist_mssearch_bridge_server.py --nistms "C:\NIST23\MSSEARCH\NISTMS$.EXE"

Then open software/index.html and click:
  接続確認 → 自動NIST検索 → CSV出力
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
import urllib.error
import re
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import the command-line bridge in the same directory.
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from nist_mssearch_bridge import (  # noqa: E402
    Hit,
    autoimp_writability,
    build_search_command,
    clean_path_text,
    default_bridge_tempdir,
    discover_nist_workdir,
    discover_nistms,
    file_state,
    launch_nist_gui,
    parse_srcreslt_file,
    read_srcready_count,
    search_hits,
    ready_path,
    reslt_path,
    READY_NAMES,
    RESLT_NAMES,
    read_text_if_exists,
    parse_srcreslt_text,
    run_nist_search,
    write_hits_csv,
    append_hits_csv,
)


def hits_to_groups(hits: List[Hit]) -> List[Dict[str, Any]]:
    by: Dict[int, Dict[str, Any]] = {}
    for h in hits:
        g = by.setdefault(h.query_index, {
            "query_index": h.query_index,
            "query_name": h.query_name,
            "header": h.header or h.query_name or f"Query {h.query_index}",
            "hits": [],
        })
        g["hits"].append({
            "rank": h.rank,
            "name": h.name,
            "formula": h.formula,
            "mf": h.mf,
            "rmf": h.rmf,
            "prob": h.prob,
            "cas": h.cas,
            "mw": h.mw,
            "lib": h.lib,
            "id": h.id,
            "ri": h.ri,
        })
    groups = [by[k] for k in sorted(by)]
    for g in groups:
        g["hits"].sort(key=lambda x: x.get("rank", 9999))
    return groups


def hits_to_csv_string(hits: List[Hit]) -> str:
    buf = io.StringIO()
    fieldnames = ["QueryIndex", "QueryName", "Header", "Rank", "Name", "Formula", "MF", "RMF", "Prob", "CAS", "MW", "Lib", "Id", "RI"]
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for h in hits:
        w.writerow({
            "QueryIndex": h.query_index,
            "QueryName": h.query_name,
            "Header": h.header,
            "Rank": h.rank,
            "Name": h.name,
            "Formula": h.formula,
            "MF": h.mf,
            "RMF": h.rmf,
            "Prob": h.prob,
            "CAS": h.cas,
            "MW": h.mw,
            "Lib": h.lib,
            "Id": h.id,
            "RI": h.ri,
        })
    return buf.getvalue()



def _extract_text_from_openai_response(obj: Dict[str, Any]) -> str:
    if isinstance(obj.get("output_text"), str):
        return obj["output_text"]
    parts: List[str] = []
    for out in obj.get("output", []) or []:
        for c in out.get("content", []) or []:
            txt = c.get("text") or c.get("output_text")
            if isinstance(txt, str):
                parts.append(txt)
    return "\n".join(parts)


def _extract_json_from_text(text: str) -> Any:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        return json.loads(m.group(1))
    raise ValueError("AI response did not contain valid JSON")


def openai_ai_qc(api_key: str, model: str, items: List[Dict[str, Any]], timeout: float = 120.0, max_candidates: int = 15, reasoning_effort: str = "medium", sample_matrix: str = "dry_sediment_bulk", enable_critic: bool = True) -> Dict[str, Any]:
    """Call OpenAI Responses API for controlled candidate curation.

    The model is constrained to choose only from supplied NIST candidates or return
    selected_rank=0 (unassigned/contaminant).  The API key is used only for this
    request and is not saved by the bridge.
    """
    if not api_key or not api_key.strip():
        raise ValueError("OpenAI API key is empty")
    if not model or not model.strip():
        model = "gpt-5.5"

    matrix_labels = {
        "dry_sediment_bulk": "dried bulk sediment",
        "dry_lake_sediment_bulk": "dried bulk lake sediment",
        "dry_river_sediment_bulk": "dried bulk river sediment",
        "dry_soil_bulk": "dried bulk soil",
        "dry_forest_soil_bulk": "dried bulk forest soil",
        "dry_agricultural_soil_bulk": "dried bulk agricultural soil",
        "humic_acid": "humic acid or humic-like organic matter",
        "sludge": "dried sludge or organic mud",
    }
    sample_matrix = sample_matrix or "dry_sediment_bulk"
    sample_label = matrix_labels.get(sample_matrix, sample_matrix)

    if "soil" in sample_matrix:
        context = (
            "The sample is dried bulk soil. Prioritize plausible Py-GC/MS products from "
            "terrestrial plant residues, lignin, cellulose/hemicellulose, root-derived organic matter, "
            "microbial residues, lipids/waxes, soil humification, and black carbon. Plausible classes include "
            "phenols, methoxyphenols, furans, pyrroles, pyridines, indoles, nitriles, amides, alkanes, alkenes, "
            "fatty acids/esters, alkylbenzenes, and PAHs. Flag siloxanes, phthalates, column bleed, solvent/septum artifacts, "
            "and chemically implausible P/S/halogen-rich candidates."
        )
    elif "humic" in sample_matrix:
        context = (
            "The sample is humic acid or humic-like natural organic matter. Prioritize aromatic and heteroatom-containing "
            "Py-GC/MS products such as phenols, alkylphenols, methoxyphenols, benzenes, alkylbenzenes, furans, pyrroles, "
            "pyridines, indoles, nitriles, and PAH-like products. Flag common artifacts and chemically implausible candidates."
        )
    elif "sludge" in sample_matrix:
        context = (
            "The sample is dried sludge or organic mud. Protein/microbial nitrogen compounds, lipids/fatty acids, sterols, "
            "sulfur compounds, surfactant-related compounds, and humic-like products may be plausible. Anthropogenic compounds "
            "can occur, but siloxanes, phthalates, column bleed, and artifacts must be flagged rather than over-assigned."
        )
    else:
        context = (
            "The sample is dried bulk sediment. Prioritize plausible Py-GC/MS products from aquatic/sedimentary organic matter, "
            "microbial residues, humic-like material, lipids, lignin-derived inputs, and redox-related sulfur chemistry. Plausible classes "
            "include phenols, alkylphenols, methoxyphenols, furans, pyrroles, pyridines, indoles, nitriles, amides, thiophenes, "
            "alkanes, alkenes, fatty acids/esters, alkylbenzenes, and PAHs. Flag siloxanes, phthalates, column bleed, solvent/septum artifacts, "
            "and chemically implausible P/S/halogen-rich candidates."
        )

    system = (
        "You are a conservative analytical chemist performing AI-assisted candidate curation for Py-GC/MS. "
        "This is not confirmed identification. You must choose only from the provided NIST candidates or return selected_rank=0. "
        "Never invent a compound name. Prefer tentative or unassigned over over-confident assignment. "
        "Evaluate each candidate by spectral match, reverse match, major ions if present, retention/RI if present, "
        "Py-GC/MS product plausibility, sample matrix plausibility, elemental/structural plausibility, and contamination/artifact risk. "
        "If enable_critic is true, perform a final critical review and downgrade/reject over-assigned candidates. "
        "Return strict JSON only. No prose outside JSON. For transparency, include candidate_decisions for every provided candidate with rank, score, decision, and a brief reason. The reasons must explain why the selected candidate was selected and why each non-selected candidate was rejected or retained but not selected."
    )
    user = {
        "task": "For each item, return one conservative candidate-curation decision.",
        "sample_matrix": sample_matrix,
        "sample_label": sample_label,
        "sample_context": context,
        "enable_critic": bool(enable_critic),
        "max_candidate_rank": int(max_candidates),
        "selection_rules": [
            "selected_rank must be 1..max_candidate_rank or 0 for unassigned/rejected-all",
            "do not invent compound names",
            "evaluate all supplied NIST candidates up to max_candidate_rank, not only the first two",
            "include candidate_decisions for every supplied candidate so the CSV can preserve selection and rejection reasons",
            "confirmed is allowed only when authentic standard evidence is present in the input; otherwise use probable/tentative/unassigned/contaminant_or_artifact",
            "flag siloxanes/TMS/column bleed, phthalates/plasticizers, deuterated/internal standards, solvent/septum artifacts, implausible organophosphorus/sulfate formulas, unsupported halogen-rich candidates, and low-match candidates",
        ],
        "required_json_shape": {
            "decisions": [
                {
                    "id": "input id",
                    "selected_rank": "1-{} or 0".format(max_candidates),
                    "selected_name": "candidate name or unassigned",
                    "action": "accepted|reselected|rejected-all",
                    "annotation_level": "probable|tentative|unassigned|contaminant_or_artifact",
                    "confidence": "high|medium|low",
                    "compound_class": "short class label",
                    "origin_interpretation": "short environmental source/process interpretation",
                    "total_score": "0-20 integer",
                    "reason": "short reason",
                    "qc_flags": "semicolon separated flags",
                    "critic_decision": "keep|downgrade|reject|not_run",
                    "critic_reason": "short critical-review reason",
                    "candidate_scores_summary": "rank:score:decision; rank:score:decision",
                    "candidate_decisions": [
                        {"rank": 1, "score": 0, "decision": "selected|not_selected|rejected", "reason": "brief candidate-specific reason"}
                    ]
                }
            ]
        },
        "items": items,
    }
    selected_model = model.strip() or "gpt-5.5"
    effort = (reasoning_effort or "medium").strip().lower()
    if effort not in {"none", "low", "medium", "high", "xhigh"}:
        effort = "medium"
    body = {
        "model": selected_model,
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
        ],
        "max_output_tokens": 8000,
    }
    if selected_model.lower().startswith(("gpt-5", "o")) and effort != "none":
        body["reasoning"] = {"effort": effort}
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=data,
        headers={
            "Authorization": "Bearer " + api_key.strip(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"OpenAI API HTTP {e.code}: {detail}")
    obj = json.loads(raw)
    text = _extract_text_from_openai_response(obj)
    parsed = _extract_json_from_text(text)
    if isinstance(parsed, list):
        parsed = {"decisions": parsed}
    if not isinstance(parsed, dict) or not isinstance(parsed.get("decisions"), list):
        raise ValueError("AI JSON did not include decisions[]")
    return {"ok": True, "model": selected_model, "reasoning_effort": effort, "sample_matrix": sample_matrix, "enable_critic": bool(enable_critic), "decisions": parsed["decisions"], "usage": obj.get("usage", {})}



def safe_output_filename(name: str) -> str:
    """Return a safe basename for browser-submitted output files."""
    s = Path(str(name or "output.txt")).name.strip().replace("\x00", "")
    s = re.sub(r"[<>:\"/\\|?*]+", "_", s)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("._ ")
    return s[:180] or "output.txt"


def safe_run_id(value: str) -> str:
    s = str(value or time.strftime("PyGCMS_batch_%Y%m%d_%H%M%S"))
    s = re.sub(r"[^0-9A-Za-z._-]+", "_", s).strip("._-")
    return s[:80] or time.strftime("PyGCMS_batch_%Y%m%d_%H%M%S")


class AppState:
    def __init__(
        self,
        nistms: Optional[Path],
        nist_workdir: Optional[Path],
        port: int,
        host: str,
        bridge_workdir: Optional[Path],
        create_autoimp: bool,
        default_timeout: float,
    ):
        self.nistms = nistms
        self.nist_workdir = nist_workdir
        self.port = port
        self.host = host
        self.workdir = bridge_workdir or (default_bridge_tempdir() / "http")
        self.create_autoimp = create_autoimp
        self.default_timeout = default_timeout
        self.started_at = time.time()
        self.last_search: Dict[str, Any] = {}

    def resolve_nistms(self, override: Optional[str] = None) -> Path:
        if override:
            p = Path(clean_path_text(override)).expanduser()
            if p.exists():
                return p
            raise FileNotFoundError(f"NISTMS$.EXE not found: {p}")
        if self.nistms and self.nistms.exists():
            return self.nistms
        p = discover_nistms()
        if p and p.exists():
            self.nistms = p
            return p
        raise FileNotFoundError("NISTMS$.EXE could not be found. Start the bridge with --nistms or enter the path in the app.")

    def resolve_nist_workdir(self, nistms: Optional[Path] = None, override: Optional[str] = None) -> Path:
        if override:
            p = Path(clean_path_text(override)).expanduser()
            if p.exists():
                return p
            raise FileNotFoundError(f"NIST MS Search WorkDir not found: {p}")
        if self.nist_workdir and self.nist_workdir.exists():
            return self.nist_workdir
        # Follow the selected exe's own folder (correct even with multiple NIST versions
        # installed and a stale WIN.INI WorkDir32).
        base = nistms or self.nistms
        if base and Path(base).exists():
            return Path(base).resolve().parent
        p = discover_nist_workdir(base)
        if p.exists():
            self.nist_workdir = p
            return p
        return p


STATE: Optional[AppState] = None


class Handler(BaseHTTPRequestHandler):
    server_version = "PyGCMS-Pipeline/1.3.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Invalid JSON request: {e}")

    def _send_json(self, obj: Any, status: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error_json(self, message: str, status: int = 500, **extra: Any) -> None:
        payload = {"ok": False, "error": message}
        payload.update(extra)
        self._send_json(payload, status=status)

    def _health_payload(self) -> Dict[str, Any]:
        assert STATE is not None
        nistms: Optional[str] = None
        nistms_exists = False
        nist_workdir: Optional[str] = None
        nist_workdir_exists = False
        autoimp = srcreslt = srcready = ""
        autoimp_writable = ""
        search_command = "NISTMS$.EXE /INSTRUMENT /PAR=2"
        try:
            p = STATE.resolve_nistms()
            nistms = str(p)
            nistms_exists = p.exists()
            search_command = " ".join(build_search_command(p, par=2, instrument=True))
            wd = STATE.resolve_nist_workdir(p)
            nist_workdir = str(wd)
            nist_workdir_exists = wd.exists()
            autoimp_path = wd / "AUTOIMP.MSD"
            srcreslt_path = reslt_path(wd) or wd / "SRCRESLT.TXT"
            srcready_path = ready_path(wd) or wd / "SRCREADY.TXT"
            autoimp = file_state(autoimp_path)
            autoimp_writable = autoimp_writability(wd)
            srcreslt = file_state(srcreslt_path)
            srcready = file_state(srcready_path)
        except Exception:
            pass
        return {
            "ok": True,
            "service": "PyGCMS Pipeline",
            "version": "1.3.0",
            "host": STATE.host,
            "port": STATE.port,
            "nistms": nistms,
            "nistms_exists": nistms_exists,
            "nist_workdir": nist_workdir,
            "nist_workdir_exists": nist_workdir_exists,
            "bridge_workdir": str(STATE.workdir),
            "workdir": str(STATE.workdir),  # backward-compatible key
            "autoimp_state": autoimp,
            "autoimp_writable": autoimp_writable,
            "srcreslt_state": srcreslt,
            "srcready_state": srcready,
            "required_command": "NISTMS$.EXE /INSTRUMENT /PAR=2",
            "search_command": search_command,
            "uptime_s": round(time.time() - STATE.started_at, 1),
            "last_search": STATE.last_search,
            "ai_proxy": True,
            "batch_save_endpoint": True,
            "batch_default_output_dir": str(STATE.workdir / "batch_outputs"),
            "note": "NIST library files are not read by this bridge; only user MSP input and NISTMS$.EXE search outputs are parsed. Optional OpenAI API calls use the API key supplied per request or OPENAI_API_KEY environment variable; the key is not written to disk by the bridge. The /save_outputs endpoint saves only browser-generated CSV/text outputs to a user-specified local folder or to bridge_work/batch_outputs.",
        }

    def _send_html(self, html: str, status: int = 200) -> None:
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_app(self) -> None:
        """Serve the released English browser application from software/index.html."""
        root = Path(__file__).resolve().parents[1]
        app = root / "software" / "index.html"
        if not app.exists():
            self._send_html(
                "<h1>PyGCMS Pipeline app not found</h1>"
                "<p>software/index.html was not found. Please extract the archive fully.</p>",
                status=404,
            )
            return
        data = app.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        assert STATE is not None
        if self.path.startswith("/health") or self.path.startswith("/diagnose"):
            self._send_json(self._health_payload())
            return
        if self.path == "/" or self.path.startswith("/app"):
            self._serve_app()
            return
        if self.path.startswith("/status"):
            h = self._health_payload()
            ok = "YES" if h.get("nistms_exists") else "NO - set nistms_path.txt to NISTMS$.EXE"
            html = """<!doctype html><html lang='en'><meta charset='utf-8'><title>PyGCMS NIST Bridge Status</title>
<style>body{{font-family:Segoe UI,Meiryo,sans-serif;margin:32px;line-height:1.7}}code,pre{{background:#f3f3f3;padding:2px 5px;border-radius:3px}}.ok{{color:#087a52;font-weight:700}}.bad{{color:#b00020;font-weight:700}}a.btn{{display:inline-block;background:#0a8f6a;color:white;padding:9px 14px;border-radius:5px;text-decoration:none;margin:12px 0}}</style>
<h1>PyGCMS Pipeline local bridge</h1><p class='ok'>Bridge is running.</p><p>NISTMS$.EXE found: <b>{ok}</b></p><p>Path: <code>{nistms}</code></p><p>NIST WorkDir: <code>{nist_workdir}</code></p><p>Bridge WorkDir: <code>{bridge_workdir}</code></p><p>AUTOIMP.MSD: <code>{autoimp}</code></p><p>SRCREADY.TXT: <code>{srcready}</code></p><p>SRCRESLT.TXT: <code>{srcreslt}</code></p><p>Command used for search: <code>{cmd}</code></p><p><a class='btn' href='/app'>Open PyGCMS Pipeline</a></p><p>JSON health endpoint: <a href='/health'>/health</a></p></html>""".format(
                ok=ok,
                nistms=h.get('nistms') or '',
                nist_workdir=h.get('nist_workdir') or '',
                bridge_workdir=h.get('bridge_workdir') or '',
                autoimp=h.get('autoimp_state') or '',
                srcready=h.get('srcready_state') or '',
                srcreslt=h.get('srcreslt_state') or '',
                cmd=h.get('required_command') or '',
            )
            self._send_html(html)
            return
        self._send_error_json("Not found", status=404)

    def do_POST(self) -> None:
        assert STATE is not None
        try:
            if self.path.startswith("/search"):
                self._handle_search()
            elif self.path.startswith("/ai_qc"):
                self._handle_ai_qc()
            elif self.path.startswith("/save_outputs"):
                self._handle_save_outputs()
            elif self.path.startswith("/parse"):
                self._handle_parse()
            elif self.path.startswith("/launch"):
                self._handle_launch()
            else:
                self._send_error_json("Not found", status=404)
        except Exception as e:
            self._send_error_json(str(e), status=500)

    def _handle_save_outputs(self) -> None:
        """Save browser-generated batch CSV/text outputs to a local folder.

        Robust Windows implementation:
        - creates the base and run folders before every write,
        - sanitizes all filenames to basenames,
        - uses plain open(..., 'w') instead of Path.write_text to avoid
          version/path edge cases,
        - returns a detailed error message if a write fails.
        """
        assert STATE is not None
        payload = self._read_json()
        files = payload.get("files") or []
        if not isinstance(files, list) or not files:
            raise ValueError("files must be a non-empty list")

        output_dir_raw = clean_path_text(payload.get("output_dir") or "")
        if output_dir_raw:
            base = Path(output_dir_raw).expanduser()
        else:
            base = STATE.workdir / "batch_outputs"

        run_id = safe_run_id(payload.get("run_id") or "")
        if bool(payload.get("make_run_subdir", True)) and run_id:
            base = base / run_id

        # Convert to an absolute path early; Windows relative paths from service/cmd
        # sessions can otherwise point to unexpected locations.
        try:
            base = base.resolve(strict=False)
        except TypeError:
            base = Path(os.path.abspath(str(base)))
        except Exception:
            base = Path(os.path.abspath(str(base)))

        try:
            os.makedirs(str(base), exist_ok=True)
        except Exception as exc:
            raise RuntimeError(f"Could not create output directory: {base} :: {exc}")

        saved: List[str] = []
        errors: List[str] = []
        for item in files:
            if not isinstance(item, dict):
                continue
            filename = safe_output_filename(item.get("filename") or item.get("name") or "output.csv")
            content = item.get("content")
            if content is None:
                content = ""
            target = base / filename
            try:
                # Re-create immediately before writing; this is intentionally redundant
                # because some long Windows runs can lose/rename folders during testing.
                os.makedirs(str(target.parent), exist_ok=True)
                # Defense-in-depth: sanitized filename must stay directly under base.
                try:
                    base_abs = os.path.abspath(str(base))
                    target_abs = os.path.abspath(str(target))
                    if os.path.dirname(target_abs).lower() != base_abs.lower():
                        raise ValueError("unsafe output path")
                except Exception as path_exc:
                    raise RuntimeError(f"Output path validation failed: {path_exc}")
                with open(str(target), "w", encoding="utf-8", errors="replace", newline="") as fh:
                    fh.write(str(content))
                saved.append(str(target))
            except Exception as exc:
                errors.append(f"{filename}: {exc}")

        if errors:
            raise RuntimeError("; ".join(errors[:5]))

        self._send_json({
            "ok": True,
            "output_dir": str(base),
            "run_id": run_id,
            "n_saved": len(saved),
            "saved_paths": saved,
        })

    def _handle_ai_qc(self) -> None:
        payload = self._read_json()
        api_key = payload.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        model = payload.get("model") or "gpt-5.5"
        reasoning_effort = (payload.get("reasoning_effort") or "medium").strip().lower()
        sample_matrix = (payload.get("sample_matrix") or "dry_sediment_bulk").strip()
        enable_critic = bool(payload.get("enable_critic", True))
        items = payload.get("items") or []
        timeout = float(payload.get("timeout") or 120.0)
        try:
            max_candidates = int(payload.get("max_candidates") or 15)
        except Exception:
            max_candidates = 15
        max_candidates = max(1, min(50, max_candidates))
        if not isinstance(items, list):
            raise ValueError("items must be a list")
        data = openai_ai_qc(api_key=api_key, model=model, items=items, timeout=timeout, max_candidates=max_candidates, reasoning_effort=reasoning_effort, sample_matrix=sample_matrix, enable_critic=enable_critic)
        decisions = data.get("decisions") if isinstance(data, dict) else None
        self._send_json({
            "ok": True,
            "decisions": decisions or [],
            "raw": data,
            "max_candidates": max_candidates,
            "sample_matrix": sample_matrix,
            "enable_critic": enable_critic,
        })

    def _handle_parse(self) -> None:
        payload = self._read_json()
        text = payload.get("srcreslt_text") or payload.get("text") or ""
        srcreslt_path = payload.get("srcreslt_path") or ""
        if srcreslt_path:
            hits = parse_srcreslt_file(Path(clean_path_text(srcreslt_path)))
        elif text:
            hits = parse_srcreslt_text(text)
        else:
            raise ValueError("Provide srcreslt_text or srcreslt_path")
        self._send_json({"ok": True, "n_hits": len(hits), "groups": hits_to_groups(hits), "csv": hits_to_csv_string(hits)})

    def _handle_launch(self) -> None:
        assert STATE is not None
        payload = self._read_json()
        nistms = STATE.resolve_nistms(payload.get("nistms") or None)
        instrument = bool(payload.get("instrument", True))
        pid = launch_nist_gui(nistms, instrument=instrument)
        STATE.last_search = {"launched": True, "nistms": str(nistms), "pid": pid}
        self._send_json({
            "ok": True,
            "launched": True,
            "pid": pid,
            "nistms": str(nistms),
            "message": ("NIST MS Search launched. In NIST, open Options > Library Search Options > "
                        "Automation, enable Automation, set 'Number of hits to print' > 0, and select "
                        "at least one library. Leave NIST running, then use 自動NIST検索."),
        })

    def _handle_search(self) -> None:
        assert STATE is not None
        payload = self._read_json()
        msp_text = payload.get("msp") or payload.get("msp_text") or ""
        if not msp_text.strip():
            raise ValueError("No MSP text provided")
        filename = payload.get("filename") or "pygcms_deconvolved_for_NIST.msp"
        filename = Path(str(filename)).name.replace("/", "_").replace("\\", "_")
        timeout = float(payload.get("timeout") or STATE.default_timeout)
        append_mode = payload.get("append_mode") or "OVERWRITE"
        dry_run = bool(payload.get("dry_run", False))
        par = int(payload.get("par") or 2)
        instrument = bool(payload.get("instrument", True))
        prelaunch = bool(payload.get("prelaunch", False))
        nistms = STATE.resolve_nistms(payload.get("nistms") or None)
        nist_workdir = STATE.resolve_nist_workdir(nistms, payload.get("nist_workdir") or None)

        # Stage MSP in a short ASCII-only directory.  This avoids NIST20/23
        # silently failing to produce SRCREADY.TXT when the spectrum file is
        # under a long app path, a Downloads path, or a non-system drive.
        STATE.workdir.mkdir(parents=True, exist_ok=True)
        nist_stage = default_bridge_tempdir()
        nist_stage.mkdir(parents=True, exist_ok=True)
        msp_path = nist_stage / filename
        msp_path.write_text(msp_text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n"), encoding="utf-8", errors="replace")

        if dry_run:
            STATE.last_search = {"dry_run": True, "msp_path": str(msp_path), "nistms": str(nistms), "nist_workdir": str(nist_workdir)}
            self._send_json({
                "ok": True,
                "dry_run": True,
                "msp_path": str(msp_path),
                "nistms": str(nistms),
                "nist_workdir": str(nist_workdir),
                "message": "Dry run completed. NIST was not launched.",
            })
            return

        backend = str(payload.get("backend") or "auto").lower()
        n_hits = int(payload.get("max_candidates") or payload.get("n_hits") or 15)
        n_hits = max(1, min(50, n_hits))
        hits, used_backend = search_hits(
            msp=msp_path,
            nistms=nistms,
            backend=backend,
            n_hits=n_hits,
            timeout=timeout,
            append_mode=append_mode,
            create_autoimp=STATE.create_autoimp,
            dry_run=False,
            nist_workdir=nist_workdir,
            par=par,
            instrument=instrument,
            prelaunch=prelaunch,
            poll_interval=float(payload.get("poll_interval") or 0.03),
        )
        if used_backend == "dll":
            srcreslt = msp_path.with_suffix(".dllhits")
            ready_count = len({h.query_index for h in hits})
        else:
            srcreslt = nist_workdir / "SRCRESLT.TXT"
            ready_count = read_srcready_count(ready_path(srcreslt.parent) or srcreslt.parent / "SRCREADY.TXT")

        # ---- One CSV per analysis file -------------------------------------
        # Batches of the same run append to a single CSV named after the source
        # file.  Per-batch CSV/JSON are only written when explicitly requested.
        source_name = str(payload.get("source_name") or "").strip()
        source_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_name) or msp_path.stem
        index_offset = int(payload.get("index_offset") or 0)
        keep_intermediates = bool(payload.get("keep_intermediates", False))
        reset_csv = bool(payload.get("reset_csv", False))

        results_dir = STATE.workdir / "results"
        csv_path = results_dir / f"{source_name}_NIST_hits.csv"
        if reset_csv and csv_path.exists():
            csv_path.unlink()
        append_hits_csv(hits, csv_path, index_offset=index_offset)

        json_path = None
        if keep_intermediates:
            json_path = STATE.workdir / (msp_path.stem + "_hits.json")
            json_path.write_text(json.dumps([asdict(h) for h in hits], ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            # The staged MSP is scratch; keeping 18 of them per run helps nobody.
            try:
                msp_path.unlink()
            except OSError:
                pass
        if not hits:
            # A valid NIST run can produce a fresh SRCREADY.TXT with zero printable hits
            # for a low-information or unusual deconvoluted spectrum. Earlier versions
            # treated this as HTTP 500, which stopped long batch searches at the first
            # zero-hit component. Return ok=True with an empty hit list so the browser
            # can mark this component as NIST-unidentified and continue to the end.
            preview = read_text_if_exists(srcreslt, limit=2000)
            raw_hit_lines = sum(1 for line in preview.splitlines() if line.strip().lower().startswith("hit"))
            warning = (
                "NIST returned SRCREADY/SRCRESLT but no parsable Hit lines were found; "
                "this spectrum will be left as NIST-unidentified and the batch will continue."
            )
            STATE.last_search = {
                "msp_path": str(msp_path),
                "srcreslt": str(srcreslt),
                "csv_path": str(csv_path),
                "json_path": (str(json_path) if json_path else ""),
                "n_hits": 0,
                "n_groups": 0,
                "zero_hits": True,
                "srcready_count": ready_count,
                "raw_hit_lines": raw_hit_lines,
                "nistms": str(nistms),
                "nist_workdir": str(nist_workdir),
                "warning": warning,
                "preview": preview[:500],
            }
            self._send_json({
                "ok": True,
                "n_hits": 0,
                "n_groups": 0,
                "zero_hits": True,
                "raw_hit_lines": raw_hit_lines,
                "srcready_count": ready_count,
                "groups": [],
                "csv": hits_to_csv_string([]),
                "msp_path": str(msp_path),
                "srcreslt": str(srcreslt),
                "csv_path": str(csv_path),
                "json_path": (str(json_path) if json_path else ""),
                "nistms": str(nistms),
                "nist_workdir": str(nist_workdir),
                "warning": warning,
                "preview": preview[:500],
            })
            return
        STATE.last_search = {
            "msp_path": str(msp_path),
            "srcreslt": str(srcreslt),
            "csv_path": str(csv_path),
            "json_path": (str(json_path) if json_path else ""),
            "n_hits": len(hits),
            "n_groups": len(hits_to_groups(hits)),
            "srcready_count": ready_count,
            "nistms": str(nistms),
            "nist_workdir": str(nist_workdir),
        }
        self._send_json({
            "ok": True,
            "n_hits": len(hits),
            "n_groups": len(hits_to_groups(hits)),
            "srcready_count": ready_count,
            "groups": hits_to_groups(hits),
            "csv": hits_to_csv_string(hits),
            "msp_path": str(msp_path),
            "srcreslt": str(srcreslt),
            "csv_path": str(csv_path),
            "json_path": (str(json_path) if json_path else ""),
            "nistms": str(nistms),
            "nist_workdir": str(nist_workdir),
        })


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Local HTTP bridge for PyGCMS Pipeline and licensed NIST MS Search")
    p.add_argument("--host", default="127.0.0.1", help="Host to bind. Keep 127.0.0.1 unless you know what you are doing.")
    p.add_argument("--port", type=int, default=18789, help="Local port used by the browser app")
    p.add_argument("--nistms", help="Full path to NISTMS$.EXE, e.g. C:\\NIST23\\MSSEARCH\\NISTMS$.EXE")
    p.add_argument("--nist-workdir", help="Optional NIST MS Search WorkDir32. Usually auto-detected from WIN.INI.")
    p.add_argument("--workdir", help="Directory for temporary MSP and parsed result files")
    p.add_argument("--timeout", type=float, default=240.0, help="Seconds to wait for SRCREADY/SRCRESLT")
    p.add_argument("--no-create-autoimp", action="store_true", help="Do not create AUTOIMP.MSD in the NIST MS Search directory")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    nistms = Path(clean_path_text(args.nistms)).expanduser() if args.nistms else discover_nistms()
    nist_workdir = Path(clean_path_text(args.nist_workdir)).expanduser() if args.nist_workdir else None
    bridge_workdir = Path(clean_path_text(args.workdir)).expanduser() if args.workdir else None
    global STATE
    STATE = AppState(
        nistms=nistms,
        nist_workdir=nist_workdir,
        port=args.port,
        host=args.host,
        bridge_workdir=bridge_workdir,
        create_autoimp=not args.no_create_autoimp,
        default_timeout=args.timeout,
    )
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"PyGCMS Pipeline local bridge listening on http://{args.host}:{args.port}")
    print(f"Open browser app:  http://{args.host}:{args.port}/app")
    try:
        print("NISTMS$.EXE:", STATE.resolve_nistms())
        print("NIST WorkDir:", STATE.resolve_nist_workdir(STATE.nistms))
    except Exception as e:
        print("NISTMS$.EXE not resolved yet:", e)
    print("Bridge WorkDir:", STATE.workdir)
    print("Search command: NISTMS$.EXE /INSTRUMENT /PAR=2  (default for NIST20/NIST23)")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
