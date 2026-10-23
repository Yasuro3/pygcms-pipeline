#!/usr/bin/env python3
"""Build an offline browser QC review with the unmodified PyGCMS v1.4.0 engine.

Python 3.10+ standard library only. This script embeds component-source CSVs in
the released HTML and adds a UI bootstrap. It does not run a library search or
implement/modify the scientific classification and QC algorithms.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "7d7ab77cef342cf5061eb87c412126789f152a3f"
HTML_BLOB_SHA = "bc8e30666714f396efe9b79b5755ed48f392346d"
MAX_CSV_BYTES = 150_000_000
CSV_PATTERN = "*_NIST_component_source.csv"
csv.field_size_limit(20_000_000)

NOTICE = """PyGCMS Pipeline 1.4.1 (experimental NNLS) outputs / 1.4.0 QC re-evaluation

本体 1.4.0 / 分類モデル 2.2.0 / Identification QC 1.0.0 /
Reporting model JAAP-7-v1.0.0 を使用します。正式タグの JavaScript は
無改変です。追加コードは CSV の埋込み、公式 API の呼出、表示と保存を担当します。

今回の TotalIntensity は各 scan×m/z のベースライン補正後の観測信号を各成分に重複なく配分した時間積分（近似的に counts×min）です。
旧v1.4.0の TotalIntensity とは算出方法が異なり、直接比較できません。
濃度、直線的な mg 当たり応答、質量割合として解釈しないでください。
response 閾値はv1.4.1の分配済み信号指標に適用されます。原資料の閾値での感度は未検証です。

表示する名前は NIST ライブラリ候補であり、標準物質で確定した同定ではありません。
MF は一致度指標です。MF を同定の確率として扱わないでください。
近接候補、異性体、化学式／CAS の矛盾、RT の複数帯は公式 QC の監査欄を確認します。

FA 主表示では FA の測定 run のみを読み込みます。全 GC 監査表示には blank と
補正試料も含まれるため、All_run_frequency を FA 試料の頻度に読み替えないでください。
SS は TD/PY 頻度の分母に入りません。Either は完全な 1 TD / 1 PY の組だけです。

検索対象にならなかった成分、ヒットなし、未検索の成分も入力 CSV に残ります。
MSSearch_Status と MF_NOT_RECORDED などのフラグを確認してください。
検索未実行の preview は同定結果ではありません。

01_component_QC_audit.csv は元 CSV の全列を保持し、QC140_ 列を追記します。
入力の SHA-256 と設定は 09_processing_manifest.json、および今回用の
11_PyGCMS_v141_review_provenance.json に記録します。元 CSV は変更しません。
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def sample_stem(name: str) -> str:
    stem = re.sub(r"\.csv$", "", name, flags=re.I)
    return re.sub(r"_(results|classification|qc_audit)$", "", stem, flags=re.I)


def first_value(row: dict, keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return default


def read_csv(data: bytes, name: str) -> tuple[str, list[str], list[dict]]:
    if len(data) > MAX_CSV_BYTES:
        raise ValueError(f"{name}: CSV exceeds the official browser's 150 MB limit")
    text = data.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    fields = reader.fieldnames or []
    if not fields or len(fields) != len(set(fields)):
        raise ValueError(f"{name}: empty or duplicate CSV headers")
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{name}: inconsistent CSV column count near line {reader.line_num}")
        rows.append(row)
    return text, fields, rows


def input_paths(values: list[str], pattern: str) -> list[Path]:
    result: list[Path] = []
    seen = set()
    for value in values:
        path = Path(value).expanduser().resolve()
        candidates = sorted(path.rglob(pattern)) if path.is_dir() else [path]
        for item in candidates:
            if not item.is_file():
                raise FileNotFoundError(item)
            if item.suffix.lower() != ".csv":
                raise ValueError(f"Expected a CSV file: {item}")
            if item not in seen:
                seen.add(item)
                result.append(item)
    if not result:
        raise ValueError(f"No component-source CSVs match {pattern}")
    return result


def load_inputs(values: list[str], pattern: str, selected_runs: set[str]) -> tuple[list[dict], list[dict], set[str]]:
    files: list[dict] = []
    inventory: list[dict] = []
    used_names = set()
    record_keys = set()
    loaded_samples = set()
    for path in input_paths(values, pattern):
        data = path.read_bytes()
        text, fields, rows = read_csv(data, path.name)
        if "TotalIntensity" not in fields or not {"Compound", "Candidate_name"}.intersection(fields):
            raise ValueError(f"{path.name}: expected component CSV with Compound and TotalIntensity")
        if any(field.startswith("QC140_") for field in fields):
            raise ValueError(f"{path.name}: use component-source CSV, not an already processed QC audit")
        samples = {first_value(row, ("Sample", "sample", "Run_ID"), sample_stem(path.name)) for row in rows}
        if not samples:
            samples.add(sample_stem(path.name))
        if selected_runs:
            if not samples.intersection(selected_runs):
                continue
            if not samples.issubset(selected_runs):
                raise ValueError(f"{path.name}: contains both selected and unselected runs; provide one CSV per run")
        if path.name in used_names:
            raise ValueError(f"Duplicate input filename: {path.name}")
        used_names.add(path.name)
        for i, row in enumerate(rows, 1):
            sample = first_value(row, ("Sample", "sample", "Run_ID"), sample_stem(path.name))
            no = first_value(row, ("No", "ComponentNo", "Component_ID"), str(i))
            key = sample + "|" + no
            if key in record_keys:
                raise ValueError(f"Duplicate component {key}; overlapping exports cannot be loaded twice")
            record_keys.add(key)
        status_counts = Counter(first_value(row, ("MSSearch_Status",), "NOT_RECORDED") for row in rows)
        status_by_sample = {sample: Counter() for sample in samples}
        for row in rows:
            sample = first_value(row, ("Sample", "sample", "Run_ID"), sample_stem(path.name))
            status_by_sample[sample][first_value(row, ("MSSearch_Status",), "NOT_RECORDED")] += 1
        files.append({"name": path.name, "text": text, "sha256": sha256(data)})
        inventory.append({
            "name": path.name, "sha256": sha256(data), "bytes": len(data),
            "rows": len(rows), "columns": len(fields), "samples": sorted(samples),
            "search_status_counts": dict(sorted(status_counts.items())),
            "search_status_by_sample": {sample: dict(sorted(counts.items())) for sample, counts in sorted(status_by_sample.items())},
            "rows_with_recorded_MF": sum(bool(str(row.get("NIST_MF") or "").strip()) for row in rows),
        })
        loaded_samples.update(samples)
    if not files:
        raise ValueError("No component CSVs remain after selecting runs; Sample/Run_ID must match --runs")
    missing = selected_runs - loaded_samples
    if missing:
        raise ValueError("Selected run CSVs are missing: " + ", ".join(sorted(missing)))
    return files, inventory, loaded_samples


def load_manifest(path: Path | None, selected_runs: set[str], loaded_samples: set[str]) -> tuple[list[dict], dict | None]:
    if path is None:
        return [], None
    data = path.read_bytes()
    _, _, rows = read_csv(data, path.name)
    seen = set()
    selected = []
    for row in rows:
        sample = first_value(row, ("Sample", "sample", "Run_ID"))
        if not sample:
            raise ValueError("Run manifest requires Sample on every row")
        if sample in seen:
            raise ValueError("Duplicate manifest Sample: " + sample)
        seen.add(sample)
        if not selected_runs or sample in loaded_samples:
            selected.append(row)
    return selected, {"name": path.name, "sha256": sha256(data), "rows_used": len(selected)}


def safe_json(value: object) -> str:
    # Input strings must not be able to close the HTML script element.
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    for value, replacement in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(value, replacement)
    return text


BOOTSTRAP = r'''
<!-- KOBE_QC_BOOTSTRAP_BEGIN: additional UI adapter; released engine above is unchanged. -->
<style>
body>header,#drop{display:none!important}main{max-width:1400px;padding:20px}
main>:not(#qc140panel):not(#kobeQcIntro):not(#kobeQcRuns){display:none!important}
#kobeQcIntro,#kobeQcRuns{background:white;border:1px solid #d7e0e4;border-radius:8px;padding:20px;margin:0 0 16px}
#kobeQcIntro h1{font-size:25px;color:#174d59;line-height:1.3;margin:0 0 12px}
#kobeQcIntro p{margin:8px 0;line-height:1.65}.kobe-note{padding:12px;background:#fff3d8;border-left:4px solid #bd7900}
.kobe-preview{background:#8d2525;color:white;padding:12px;font-size:15px;font-weight:700;margin:8px 0}
.kobe-buttons{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.kobe-buttons button{font-size:12px;padding:8px 12px}
#kobeQcRuns h2{font-size:18px;margin-bottom:10px}#kobeQcRuns .kobe-scroll{overflow:auto;max-height:420px}
#kobeQcRuns th,#kobeQcRuns td{font-size:12px;padding:8px;white-space:nowrap}.kobe-muted{color:#596d75}
#kobeQcError{color:#9d2020;white-space:pre-wrap;font-weight:bold}#kobeQcStatus{font-size:16px;font-weight:bold}
@media print{.kobe-buttons,#q140run{display:none}main{padding:0}#kobeQcIntro,#kobeQcRuns{border:0}}
</style>
<section id="kobeQcIntro">
 <h1 id="kobeQcTitle">PyGCMS 1.4.1：NIST ライブラリ候補の QC</h1>
 <div id="kobeQcPreview" class="kobe-preview" hidden>NIST 検索未実行の確認用プレビューです。同定結果ではありません。</div>
 <p>本体 <b>1.4.0</b> ／ 分類モデル <b>2.2.0</b> ／ QC <b>1.0.0</b> ／ Reporting <b>JAAP-7-v1.0.0</b></p>
 <p id="kobeQcScope"></p>
 <p class="kobe-note"><b>数値の読み方：</b>今回の TotalIntensity はベースライン補正後の観測イオン信号を重複なく各成分に配分した時間積分（近似的に counts×min）です。旧v1.4.0の値とは比較できません。濃度や校正済みピーク面積ではありません。QC の候補名は標準物質で確定した同定ではありません。</p>
 <p>FA 主表示には FA 試料の run だけを含めます。全 GC 監査表示の頻度には blank と補正試料も入るため、FA 試料の頻度と区別してください。SS は TD/PY 頻度の分母に入りません。Either は完全な TD/PY の組だけです。</p>
 <p id="kobeQcStatus" role="status">CSV を読み込み、正規 QC をローカルで実行します…</p>
 <p id="kobeQcSearchStatus"></p><p id="kobeQcError" role="alert"></p>
 <div class="kobe-buttons">
  <button class="btn pri" id="kobeQcZip" disabled>今回用 QC 一式を ZIP 保存（注意書き付）</button>
  <button class="btn" id="kobeQcNotice">数値・同定・頻度の注意書き</button>
  <button class="btn" id="kobeQcProvenance">入力と正規コードの記録</button>
 </div>
 <details><summary>個別ファイルを保存</summary><div id="kobeQcDownloads" class="kobe-buttons"></div></details>
 <p class="kobe-muted">この HTML に入力 CSV を埋め込んであります。開くたびに同梱された正規エンジンで再計算します。新しい NIST 検索や外部 AI への送信は行いません。下の設定を変えた場合は「Run QC &amp; recompute reports」を押してください。</p>
</section>
<section id="kobeQcRuns"><h2>測定 run ごとの入力・QC 通過件数</h2><div class="kobe-scroll"><table><thead><tr><th>Sample</th><th>Phase</th><th>入力成分</th><th>通過</th><th>除外規則</th><th>検索状態（成分数）</th></tr></thead><tbody id="kobeQcRunBody"></tbody></table></div></section>
<noscript>この QC レビューは JavaScript が有効な標準ブラウザで開いてください。</noscript>
<script id="kobe-qc-inputs" type="application/json">__KOBE_PAYLOAD__</script>
<script id="kobe-qc-bootstrap">
(function(){'use strict';
const payload=JSON.parse(document.getElementById('kobe-qc-inputs').textContent);
const el=id=>document.getElementById(id),E=window.PyGCMSQC140;
const fieldMap={minMF:'q140mf',minIons:'q140ions',minResponsePct:'q140pct',nearTieGap:'q140gap',rtBandGap:'q140rt',nearRT:'q140near',exclusionProfile:'q140profile',rtDiagnostics:'q140rtcheck'};
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let cached=null,busy=false;
function download(name,text,type){const u=URL.createObjectURL(text instanceof Blob?text:new Blob([text],{type:type||'text/plain;charset=utf-8'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),12000);}
function zip(files){const enc=new TextEncoder(),parts=[],central=[],lut=new Uint32Array(256);let offset=0;for(let i=0;i<256;i++){let c=i;for(let j=0;j<8;j++)c=c&1?0xedb88320^(c>>>1):c>>>1;lut[i]=c>>>0;}const crc=b=>{let c=0xffffffff;for(const x of b)c=lut[(c^x)&255]^(c>>>8);return(c^0xffffffff)>>>0;};for(const [name,content] of Object.entries(files)){const nb=enc.encode(name),db=enc.encode(content),ch=crc(db),h=new Uint8Array(30+nb.length),v=new DataView(h.buffer);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint32(14,ch,true);v.setUint32(18,db.length,true);v.setUint32(22,db.length,true);v.setUint16(26,nb.length,true);h.set(nb,30);parts.push(h,db);const c=new Uint8Array(46+nb.length),w=new DataView(c.buffer);w.setUint32(0,0x02014b50,true);w.setUint16(4,20,true);w.setUint16(6,20,true);w.setUint16(8,0x800,true);w.setUint32(16,ch,true);w.setUint32(20,db.length,true);w.setUint32(24,db.length,true);w.setUint16(28,nb.length,true);w.setUint32(42,offset,true);c.set(nb,46);central.push(c);offset+=h.length+db.length;}const size=central.reduce((s,a)=>s+a.length,0),end=new Uint8Array(22),v=new DataView(end.buffer);v.setUint32(0,0x06054b50,true);v.setUint16(8,central.length,true);v.setUint16(10,central.length,true);v.setUint32(12,size,true);v.setUint32(16,offset,true);return new Blob([...parts,...central,end],{type:'application/zip'});}
function provenance(){const result=window.QC140&&QC140.state.result;return Object.assign({},payload.provenance,{preview:payload.preview,notice:payload.notice,active_QC_settings:result?result.metadata.settings:null,QC_complete:!!result});}
function outputs(){if(!QC140.state.result)throw new Error('先に QC を実行してください。');if(!cached){cached=E.tables(QC140.state.result);cached['10_printable_inventory.html']=E.htmlTable(QC140.state.result);cached['11_PyGCMS_v141_review_provenance.json']=JSON.stringify(provenance(),null,2)+'\n';cached['README_PyGCMS_v141_QC.txt']=(payload.preview?'【NIST 検索未実行の確認用プレビュー】\n\n':'')+payload.notice;}return cached;}
function exportZIP(){try{download('PyGCMS_v141_QC_'+(payload.preview?'PREVIEW_':'')+payload.provenance.scope_id+'.zip',zip(outputs()));}catch(e){el('kobeQcError').textContent=e.message;}}
function updateDisplay(result){const m=result.metadata;el('kobeQcStatus').textContent=m.runCount+' run ／ '+m.inputRecords+' 入力成分 ／ '+m.qualifyingRecords+' QC 通過成分 ／ '+m.candidateKeys+' 候補ラベル';el('q140status').textContent=el('kobeQcStatus').textContent+'。確定同定を意味しません。';el('q140coverage').textContent='response は v1.4.1 の分配済み信号の時間積分（近似的に counts×min）に基づきます。濃度、校正済みピーク面積、質量組成ではありません。';el('q140warnings').textContent=m.warnings.join('\n');el('q140settings').textContent=JSON.stringify(m.settings);el('q140outputs').style.display='block';QC140.renderTable();
 const statusBySample=new Map();for(const f of payload.provenance.input_files){for(const sample of f.samples){const counts=statusBySample.get(sample)||{};for(const [k,v] of Object.entries(f.search_status_by_sample[sample]||{}))counts[k]=(counts[k]||0)+v;statusBySample.set(sample,counts);}}
 el('kobeQcRunBody').innerHTML=result.runSummary.map(r=>'<tr><td>'+esc(r.Sample)+'</td><td>'+esc(r.Phase)+'</td><td>'+r.Input_rows+'</td><td>'+r.Qualifying_rows+'</td><td>'+r.Excluded_rows+'</td><td>'+esc(Object.entries(statusBySample.get(r.Sample)||{}).map(([k,v])=>k+': '+v).join(' / '))+'</td></tr>').join('');
 const box=el('kobeQcDownloads');box.textContent='';for(const name of ['01_component_QC_audit.csv','02_reported_candidates.csv','03_run_QC_summary.csv','04_group_summary.csv','05_group_ratios.csv','06_retention_band_diagnostics.csv','07_classification_transitions.csv','08_author_review_queue.csv','09_processing_manifest.json','10_printable_inventory.html']){const b=document.createElement('button');b.className='btn';b.textContent=name;b.onclick=()=>download(name,outputs()[name],name.endsWith('.csv')?'text/csv;charset=utf-8':name.endsWith('.html')?'text/html;charset=utf-8':'application/json;charset=utf-8');box.appendChild(b);}el('kobeQcZip').disabled=false;
}
async function run(){if(busy)return;busy=true;cached=null;el('q140run').disabled=true;el('kobeQcZip').disabled=true;el('kobeQcError').textContent='';el('kobeQcDownloads').textContent='';el('kobeQcRunBody').textContent='';QC140.state.result=null;window.PyGCMS_v141QCReview.result=null;window.PyGCMS_v141QCReview.error=null;el('kobeQcStatus').textContent='正規 1.4.0 QC をローカルで再計算中…';try{await new Promise(r=>setTimeout(r,25));const live=QC140.getSettings(),settings=Object.assign({},payload.settings);for(const k of Object.keys(fieldMap))settings[k]=live[k];const result=E.run(QC140.state.files,settings,QC140.state.manifest,row=>QC140.classifier(row));QC140.state.result=result;window.PyGCMS_v141QCReview.result=result;updateDisplay(result);}catch(e){el('kobeQcError').textContent='QC ERROR: '+e.message;el('kobeQcStatus').textContent='QC は完了していません。';el('q140outputs').style.display='none';window.PyGCMS_v141QCReview.error=e.message;}finally{busy=false;el('q140run').disabled=false;}}
function start(){try{if(!E||!window.QC140||E.VERSION!=='1.4.0'||E.MODEL!=='2.2.0'||E.QC!=='1.0.0'||E.REPORT!=='JAAP-7-v1.0.0')throw new Error('Expected the exact released v1.4.0 classification/QC engine.');const main=document.querySelector('main'),panel=el('qc140panel');main.insertBefore(el('kobeQcIntro'),panel);main.appendChild(el('kobeQcRuns'));el('drop').classList.add('hide');panel.open=true;document.title=payload.title;el('kobeQcTitle').textContent=payload.title;el('kobeQcPreview').hidden=!payload.preview;el('kobeQcScope').textContent='対象：'+payload.provenance.samples.join(', ')+'（'+payload.provenance.input_files.length+' CSV）。入力の全成分を保持して再集計します。';
 const allCounts={};for(const f of payload.provenance.input_files)for(const [k,v] of Object.entries(f.search_status_counts))allCounts[k]=(allCounts[k]||0)+v;el('kobeQcSearchStatus').textContent='MSSearch_Status（成分数）：'+Object.entries(allCounts).map(([k,v])=>k+' = '+v).join(' / ');
 const settings=E.validateSettings(payload.settings);for(const [key,id] of Object.entries(fieldMap)){if(key==='rtDiagnostics')el(id).checked=!!settings[key];else el(id).value=settings[key];}QC140.state.files=payload.files;QC140.state.manifest=payload.manifest;QC140.state.result=null;el('q140manifeststatus').textContent=payload.manifest.length?payload.manifest.length+' run definitions supplied in the embedded manifest.':'各 CSV の Sample / Phase / Pair_ID / Method_ID 欄を使用します。';const importer=el('q140files');if(importer&&importer.parentElement)importer.parentElement.style.display='none';el('q140run').onclick=run;const upstreamZip=panel.querySelector('button[onclick="QC140.exportZIP()"]');if(upstreamZip){upstreamZip.onclick=exportZIP;upstreamZip.textContent='3. Export complete QC ZIP + PyGCMS_v141 notes';}el('kobeQcZip').onclick=exportZIP;el('kobeQcNotice').onclick=()=>download('README_PyGCMS_v141_QC.txt',payload.notice);el('kobeQcProvenance').onclick=()=>download('11_PyGCMS_v141_review_provenance.json',JSON.stringify(provenance(),null,2)+'\n','application/json;charset=utf-8');window.PyGCMS_v141QCReview={run,outputs,exportZIP,provenance,result:null,error:null};window.PyGCMS_v141QCReview.ready=run();}catch(e){el('kobeQcError').textContent='BOOTSTRAP ERROR: '+e.message;}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();
</script>
<!-- KOBE_QC_BOOTSTRAP_END -->
'''


def build_review(args: argparse.Namespace) -> dict:
    source = args.html.expanduser().resolve()
    base = source.read_bytes()
    if git_blob(base) != HTML_BLOB_SHA:
        raise ValueError("Official software/index.html Git blob SHA mismatch; use the formal v1.4.0 runtime")
    selected_runs = {value.strip() for value in args.runs.split(",") if value.strip()}
    files, inventory, samples = load_inputs(args.inputs, args.pattern, selected_runs)
    manifest, manifest_info = load_manifest(args.manifest, selected_runs, samples)
    settings = json.loads(args.settings.read_text(encoding="utf-8-sig")) if args.settings else {}
    if not isinstance(settings, dict):
        raise ValueError("--settings must contain a JSON object")
    expected_keys = {"minMF", "minIons", "minResponsePct", "nearTieGap", "rtBandGap", "nearRT", "rtDiagnostics", "exclusionProfile", "retentionWarningPct"}
    unknown = set(settings) - expected_keys
    if unknown:
        raise ValueError("Unknown QC settings: " + ", ".join(sorted(unknown)))
    output = args.out.expanduser().resolve()
    if output.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("--out must be an HTML filename")
    build_manifest = output.with_suffix(".build_manifest.json")
    if not args.force and (output.exists() or build_manifest.exists()):
        raise FileExistsError("Output already exists; use --force to regenerate this review")
    if output == source or output in input_paths(args.inputs, args.pattern):
        raise ValueError("Output cannot overwrite the official HTML or a source CSV")
    created = datetime.now(timezone.utc).isoformat()
    scripts = re.findall(rb"<script\b[^>]*>([\s\S]*?)</script\s*>", base, flags=re.I)
    provenance = {
        "generator": "PyGCMS_v141 offline QC review adapter; separate from the upstream release",
        "generator_sha256": sha256(Path(__file__).read_bytes()),
        "created_utc": created,
        "upstream": {"repository": "https://github.com/Yasuro3/pygcms-pipeline", "tag": "v1.4.0", "commit": COMMIT,
                     "html_git_blob_sha": git_blob(base), "html_sha256": sha256(base),
                     "embedded_upstream_script_sha256": [sha256(script) for script in scripts]},
        "scope_id": "selected_runs" if selected_runs else "all_loaded_runs",
        "samples": sorted(samples), "input_files": inventory, "manifest_input": manifest_info,
        "original_input_columns_preserved": True, "requested_QC_settings": settings,
        "execution": "Browser calls the unmodified PyGCMSQC140.run(files, settings, manifest, row=>QC140.classifier(row)). No NIST search or external-model call is made by this adapter.",
        "response_interpretation": "v1.4.1 TotalIntensity is the time integral of baseline-corrected observed ion signal jointly allocated among components without double counting (approximately counts x minutes). It is uncalibrated and is not concentration, calibrated peak area, linear response per mg, or mass composition; it is not directly comparable with legacy v1.4.0 TotalIntensity.",
    }
    payload = {"title": args.title, "preview": bool(args.preview), "files": files, "manifest": manifest,
               "settings": settings, "provenance": provenance, "notice": NOTICE}
    addition = BOOTSTRAP.replace("__KOBE_PAYLOAD__", safe_json(payload)).encode("utf-8")
    offset = base.lower().rfind(b"</body>")
    if offset < 0:
        raise ValueError("Expected the official HTML closing body tag")
    generated = base[:offset] + addition + base[offset:]
    # Removing the single addition must recover the official HTML byte for byte.
    assert generated[:offset] + generated[offset + len(addition):] == base
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(generated)
    temporary.replace(output)
    report = {
        "output": output.name, "created_utc": created, "preview": bool(args.preview),
        "html_sha256": sha256(generated), "html_bytes": len(generated),
        "input_CSV_count": len(files), "input_records": sum(item["rows"] for item in inventory),
        "upstream_HTML_unchanged_after_removing_single_bootstrap": True,
        "bootstrap_insert_offset_bytes": offset, "bootstrap_bytes": len(addition),
        "bootstrap_sha256": sha256(addition), "browser_QC_executed_by_generator": False,
        "browser_QC_note": "Open the generated HTML to run the official QC. Building HTML alone is not completion of QC or NIST identification.",
        "provenance": provenance,
    }
    build_manifest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.open:
        webbrowser.open(output.as_uri())
    return report


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="+", help="component CSV files or a directory")
    p.add_argument("--out", required=True, type=Path, help="self-contained output HTML")
    p.add_argument("--pattern", default=CSV_PATTERN, help="CSV glob when reading directories")
    p.add_argument("--html", type=Path, default=ROOT / "runtime/software/index.html", help="exact released HTML")
    p.add_argument("--manifest", type=Path, help="optional explicit QC run manifest CSV")
    p.add_argument("--settings", type=Path, help="optional official QC settings JSON")
    p.add_argument("--runs", default="", help="comma-separated Sample/Run_ID values; selects whole per-run CSVs")
    p.add_argument("--title", default="PyGCMS 1.4.1：NIST ライブラリ候補の QC（PyGCMS 1.4.0）")
    p.add_argument("--preview", action="store_true", help="visibly label an unsearched preview")
    p.add_argument("--force", action="store_true", help="regenerate existing review HTML and build manifest")
    p.add_argument("--open", action="store_true", help="open the generated HTML in the default browser")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = build_review(args)
    except (OSError, ValueError, csv.Error) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2
    print(json.dumps({key: report[key] for key in ("output", "html_bytes", "input_CSV_count", "input_records", "preview", "html_sha256")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
