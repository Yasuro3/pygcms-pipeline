#!/usr/bin/env python3
"""Batch orchestration of the unmodified PyGCMS Pipeline v1.4.0 file bridge.

Python standard library only. The bridge/NIST search remains sequential. Input
spectra and original component CSVs are immutable. Search responses are the
checkpoint source of truth; candidate exports can always be rebuilt from them.
This wrapper does not implement a new spectral search or confirm identities.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
WRAPPER_VERSION = "1.4.1-GlobalNNLS-experimental"
DEFAULTS = {
    "nistms_path": "", "nist_workdir": "", "port": 18789,
    "batch_size": 25, "candidate_count": 15, "poll_interval": 0.03,
    "nist_version": "", "libraries": "", "search_mode": "",
    "search_constraints": "", "ri_settings": "", "nist_preprocessing": "",
    "automation_confirmed": False, "number_of_hits_to_print": 15,
    "operator_notes": "",
}
IDENTITY_FIELDS = set("Compound Formula MW CosineScore NIST_MF NIST_RMF NIST_Prob NIST_Rank NIST_CAS NIST_Lib NIST_ID NIST_RI NIST_SearchMode Category IDConfidenceLevel IDConfidenceTier IDConfidenceReason CatEvidence PaperClass9 DetailedClass SedimentOrigin SedimentHit PaperDetection_pct PaperEvidence Source NIST_candidates_Selected NIST_candidates_15 C_count H_count N_count O_count S_count C_wt% H_wt% N_wt% O_wt% S_wt% Reason NIST_UniqueSpeciesCount NIST_MFGap_Top2Unique NIST_NearTie".split())
HIT_COLUMNS = ["QueryIndex", "QueryName", "Header", "Rank", "Name", "Formula", "MF", "RMF", "Prob", "CAS", "MW", "Lib", "Id", "RI"]
HIT_MAP = dict(zip(HIT_COLUMNS[3:], ["rank", "name", "formula", "mf", "rmf", "prob", "cas", "mw", "lib", "id", "ri"]))


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(dict.fromkeys(k for row in rows for k in row))
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def load_settings():
    p = ROOT / "settings.json"
    value = dict(DEFAULTS)
    if p.exists():
        value.update(json.loads(p.read_text(encoding="utf-8-sig")))
    return value


def validate_settings(s, require_configured=True):
    for key, lo, hi in [("port", 1024, 65535), ("batch_size", 1, 200), ("candidate_count", 1, 50)]:
        if not isinstance(s[key], int) or isinstance(s[key], bool) or not lo <= s[key] <= hi:
            raise ValueError(f"settings.json: {key} must be an integer in {lo}..{hi}")
    if not 0.005 <= float(s["poll_interval"]) <= 1:
        raise ValueError("poll_interval must be in 0.005..1 second")
    if require_configured:
        if not s.get("automation_confirmed") or not s.get("nist_version") or not s.get("libraries"):
            raise ValueError("Run 00_SETUP_AND_CHECK.cmd first (NIST version, libraries and Automation settings).")
        if int(s.get("number_of_hits_to_print", 0)) < s["candidate_count"]:
            raise ValueError("NIST Number of hits to print must be at least candidate_count. Run setup again.")


def request_bytes(base, endpoint, payload=None, timeout=10):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + endpoint, data=data, headers={"Content-Type": "application/json"})
    # Localhost must not be routed through a user's HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            detail = json.loads(body.decode("utf-8")).get("error", body[:500].decode("utf-8", "replace"))
        except Exception:
            detail = body[:500].decode("utf-8", "replace")
        raise RuntimeError(f"Bridge HTTP {e.code}: {detail}") from e
    return body


def request_json(base, endpoint, payload=None, timeout=10):
    result = json.loads(request_bytes(base, endpoint, payload, timeout).decode("utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError("Bridge returned a non-object response")
    return result


def check_health(h):
    if not h.get("ok") or h.get("service") != "PyGCMS Pipeline" or h.get("version") != "1.4.0":
        raise ValueError("Port is occupied by a different service/version. No process was stopped. Change settings.json port or close the other service yourself.")
    if not h.get("nistms_exists"):
        raise ValueError("NISTMS$.EXE was not found. Run 00_SETUP_AND_CHECK.cmd.")


def verify_runtime():
    """Verify the shipped, unmodified upstream files before importing/starting them."""
    runtime = (ROOT / "runtime").resolve()
    manifest_bytes = (runtime / "UPSTREAM_MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get("tag") != "v1.4.0" or manifest.get("commit") != "7d7ab77cef342cf5061eb87c412126789f152a3f":
        raise ValueError("The bundled runtime does not identify the released v1.4.0 source.")
    seen = set()
    for item in manifest["files"]:
        p = (runtime / item["path"]).resolve()
        if item["path"] in seen or not p.is_relative_to(runtime):
            raise ValueError("Invalid runtime manifest path: " + item["path"])
        seen.add(item["path"])
        raw = p.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        if len(raw) != item["bytes"] or digest(raw) != item["sha256"] or blob != item["github_blob_sha"]:
            raise ValueError("Bundled upstream runtime file changed: " + item["path"])
    required = {"scripts/nist_mssearch_bridge_server.py", "scripts/nist_mssearch_bridge.py",
                "scripts/nist_dll_backend.py", "software/index.html", "software/qc140.js", "software/qc140_ui.js"}
    if not required.issubset(seen):
        raise ValueError("The bundled runtime manifest is incomplete.")
    app_sha = digest((runtime / "software" / "index.html").read_bytes())
    if app_sha != "c346ea1e089bc47f5af1b9220e7bf744be61668c0b26c24f045622833d4aa673":
        raise ValueError("The bundled application differs from released v1.4.0.")
    return {"manifest_sha256": digest(manifest_bytes), "app_sha256": app_sha,
            "files_verified": len(seen), "commit": manifest["commit"]}


def verify_bridge(base, h, s, runtime):
    check_health(h)
    for setting, reported, label in [("nistms_path", "nistms", "NIST executable"),
                                      ("nist_workdir", "nist_workdir", "NIST work directory")]:
        wanted = str(s.get(setting) or "").strip().strip('"')
        if wanted:
            def normalized(value):
                value = os.path.expandvars(os.path.expanduser(str(value).strip().strip('"')))
                return os.path.normcase(os.path.abspath(value))
            if normalized(wanted) != normalized(h.get(reported) or ""):
                raise ValueError("Existing bridge uses a different " + label + ". Choose another port or restart your bridge with the configured path.")
    app_sha = digest(request_bytes(base, "/app", timeout=10))
    if app_sha != runtime["app_sha256"]:
        raise ValueError("Bridge /app differs from the bundled released v1.4.0 application. No search was submitted.")
    return dict(h, verified_app_sha256=app_sha, bundled_runtime_manifest_sha256=runtime["manifest_sha256"])


def ensure_bridge(s):
    runtime = verify_runtime()
    base = "http://127.0.0.1:" + str(s["port"])
    try:
        h = request_json(base, "/health", timeout=3)
    except urllib.error.URLError as e:
        # A timed-out/hung listener is not an absent service.
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(("127.0.0.1", s["port"])) == 0:
                raise RuntimeError("A listener is present but its health cannot be read. No process was stopped.") from e
        h = None
    if h is not None:
        return base, verify_bridge(base, h, s, runtime)
    server = ROOT / "runtime" / "scripts" / "nist_mssearch_bridge_server.py"
    if not server.exists():
        raise FileNotFoundError("runtime is incomplete. Extract the entire ZIP before running.")
    logdir = ROOT / "bridge_work"
    logdir.mkdir(exist_ok=True)
    cmd = [sys.executable, "-u", str(server), "--host", "127.0.0.1", "--port", str(s["port"]), "--workdir", str(logdir)]
    if s.get("nistms_path"):
        cmd += ["--nistms", str(s["nistms_path"])]
    if s.get("nist_workdir"):
        cmd += ["--nist-workdir", str(s["nist_workdir"])]
    with (logdir / "bridge_server.log").open("ab") as log:
        proc = subprocess.Popen(cmd, cwd=str(ROOT / "runtime"), stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    atomic_json(logdir / "owned_bridge_process.json", {"pid": proc.pid, "started_utc": now(), "command": cmd})
    for _ in range(60):
        if proc.poll() is not None:
            raise RuntimeError("Bridge stopped during startup. See bridge_work/bridge_server.log.")
        try:
            h = request_json(base, "/health", timeout=1)
            return base, verify_bridge(base, h, s, runtime)
        except urllib.error.URLError:
            time.sleep(0.25)
    raise RuntimeError("Bridge startup timed out. See bridge_work/bridge_server.log.")


def configure():
    verify_runtime()
    with SingleRunLock(global_lock_path()):
        return configure_locked()


def configure_locked():
    s = load_settings()
    if os.name != "nt":
        raise RuntimeError("Setup and licensed NIST search must run on Windows.")
    sys.path.insert(0, str(ROOT / "runtime" / "scripts"))
    from nist_mssearch_bridge import discover_nistms
    discovered = s.get("nistms_path") or str(discover_nistms() or "")
    print("\nPyGCMS Pipeline v1.4.0 / 神戸大学 全測定 一括検索設定")
    print("NISTMS$.EXE のフルパスを入力してください。候補が正しければEnter。")
    value = input(f"NISTMS$.EXE [{discovered}]: ").strip().strip('"') or discovered
    exe = Path(os.path.expandvars(value))
    if not exe.is_file() or exe.name.lower() != "nistms$.exe":
        raise ValueError("NISTMS$.EXE が見つかりません。ファイルのフルパスを指定してください。")
    s["nistms_path"] = str(exe.resolve())
    base, health = ensure_bridge(s)
    request_json(base, "/launch", {"nistms": s["nistms_path"], "instrument": True}, timeout=30)
    print("\nNISTで Options > Library Search Options > Automation を開きます。")
    print("Automationを有効にし、Number of hits to printを15以上に設定。検索するライブラリも選択してください。")
    print("下記は実際のGUI設定の記録です。ライブラリや検索モードをこのプログラムが変更することはありません。")
    prompts = [
        ("nist_version", "NIST MS Searchのバージョン（例 NIST 23 / MS Search 2.4）", True),
        ("libraries", "選択済みライブラリ名・版（実際の設定を記入）", True),
        ("search_mode", "検索モード（Identity/Similarity等、実際の設定）", True),
        ("search_constraints", "分子量・元素・その他の検索制限（なければ none）", False),
        ("ri_settings", "RI条件（未使用なら not used）", False),
        ("nist_preprocessing", "NIST側の前処理・除外イオン等（なければ none）", False),
    ]
    for key, prompt, required in prompts:
        old = s.get(key, "")
        value = input(f"{prompt} [{old}]: ").strip() or old
        while required and not value:
            value = input("設定記録のため入力してください: ").strip()
        s[key] = value or "not recorded"
    n = input(f"Number of hits to print [{s['number_of_hits_to_print']}]: ").strip()
    if n:
        s["number_of_hits_to_print"] = int(n)
    print("NIST側のAutomation、候補数、ライブラリ選択を確認後、YESと入力してください。")
    s["automation_confirmed"] = input("確認 / confirmed: ").strip().upper() == "YES"
    s["configured_utc"] = now()
    validate_settings(s)
    atomic_json(ROOT / "settings.json", s)
    (ROOT / "nistms_path.txt").write_text(s["nistms_path"] + "\n", encoding="utf-8")
    print("\n設定保存・v1.4.1の検索入力を使うためのv1.4.0 NISTブリッジ接続準備完了。01_RUN_ALL_MSSearch.cmdで全GC測定を検索できます。")


def load_index():
    path = ROOT / "inputs" / "query_index.json"
    raw = path.read_bytes()
    x = json.loads(raw)
    if x.get("software_version") != "1.4.1":
        raise ValueError("Expected PyGCMS Pipeline v1.4.1 input; do not reuse previous NIST output")
    names = [q["query_name"] for q in x["queries"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate query identities in input")
    ids = [(q["run_id"], q["component_index"]) for q in x["queries"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate run/component identities in input")
    run_ids = [r["run_id"] for r in x["runs"]]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("Duplicate runs in input")
    for q in x["queries"]:
        lines = q["msp_text"].splitlines()
        peak_count = [int(v.split(":", 1)[1]) for v in lines if v.startswith("Num Peaks:")]
        match = re.fullmatch(r"Q\d{2,}_PGCMS_(\d+)_RT_\d+\.\d{3}_SCAN_\d+", q["query_name"])
        if (q["run_id"] not in run_ids or q["query_name"] != q["run_id"] + "_" + q["original_name"]
                or not match or int(match[1]) != q["component_index"]
                or q["retained_ion_count"] < 3 or peak_count != [q["retained_ion_count"]]
                or not lines or lines[0] != "Name: " + q["query_name"]):
            raise ValueError("Input spectrum eligibility/identity mismatch: " + q["query_name"])
    for run in x["runs"]:
        for pkey, hkey in [("original_msp_path", "original_msp_sha256"), ("unique_msp_path", "unique_msp_sha256"),
                           ("component_source_csv_path", "official_component_source_csv_sha256")]:
            p = (ROOT / run[pkey]).resolve()
            if not p.is_relative_to(ROOT.resolve()) or digest(p.read_bytes()) != run[hkey]:
                raise ValueError("Input file changed or escaped package: " + run[pkey])
        expected = "\r\n".join(q["msp_text"] for q in x["queries"] if q["run_id"] == run["run_id"]).encode("ascii")
        if expected != (ROOT / run["unique_msp_path"]).read_bytes():
            raise ValueError("Query-index spectrum bytes differ from the verified per-run MSP: " + run["run_id"])
    return x, digest(raw)


def map_response(queries, data):
    """Names are mandatory; request-local QueryIndex is never a global key."""
    if data.get("ok") is not True:
        raise ValueError(str(data.get("error") or "NIST request did not succeed"))
    known = {q["query_name"]: q for q in queries}
    found = {}
    total_hits = 0
    groups = data.get("groups", [])
    if groups is None:
        groups = []
    if not isinstance(groups, list):
        raise ValueError("Invalid bridge groups")
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Invalid bridge result group")
        header = str(group.get("query_name") or "") + " " + str(group.get("header") or "")
        matches = set(re.findall(r"(?<![A-Za-z0-9_])Q\d{2,}_PGCMS_\d+_RT_[\d.]+_SCAN_\d+(?![A-Za-z0-9_.])", header))
        if len(matches) != 1 or not matches.issubset(known):
            raise ValueError("Returned spectrum name does not match this request; results preserved for review: " + header[:250])
        name = next(iter(matches))
        if name in found:
            raise ValueError("Duplicate result group for " + name)
        hits = group.get("hits", [])
        if hits is None:
            hits = []
        if not isinstance(hits, list) or any(not isinstance(h, dict) or not h.get("name") for h in hits):
            raise ValueError("Malformed NIST candidate list for " + name)
        # v1.4.0 preserves printed candidate order and ranks; do not re-rank by MF.
        found[name] = hits
        total_hits += len(hits)
    if "n_hits" in data and int(data["n_hits"]) != total_hits:
        raise ValueError("Bridge candidate count and returned groups disagree")
    if "n_groups" in data and int(data["n_groups"]) != len(groups):
        raise ValueError("Bridge group count and returned groups disagree")
    if data.get("zero_hits") and total_hits:
        raise ValueError("Bridge zero-hit flag conflicts with returned candidates")
    if not groups and not data.get("zero_hits") and int(data.get("n_hits", -1)) != 0:
        raise ValueError("Missing result groups without an explicit zero-hit response")
    return {
        q["query_name"]: {
            "status": "hits_returned" if found.get(q["query_name"]) else "no_parsed_hits",
            "hits": found.get(q["query_name"], []),
            "warning": str(data.get("warning") or "") if not found.get(q["query_name"]) else "",
            "srcready_count": data.get("srcready_count"),
            "zero_hit_interpretation": "No candidate parsed in a successful bridge response; not proof of chemical absence.",
        } for q in queries
    }


def batches(queries, size):
    # Preserve run boundaries so original v1.4.0 imports remain easy to inspect.
    result = []
    for q in queries:
        if not result or len(result[-1]) >= size or result[-1][-1]["run_id"] != q["run_id"]:
            result.append([])
        result[-1].append(q)
    return result


def replay(out, selected):
    lookup = {q["query_name"]: q for q in selected}
    state = {}
    for path in sorted((out / "responses").glob("*.json")):
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope.get("validated") is not True:
            continue
        names = envelope["query_names"]
        if not isinstance(names, list) or not names or len(names) != len(set(names)):
            raise ValueError("Checkpoint has invalid or duplicate query identities")
        if not set(names).issubset(lookup):
            raise ValueError("Checkpoint contains queries outside this job")
        mapped = map_response([lookup[n] for n in names], envelope["response"])
        if set(mapped).intersection(state):
            raise ValueError("Duplicate successful query in checkpoints")
        state.update(mapped)
    return state


def candidate_export(index, selected, state, out, count):
    selected_runs = {q["run_id"] for q in selected}
    query_by_id = {(q["run_id"], q["component_index"]): q for q in selected}
    all_rows, long_rows, status_rows = [], [], []
    metadata_path = ROOT / "inputs" / "run_metadata.json"
    metadata = {r["run_id"]: r for r in json.loads(metadata_path.read_text(encoding="utf-8"))} if metadata_path.exists() else {}
    for run in index["runs"]:
        if run["run_id"] not in selected_runs:
            continue
        run_meta = metadata.get(run["run_id"], {})
        source = ROOT / run["component_source_csv_path"]
        with source.open(encoding="utf-8-sig", newline="") as f:
            original_rows = list(csv.DictReader(f))
        run_rows, import_rows = [], []
        for original in original_rows:
            no = int(original["No"])
            q = query_by_id.get((run["run_id"], no))
            result = state.get(q["query_name"], {}) if q else {}
            hits = result.get("hits", [])
            kept = hits[:count]
            status = result.get("status", "pending" if q else "not_eligible_min_3_ions")
            row = dict(original)
            # Clear earlier local heuristics and classification/AI assertions. Their
            # unmodified originals remain in inputs/per_run_component_source/.
            for key in row:
                if key in IDENTITY_FIELDS or key.startswith(("Cand", "Final", "AI_", "Literature")):
                    row[key] = ""
            row.update({"Run_ID": run["run_id"], "Sample": run["run_id"], "Sample_Label": run["sample_label"],
                        "Phase": run["phase"], "Method_ID": run_meta.get("method_name", ""),
                        "Pair_ID": run.get("sample_id", "") if run["phase"] in ["TD", "PY"] else "",
                        "Mass_mg": run_meta.get("mass_mg") if run_meta.get("mass_mg") is not None else "",
                        "Source_File": run["source_file"], "Query_Name": q["query_name"] if q else "",
                        "MSSearch_Status": status, "NIST_CandidateCount": len(kept), "NIST_PrintedCandidateCount": len(hits),
                        "NIST_SearchMode": "file bridge / recorded NIST GUI settings", "Candidate_Selection": "unreviewed first printed candidate" if kept else "",
                        "Intensity_Use": "Shared-cell allocated EI response integral (counts x minutes); not calibrated concentration or independent peak area",
                        "Identification_Status": "candidate annotation; review required" if kept else "unidentified",
                        "MSSearch_Notes": result.get("warning", "")})
            if kept:
                first = kept[0]
                row.update({"Compound": first.get("name", ""), "Formula": first.get("formula", ""), "MW": first.get("mw", ""),
                            "NIST_MF": first.get("mf", ""), "NIST_RMF": first.get("rmf", ""), "NIST_Prob": first.get("prob", ""),
                            "NIST_Rank": first.get("rank", ""), "NIST_CAS": first.get("cas", ""), "NIST_Lib": first.get("lib", ""),
                            "NIST_ID": first.get("id", ""), "NIST_RI": first.get("ri", ""), "Source": "nist",
                            "Reason": "Licensed NIST MS Search candidate; printed order preserved; no external AI selection or standard confirmation"})
            for rank, hit in enumerate(kept, 1):
                prefix = f"Cand{rank:02d}_"
                for label, key in {"Name": "name", "Formula": "formula", "MW": "mw", "MF": "mf", "RMF": "rmf", "Prob": "prob", "Rank": "rank", "CAS": "cas", "Lib": "lib", "RI": "ri", "ID": "id"}.items():
                    row[prefix + label] = hit.get(key, "")
            for hit in hits:
                imported = {"QueryIndex": no, "QueryName": q["original_name"], "Header": q["original_name"]}
                imported.update({col: hit.get(key, "") for col, key in HIT_MAP.items()})
                import_rows.append(imported)
                longrow = {"Run_ID": run["run_id"], "Sample_Label": run["sample_label"], "Phase": run["phase"],
                           "Component_No": no, "RT_min": original["RT_min"], "Query_Name": q["query_name"], "Source_File": run["source_file"]}
                longrow.update(imported)
                long_rows.append(longrow)
            run_rows.append(row)
            status_rows.append({"Run_ID": run["run_id"], "Component_No": no, "Query_Name": q["query_name"] if q else "",
                                "RT_min": original["RT_min"], "MSSearch_Status": status, "Printed_Candidates": len(hits),
                                "Retained_Candidates": len(kept), "Identity_Confirmed": "no"})
        all_rows.extend(run_rows)
        write_csv(out / "component_source" / (run["run_id"] + "_NIST_component_source.csv"), run_rows)
        write_csv(out / "for_v140_import" / (run["run_id"] + "_NIST_hits.csv"), import_rows, HIT_COLUMNS)
    write_csv(out / "all_components_NIST_candidates.csv", all_rows)
    write_csv(out / "all_NIST_hits_long.csv", long_rows, fields=None if long_rows else ["Run_ID", "Query_Name"] + HIT_COLUMNS)
    write_csv(out / "component_search_status.csv", status_rows)
    summary = {"updated_utc": now(), "queries_planned": len(selected), "queries_completed": len(state),
               "queries_pending": len(selected) - len(state), "queries_with_hits": sum(bool(s.get("hits")) for s in state.values()),
               "queries_without_parsed_hits": sum(not s.get("hits") for s in state.values()),
               "all_component_rows_in_selected_runs": len(all_rows), "all_printed_candidates": len(long_rows),
               "candidate_count_for_wide_csv": count, "confirmed_compound_identities": 0,
               "note": "Completion means successful NIST bridge return, not confirmed molecular identity. TotalIntensity uses experimental globally allocated EI ion-response integral, not the native v1.4.0 squared-like response; not a calibrated peak area."}
    atomic_json(out / "progress.json", summary)
    return summary


def global_lock_path():
    # Share the lock across extracted packages, scopes and configured ports.
    # Other programs/manual NIST operations must still be kept idle by the user.
    return Path(tempfile.gettempdir()) / "PyGCMS_NIST_batch.lock"


class SingleRunLock:
    """OS releases lock after crash; avoid a stale-file/manual-unlock workflow."""
    def __init__(self, path):
        self.path = path
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self.file.close()
            raise RuntimeError("Another batch runner is active. NIST search must remain sequential.") from e
        return self

    def __exit__(self, *args):
        self.file.close()


def build_review(out):
    script = ROOT / "scripts" / "build_qc_review.py"
    if not script.exists():
        return
    input_dir = out / "component_source"
    progress_path = out / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8")) if progress_path.exists() else {}
    preview_args = ["--preview"] if not progress.get("queries_completed", 0) else []
    index = json.loads((ROOT / "inputs" / "query_index.json").read_text(encoding="utf-8"))
    fa_ids = [r["run_id"] for r in index["runs"] if r.get("is_FA")]
    fa_ids = [r for r in fa_ids if (input_dir / (r + "_NIST_component_source.csv")).exists()]
    jobs = []
    if fa_ids:
        jobs.append(("OPEN_QC_REVIEW.html", ["--runs", ",".join(fa_ids), "--title", "v1.4.1 Global NNLS / v1.4.0 identification QC"]))
    if out.name == "all":
        jobs.append(("OPEN_QC_REVIEW_all_GC.html", ["--title", "v1.4.1 Global NNLS all GC / v1.4.0 QC audit"]))
    for filename, options in jobs:
        cmd = [sys.executable, str(script), str(input_dir), "--out", str(out / filename), "--force"] + options + preview_args
        completed = subprocess.run(cmd, cwd=str(ROOT))
        if completed.returncode:
            print("Candidate CSVs are saved. Browser QC review generation failed; see the message above.")


def run_job(args):
    s = load_settings()
    validate_settings(s, require_configured=not (args.validate_only or args.export_only))
    runtime = verify_runtime()
    index, index_hash = load_index()
    selected = [q for q in index["queries"] if args.scope == "all" or q.get("is_FA") or q.get("fa_only_search_sequence") is not None]
    if args.scope == "fa":
        fa_runs = {r["run_id"] for r in index["runs"] if r.get("is_FA")}
        selected = [q for q in index["queries"] if q["run_id"] in fa_runs]
    if not selected:
        raise ValueError("No eligible spectra found")
    print(f"Input verified: {len(index['runs'])} GC runs / {len(index['queries'])} eligible spectra. Scope={args.scope}: {len(selected)} spectra.")
    if args.validate_only:
        print("PASS: released v1.4.0 bridge/QC hashes, v1.4.1 query metadata, immutable MSP bytes, unique names and minimum 3 ions. No NIST search was performed.")
        return 0
    out = ROOT / "results" / args.scope
    out.mkdir(parents=True, exist_ok=True)
    signature_settings = {k: v for k, v in s.items() if k not in ["operator_notes", "configured_utc", "batch_size", "port"]}
    manifest = {"schema": "PyGCMS-v141-GLOBAL-SHARED-NNLS-NIST-batch", "wrapper_version": WRAPPER_VERSION,
                "software_version": "1.4.1", "scope": args.scope, "input_index_sha256": index_hash,
                "runtime_verification": runtime,
                "settings": s, "search_backend": "file", "query_names": [q["query_name"] for q in selected],
                "job_signature": digest({"input": index_hash, "runtime": runtime["manifest_sha256"], "scope": args.scope, "settings": signature_settings})}
    with SingleRunLock(global_lock_path()):
        manifest_path = out / "job_manifest.json"
        if manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding="utf-8"))
            if previous["job_signature"] != manifest["job_signature"]:
                raise ValueError("Input or search settings differ from this checkpoint. Preserve/rename the existing results folder before starting a separate search.")
        else:
            manifest["created_utc"] = now()
            atomic_json(manifest_path, manifest)
        state = replay(out, selected)
        summary = candidate_export(index, selected, state, out, s["candidate_count"])
        if args.export_only:
            build_review(out)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        inflight_path = out / "inflight_request.json"
        if inflight_path.exists():
            inflight = json.loads(inflight_path.read_text(encoding="utf-8"))
            if set(inflight["query_names"]).issubset(state):
                inflight_path.unlink()
            elif not args.resume_after_check:
                raise RuntimeError("An interrupted request may still be active in NIST. Completed results are preserved. Confirm NIST is idle, then use 03_RESUME_AFTER_NIST_IDLE.cmd. Do not start another search while NIST is busy.")
            else:
                archive = out / "interrupted_requests"
                archive.mkdir(exist_ok=True)
                inflight_path.replace(archive / (str(time.time_ns()) + ".json"))
        todo = [q for q in selected if q["query_name"] not in state]
        if not todo:
            build_review(out)
            print("All selected spectra already completed. Exports rebuilt; no spectra resubmitted.")
            return 0
        if os.name != "nt":
            raise RuntimeError("Licensed NIST MS Search must run on Windows. --validate-only is available on any platform.")
        base, health = ensure_bridge(s)
        atomic_json(out / ("bridge_health_" + str(time.time_ns()) + ".json"), health)
        print("NIST GUI settings will be used (backend=file). Keep Automation enabled; do not operate another NIST search during this batch.")
        print(f"Resume checkpoint: {len(state)}/{len(selected)} complete; {len(todo)} remain.")
        chunks = batches(todo, s["batch_size"])
        try:
            for ci, chunk in enumerate(chunks, 1):
                names = [q["query_name"] for q in chunk]
                key = chunk[0]["run_id"] + "_" + digest(names)[:16]
                server_timeout = min(600, 60 + 30 * len(chunk))
                # Bridge may retry launch once before its own timeout. Allow more
                # than twice that budget; never blindly re-POST a timed-out call.
                client_timeout = 2 * server_timeout + 120
                payload = {"msp": "\r\n".join(q["msp_text"] for q in chunk), "filename": key + ".msp",
                           "source_name": "PyGCMS141_" + key, "max_candidates": s["candidate_count"],
                           "backend": "file", "timeout": server_timeout, "append_mode": "Overwrite", "prelaunch": False,
                           "par": 2, "instrument": True, "index_offset": 0, "reset_csv": True,
                           "keep_intermediates": True, "poll_interval": s["poll_interval"]}
                if s.get("nistms_path"):
                    payload["nistms"] = s["nistms_path"]
                if s.get("nist_workdir"):
                    payload["nist_workdir"] = s["nist_workdir"]
                atomic_json(inflight_path, {"started_utc": now(), "query_names": names, "request_sha256": digest(payload), "server_timeout": server_timeout})
                print(f"[{ci}/{len(chunks)}] {chunk[0]['run_id']} / {len(chunk)} spectra / completed {len(state)}/{len(selected)}", flush=True)
                data = request_json(base, "/search", payload, timeout=client_timeout)
                envelope = {"received_utc": now(), "query_names": names, "request_sha256": digest(payload), "response": data, "validated": False}
                # Save unvalidated raw response before attempting any join.
                # A retried batch must not overwrite an earlier rejected response.
                response_path = out / "responses" / (key + "_" + str(time.time_ns()) + ".json")
                atomic_json(response_path, envelope)
                mapped = map_response(chunk, data)
                envelope["validated"] = True
                atomic_json(response_path, envelope)
                state.update(mapped)
                inflight_path.unlink()
                atomic_json(out / "progress.json", {
                    "updated_utc": now(), "queries_planned": len(selected), "queries_completed": len(state),
                    "queries_pending": len(selected) - len(state),
                    "queries_with_hits": sum(bool(v.get("hits")) for v in state.values()),
                    "queries_without_parsed_hits": sum(not v.get("hits") for v in state.values()),
                    "confirmed_compound_identities": 0,
                    "note": "Every response is saved. CSVs are rebuilt at completion, interruption or --export-only."})
        except BaseException as e:
            candidate_export(index, selected, state, out, s["candidate_count"])
            atomic_json(out / "last_interruption.json", {"time_utc": now(), "error_type": type(e).__name__, "error": str(e),
                                                        "completed_queries": len(state), "total_queries": len(selected),
                                                        "action": "Completed responses preserved. Confirm NIST is idle before resuming an interrupted request."})
            raise
        candidate_export(index, selected, state, out, s["candidate_count"])
        build_review(out)
        summary = json.loads((out / "progress.json").read_text(encoding="utf-8"))
        print("\n全検索処理が完了しました。候補の返却と構造の確定は別です。")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print("結果: " + str(out))
        review = out / "OPEN_QC_REVIEW.html"
        if review.exists():
            webbrowser.open(review.as_uri())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["all", "fa"], default="all")
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--resume-after-check", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    if args.setup:
        configure()
        return 0
    return run_job(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n中断しました。完了済み結果は保存済みです。NISTが待機状態に戻ってから再開してください。", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
