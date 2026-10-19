#!/usr/bin/env python3
"""Reprocess component CSVs using the exact browser classification and QC engine.
Uses compact processing views to limit browser memory, then joins QC columns back
onto ALL original CSV columns without changing them. Inputs remain untouched.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,sys,zipfile,re
from fnmatch import fnmatch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'));csv.field_size_limit(20_000_000)
KEEP=set('No ComponentNo Component_ID Compound Candidate_name TotalIntensity PureIons RetainedIonCount RT_min NIST_MF NIST_RMF NIST_CAS CAS Formula FinalCategory Category FinalPaperClass9 PaperClass9 FinalOriginRuleID AI_Action Sample sample Run_ID Phase phase Window Pair_ID unit Composite_ID Station site Layer layer Date date Method_ID method Mass_mg mass_mg eligible_fixed IsotopeEvidenceReviewed NIST_MFGap_Top2Unique NIST_UniqueSpeciesCount'.split())

def iter_sources(paths:list[str],pattern:str):
    for value in paths:
        p=Path(value).expanduser().resolve()
        if p.is_dir():yield from iter_sources([str(x) for x in sorted(p.rglob(pattern))],pattern)
        elif p.suffix.lower()=='.zip':
            with zipfile.ZipFile(p) as z:
                for info in sorted(z.infolist(),key=lambda x:x.filename):
                    if info.is_dir() or not fnmatch(Path(info.filename).name,pattern):continue
                    if info.file_size>250_000_000:raise ValueError('CSV exceeds 250 MB safety limit: '+info.filename)
                    yield Path(info.filename).name,z.read(info)
        elif p.is_file():yield p.name,p.read_bytes()
        else:raise FileNotFoundError(p)

def compact_inputs(paths,pattern):
    files=[]
    for name,data in iter_sources(paths,pattern):
        reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
        fields=reader.fieldnames or []
        chosen=[k for k in fields if k in KEEP or re.fullmatch(r'Cand\d+_(Name|Formula|CAS|MF|Rank)',k)]
        stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=chosen,lineterminator='\n');writer.writeheader()
        for r in reader:
            if None in r:raise ValueError(name+': inconsistent column count')
            writer.writerow({k:r.get(k,'') for k in chosen})
        files.append({'name':name,'text':stream.getvalue(),'sha256':hashlib.sha256(data).hexdigest()})
    if not files:raise ValueError('No component CSVs matched the requested pattern.')
    return files

def sample_stem(name):return re.sub(r'_(results|classification|qc_audit)$','',re.sub(r'\.csv$','',name,flags=re.I),flags=re.I)

def restore_original_columns(paths,pattern,qctext,destination):
    qc=list(csv.DictReader(io.StringIO(qctext.lstrip('\ufeff'),newline='')))
    if not qc:
        destination.write_text(qctext,encoding='utf-8');return 0
    qcmap={r['QC140_RecordKey']:r for r in qc};new=[k for k in qc[0] if k.startswith('QC140_')];all_fields=[]
    for name,data in iter_sources(paths,pattern):
        fields=next(csv.reader(io.StringIO(data.decode('utf-8-sig'),newline='')),[])
        for k in fields:
            if k not in all_fields:all_fields.append(k)
    # Reprocessing an already QC-annotated CSV is rejected rather than overwriting its audit.
    collisions=set(new)&set(all_fields)
    if collisions:raise ValueError('Input already contains QC140 fields; use the original results CSV, not an audit output.')
    written=0
    with destination.open('w',encoding='utf-8-sig',newline='') as out:
        w=csv.DictWriter(out,fieldnames=all_fields+new,lineterminator='\n');w.writeheader()
        for name,data in iter_sources(paths,pattern):
            for i,r in enumerate(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))):
                sample=r.get('Sample') or r.get('sample') or r.get('Run_ID') or sample_stem(name)
                no=r.get('No') or r.get('ComponentNo') or r.get('Component_ID') or str(i+1)
                key=str(sample).strip()+'|'+str(no).strip()
                if key not in qcmap:raise ValueError('QC join missing '+key)
                row=dict(r);row.update({k:qcmap[key].get(k,'') for k in new});w.writerow(row);written+=1
    if written!=len(qc):raise ValueError('Original/QC row counts differ')
    return written

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inputs',nargs='+');p.add_argument('--out',required=True,type=Path)
    p.add_argument('--pattern',default='*_results.csv');p.add_argument('--manifest',type=Path);p.add_argument('--settings',type=Path)
    p.add_argument('--min-mf',type=float);p.add_argument('--min-ions',type=int);p.add_argument('--min-response-pct',type=float);p.add_argument('--generic',action='store_true')
    a=p.parse_args();dest=a.out.expanduser().resolve()
    if dest.exists() and any(dest.iterdir()):raise ValueError('Output directory must be empty; existing analyses are not overwritten.')
    files=compact_inputs(a.inputs,a.pattern);print('Loaded',len(files),'compact component inputs.',flush=True)
    settings=json.loads(a.settings.read_text()) if a.settings else {}
    for field,value in [('minMF',a.min_mf),('minIons',a.min_ions),('minResponsePct',a.min_response_pct)]:
        if value is not None:settings[field]=value
    if a.generic:settings['exclusionProfile']='NONE'
    manifest=list(csv.DictReader(a.manifest.open(encoding='utf-8-sig',newline=''))) if a.manifest else []
    try:from playwright.sync_api import sync_playwright
    except ImportError:raise RuntimeError('Install requirements-browser.txt and Chromium; see README_JA.md.')
    from browser_utils import launch_chromium
    with sync_playwright() as pw:
        browser=launch_chromium(pw);page=browser.new_page();page.set_content((ROOT/'software/index.html').read_text(encoding='utf-8'),wait_until='load');page.evaluate('window.__qcInputs=[]')
        for f in files:page.evaluate('f=>window.__qcInputs.push(f)',f)
        metadata=page.evaluate('''({settings,manifest})=>{window.__qcResult=PyGCMSQC140.run(window.__qcInputs,settings,manifest,row=>QC140.classifier(row));return window.__qcResult.metadata;}''',{'settings':settings,'manifest':manifest})
        metadata['installedSources']={str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [ROOT/'software/index.html',ROOT/'software/qc140.js',ROOT/'software/qc140_ui.js']}
        metadata['originalColumnsPreserved']=True;metadata['processingView']='Compact input projection; source hashes refer to original bytes. All original columns restored in audit CSV.'
        page.evaluate('window.__qcTables=PyGCMSQC140.tables(window.__qcResult)')
        dest.mkdir(parents=True,exist_ok=True)
        for name in page.evaluate('Object.keys(window.__qcTables)'):
            content=page.evaluate('name=>window.__qcTables[name]',name)
            if name=='01_component_QC_audit.csv':restore_original_columns(a.inputs,a.pattern,content,dest/name)
            elif name!='09_processing_manifest.json':(dest/name).write_text(content,encoding='utf-8',newline='')
        (dest/'10_printable_inventory.html').write_text(page.evaluate('PyGCMSQC140.htmlTable(window.__qcResult)'),encoding='utf-8')
        browser.close()
    (dest/'09_processing_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (dest/'README.txt').write_text('Original columns are preserved in 01_component_QC_audit.csv. Candidate-conditional and identity-conservative summaries are distinct; do not mix their denominators. Original inputs are unchanged. No new NIST search, external-model call or re-deconvolution was performed.\n')
    print(json.dumps({k:v for k,v in metadata.items() if k!='sources'},indent=2));print('WROTE:',dest)
if __name__=='__main__':
    try:main()
    except Exception as e:print('ERROR:',e,file=sys.stderr);raise SystemExit(2)
