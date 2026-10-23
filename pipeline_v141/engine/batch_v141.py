#!/usr/bin/env python3
"""PyGCMS Pipeline v1.4.1: mzML -> global NNLS -> immutable MSP / audit.

Does not identify chemicals. Independent NIST search is done through the included
v1.4.0 bridge, under a versioned v1.4.1 query index. The separation model is
experimental, *not* the proprietary NIST AMDIS implementation.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, json, math, re, sys, time, zipfile
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import asdict

import numpy as np
from mzml_native import decode_mzml
from global_engine import extraction, Settings

BASE = Path(__file__).resolve().parents[1]
SRC_CSV_FIELDS = [
    'No','RT_min','Scan','TIC','RawIons','PureIons','TotalIntensity',
    'Compound','Formula','MW','NIST_MF','NIST_RMF','NIST_CAS','NIST_Rank','NIST_Prob','NIST_Lib','Source',
    'NIST_SearchEligible','NIST_SearchEligibilityReason','BasePeak_mz','Top5_mz',
    'CSVSchemaVersion','ClassificationModelVersion','Deconv_Algorithm','Deconv_AlgorithmVersion',
    'Deconv_FitL2_Local','Deconv_ApexPurity','Deconv_PeakSNR','Deconv_SeedScore','Deconv_ReviewFlag',
    'Deconv_GlobalArea','Deconv_GlobalAllocatedArea','Deconv_WholeRunUnassignedArea','Deconv_Pass',
    'Deconv_RawmzML_SHA256','Deconv_Config_SHA256']
VERSION='1.4.1'
DECONV='global-NNLS-shared-cell-allocation-v0.3.1-EXPERIMENTAL-NOT-AMDIS'


def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def dump_json(path:Path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def dump_csv(path:Path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\r\n')
        w.writeheader();w.writerows(rows)
def iso_now():return datetime.now(timezone.utc).isoformat()

def stream_inputs(path:Path):
    """Yield (archive member / relative path, raw bytes) in a stable order.

    ZIP entry names are untrusted; they are labels ONLY, never extraction paths.
    """
    if path.is_dir():
        paths=sorted((p for p in path.rglob('*') if p.is_file() and p.suffix.lower()=='.mzml'),key=lambda p:p.relative_to(path).as_posix().lower())
        for p in paths:yield p.relative_to(path).as_posix(), p.read_bytes()
    elif path.is_file() and path.suffix.lower()=='.mzml':
        yield path.name,path.read_bytes()
    elif path.is_file() and path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            entries=sorted((p for p in z.infolist() if not p.is_dir() and p.filename.lower().endswith('.mzml')),key=lambda p:p.filename.lower())
            for p in entries:
                if p.file_size>2_000_000_000:raise ValueError('Unreasonably large mzML member: '+p.filename)
                yield p.filename,z.read(p)
    else:raise ValueError('Specify a mzML file, directory or ZIP containing mzML files: '+str(path))

def manifest_map(path):
    if not path:return {}
    path=Path(path)
    if not path.exists():raise FileNotFoundError(path)
    if path.suffix.lower()=='.json':
        records=json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(records,dict):records=records['runs']
    else:
        with path.open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
    byhash={}
    for row in records:
        h=str(row.get('source_sha256') or row.get('sha256') or '').strip().lower()
        if not re.fullmatch('[a-f0-9]{64}',h):raise ValueError('Manifest requires SHA-256 of each mzML file')
        if h in byhash:raise ValueError('Duplicate SHA-256 in manifest')
        byhash[h]=row
    return byhash

def infer_metadata(path, rawhash):
    name=path.replace('\\','/')
    low=name.lower()
    phase=('TD' if re.search(r'(^|[_/])td([_./]|$)',low) else
           'PY' if re.search(r'(^|[_/])py([_./]|$)',low) else
           'SS' if re.search(r'(^|[_/])ss([_./]|$)',low) else
           'EGA' if re.search(r'(^|[_/])ega([_./]|$)',low) else 'UNKNOWN')
    label=Path(name).stem
    blank=bool(re.search(r'(^|[/_])(bl|blank)([_/.]|$)',low))
    # Never infer unknown phase to be GC; require manifest/correct filename.
    run_type='blank' if blank else 'sample'
    sample_id=re.sub(r'(?i)(_td|_py|_ss|_ega)(?=\W|$)','',label)
    return {'source_sha256':rawhash,'source_file':name,'sample_label':label,
            'sample_id':sample_id,'run_type':run_type,'phase':phase,'mass_mg':None}

def msp_text(name, masses, intensities, comment):
    if not masses:return ''
    maxval=max(intensities)
    if not math.isfinite(maxval) or maxval<=0:return ''
    peaks=[]
    for m,v in zip(masses,intensities):
        if 35<=int(m)<=550 and math.isfinite(float(v)) and v>0:
            peaks.append((int(m),max(1,round(999.0*float(v)/maxval))))
    if not peaks:return ''
    peaks.sort(key=lambda t:-t[1])
    lines=['Name: '+name,'Comment: '+comment,'Num Peaks: '+str(len(peaks))]
    lines.extend('; '.join(f'{mz} {intensity}' for mz,intensity in peaks[i:i+8]) for i in range(0,len(peaks),8))
    return '\r\n'.join(lines)+'\r\n\r\n'

def select_runs(raw_items, byhash):
    rows=[];seen=set();known=set()
    for path, raw in raw_items:
        h=sha(raw)
        if h in seen:raise ValueError('Same mzML appears twice in input: '+path)
        seen.add(h)
        if byhash and h not in byhash:raise ValueError('mzML missing from supplied manifest: '+path)
        info=dict(infer_metadata(path,h),**byhash.get(h,{}))
        phase=str(info.get('phase') or '').upper().strip()
        if phase in ('BLANK','BL','GC BLANK'):
            folder=str(info.get('folder_mode') or '').upper()
            # The original Kobe archive has 500-scan EGA blanks and 1600-scan GC blanks
            # in the same folder. A method/manifest is essential for reliable sorting.
            count=info.get('n_scans')
            if folder=='EGA' and str(count)=='500':phase='EGA'
            else:phase='GC_BLANK'
        if phase not in ('SS','TD','PY','EGA','GC_BLANK'):
            raise ValueError('Cannot infer GC phase for '+path+'; supply --manifest CSV/JSON with phase=SS/TD/PY/EGA and exact source_sha256')
        info['phase']=phase
        if info.get('run_id') and not re.fullmatch(r'Q\d{2,}',str(info['run_id'])):
            raise ValueError('Invalid manifest run_id: '+str(info['run_id']))
        rows.append((path, raw, info))
    if not rows:raise ValueError('No mzML files found')
    return rows

def main(argv=None):
    arg=argparse.ArgumentParser(description=__doc__)
    arg.add_argument('--input',required=True,help='mzML archive .zip, mzML directory or individual .mzml file')
    arg.add_argument('--manifest',help='CSV/JSON with source_sha256,phase,run_id,sample_id,run_type')
    arg.add_argument('--config',default=str(BASE/'settings'/'deconvolution.json'))
    arg.add_argument('--output',default=str(BASE/'nist_search'))
    arg.add_argument('--dry-run',action='store_true',help='Check names and phases; no deconvolution')
    args=arg.parse_args(argv)
    out=Path(args.output).expanduser().resolve()
    setting_path=Path(args.config)
    config=json.loads(setting_path.read_text(encoding='utf-8-sig'))
    settings=Settings(**config['parameters']);settings_hash=sha(setting_path.read_bytes())
    byhash=manifest_map(args.manifest)
    rows=select_runs(stream_inputs(Path(args.input)),byhash)
    assigned_ids=set()
    for n,(_,_,info) in enumerate(rows,1):
        info['run_id']=str(info.get('run_id') or f'Q{n:02d}')
        if info['run_id'] in assigned_ids:raise ValueError('Duplicate run_id '+info['run_id'])
        assigned_ids.add(info['run_id'])
    print('PyGCMS Pipeline v'+VERSION+' experimental Global NNLS')
    print('Sources:',len(rows),' / GC:',sum(info['phase']!='EGA' for _,_,info in rows),' / EGA:',sum(info['phase']=='EGA' for _,_,info in rows))
    if args.dry_run:
        for path,raw,info in rows:print(info['run_id'], info['phase'],info.get('run_type'), path,sha(raw)[:10])
        return 0
    # Existing search responses are *never* reused with altered spectra.
    if (out/'results').exists() and any((out/'results').rglob('responses/*.json')):
        raise RuntimeError('NIST response checkpoints are present. Do not overwrite: use a NEW output directory for each deconvolution run.')
    if (out/'inputs').exists() and any(p.is_file() and p.name not in ('.gitkeep',) for p in (out/'inputs').rglob('*')):
        raise RuntimeError('A previous NIST input or partial deconvolution exists. Use a fresh output directory to prevent candidate/peak mismatches.')
    inp=out/'inputs'; audit=out.parent/'audit_v141'
    for part in ['per_run_unique','per_run_original','per_run_component_source']:
        (inp/part).mkdir(parents=True,exist_ok=True)
    run_infos=[];queries=[];allqc=[];ega=[];allsource=[];metadata=[]
    t0=time.perf_counter()
    for path,raw,meta in rows:
        k=meta['run_id'];h=sha(raw)
        print(f'[{k}] {meta["phase"]} ...',flush=True)
        d=decode_mzml(raw)
        md={**meta,'source_file':path,'source_sha256':h,'source_format':d.meta.get('source_format'), 'ms1_scans':d.meta.get('selected_records'), 'excluded_ms2':d.meta.get('ignored_non_ms1')}
        metadata.append(md)
        if meta['phase']=='EGA':
            ega.append({'run_id':k,'phase':meta['phase'],'sample_label':meta.get('sample_label'),
                        'source_file':path,'n_scans':len(d.rt),'rt_start':float(d.rt[0]),'rt_end':float(d.rt[-1]),
                        'tic_integral':float(np.trapezoid(d.tic,d.rt))})
            continue
        results,diag=extraction(d.rt,d.eic,d.mz,settings)
        if diag['allocation_conservation_rel_error']>1e-5 or diag['exported_component_area']>diag['total_signal_area']*(1+1e-5):
            raise RuntimeError('Unacceptable area conservation in '+k)
        fields=[];entries=[];originalblocks=[];uniqueblocks=[]
        for c in results:
            idx=int(c['component_index']); t=float(c['rt_min']);scan=int(c['scan']);n=int(c['ion_count'])
            original=f'PGCMS_{idx:04d}_RT_{t:.3f}_SCAN_{scan}'
            name=k+'_'+original
            good=(n>=settings.min_ms_ions)
            flags=c['flags']
            if t<2:flags=(flags+';' if flags else '')+'EARLY_RT_REVIEW'
            fields.append({'No':idx,'RT_min':f'{t:.3f}','Scan':scan,'TIC':int(d.tic[scan]),
                'RawIons':int(np.count_nonzero(d.eic[scan])),'PureIons':n,'TotalIntensity':round(float(c['allocated_area']),7),
                'Compound':'','Formula':'','MW':'','NIST_MF':'','NIST_RMF':'','NIST_CAS':'','NIST_Rank':'','NIST_Prob':'','NIST_Lib':'','Source':'',
                'NIST_SearchEligible':'yes' if good else 'no',
                'NIST_SearchEligibilityReason':'eligible' if good else 'insufficient_ions',
                'BasePeak_mz':c['base_peak_mz'],'Top5_mz':';'.join(map(str,c['mass'][:5])),
                'CSVSchemaVersion':'Pygcms_v141_GLOBAL_NNLS_component_source',
                'ClassificationModelVersion':'2.2.0','Deconv_Algorithm':'global-NNLS / shared cell allocation; NOT AMDIS',
                'Deconv_AlgorithmVersion':'0.3.1-experimental','Deconv_FitL2_Local':round(c['fit_l2_local'],5),
                'Deconv_ApexPurity':round(c['apex_purity'],5),'Deconv_PeakSNR':round(c['apex_snr'],3),
                'Deconv_SeedScore':round(c['seed_score'],3),'Deconv_ReviewFlag':flags,
                'Deconv_GlobalArea':round(diag['total_signal_area'],5),
                'Deconv_GlobalAllocatedArea':round(diag['allocated_component_area'],5),
                'Deconv_WholeRunUnassignedArea':round(diag['unassigned_signal_area'],5),
                'Deconv_Pass':c['pass'],'Deconv_RawmzML_SHA256':h,'Deconv_Config_SHA256':settings_hash})
            if not good:continue
            comment=f'Run_ID={k} OriginalName={original} RT_min={t:.3f} Scan={scan} PureIons={n} v1.4.1_GLOBAL_NNLS_experimental=true'
            a=msp_text(name,c['mass'],c['intensities'],comment)
            b=msp_text(original,c['mass'],c['intensities'],comment)
            if not a:raise RuntimeError('Eligible component produced empty MSP')
            # Global names must be immutable even if the NIST GUI returns result groups out of order.
            q={'query_name':name,'original_name':original,'run_id':k,'component_index':idx,
                'component_id':k+f'_C{idx:04d}','run_search_sequence':len(entries)+1,
                'batch_search_sequence':None,'fa_only_search_sequence':None,'scan':scan,
                'scan_index_basis':'zero-based','rt_min':t,'rt_exported_3dp':f'{t:.3f}',
                'retained_ion_count':n,'eligibility':True,'minimum_ion_count':settings.min_ms_ions,
                'identity_status':'unidentified; external NIST required','sample_id':meta.get('sample_id'),
                'sample_label':meta.get('sample_label'),'phase':meta['phase'],'run_type':meta.get('run_type'),
                'is_FA':bool(meta.get('is_FA',str(meta.get('run_type','')).lower() in ('fa','fa試料'))),
                'mass_label_mg':meta.get('mass_mg'),'source_file':path,'source_sha256':h,
                'native_tic_at_apex':int(d.tic[scan]),
                'original_msp_path':f'inputs/per_run_original/{k}_deconvolved_for_NIST.msp',
                'unique_msp_path':f'inputs/per_run_unique/{k}_unique_for_NIST.msp',
                'component_source_csv_path':f'inputs/per_run_component_source/{k}_component_source.csv',
                'normalized_base_peak':999,'msp_text':a,'spectrum_body_sha256':sha(a.encode('ascii')),
                'deconvolution_method':DECONV,'fit_quality':1.0-c['fit_l2_local'],
                'local_ion_purity':c['apex_purity']}
            entries.append(q);originalblocks.append(b);uniqueblocks.append(a)
        paths={'original_msp_path':f'inputs/per_run_original/{k}_deconvolved_for_NIST.msp',
               'unique_msp_path':f'inputs/per_run_unique/{k}_unique_for_NIST.msp',
               'component_source_csv_path':f'inputs/per_run_component_source/{k}_component_source.csv'}
        original_bytes='\r\n'.join(originalblocks).encode('ascii')
        unique_bytes='\r\n'.join(uniqueblocks).encode('ascii')
        (out/paths['original_msp_path']).write_bytes(original_bytes)
        (out/paths['unique_msp_path']).write_bytes(unique_bytes)
        csvpath=out/paths['component_source_csv_path'];dump_csv(csvpath,fields,SRC_CSV_FIELDS)
        run_info={**paths,'run_id':k,'sample_label':str(meta.get('sample_label') or k),
                  'sample_id':str(meta.get('sample_id') or k),'phase':meta['phase'],
                  'run_type':meta.get('run_type'),'is_FA':bool(entries and entries[0]['is_FA']),
                  'source_file':path,'source_sha256':h,'components':len(results),'eligible_queries':len(entries),
                  'excluded_components':len(results)-len(entries),
                  'original_msp_sha256':sha(original_bytes),'unique_msp_sha256':sha(unique_bytes),
                  'official_component_source_csv_sha256':sha(csvpath.read_bytes())}
        run_infos.append(run_info);queries.extend(entries)
        qa_flags=[]
        if diag['model_overprediction_fraction']>0.10:qa_flags.append('OVERPREDICTION_GT_10PCT_REVIEW')
        if diag['accounted_fraction']<0.80:qa_flags.append('LOW_MODEL_ACCOUNTED_FRACTION_REVIEW')
        if diag['model_relative_l2']>0.35:qa_flags.append('HIGH_GLOBAL_L2_REVIEW')
        allqc.append({'run_id':k,'phase':meta['phase'],'source_file':path,'source_sha256':h,
                      'QA_status':'REQUIRES_REVIEW' if qa_flags else 'NUMERICAL_CHECKS_ONLY',
                      'QA_review_flags':';'.join(qa_flags),**diag})
        allsource.extend([{'Run_ID':k,'Sample':meta.get('sample_label'),'Phase':meta['phase'],**v} for v in fields])
        print(f'[{k}] components={len(results)}, MSP={len(entries)}, signal-accounted={diag["accounted_fraction"]*100:.1f}%, overprediction={diag["model_overprediction_fraction"]*100:.1f}%',flush=True)
    if not queries:raise ValueError('No GC spectra suitable for searching; check phases and thresholds')
    queries.sort(key=lambda z:(z['run_id'],z['component_index']))
    fa_n=0
    for n,q in enumerate(queries,1):
        q['batch_search_sequence']=n
        if q['is_FA']:fa_n+=1;q['fa_only_search_sequence']=fa_n
    # No change to the order or raw identity of the deconvoluted MSP blocks.
    allbytes='\r\n'.join(q['msp_text'] for q in queries).encode('ascii')
    fabytes='\r\n'.join(q['msp_text'] for q in queries if q['is_FA']).encode('ascii')
    (inp/'All_GC_unique.msp').write_bytes(allbytes)
    (inp/'FA_only_unique.msp').write_bytes(fabytes)
    alloff=0;faoff=0
    for q in queries:
        b=q['msp_text'].encode('ascii')
        q['all_gc_msp_byte_offset']=alloff;q['all_gc_msp_block_bytes']=len(b);alloff+=len(b)+2
        if q['is_FA']:q['fa_only_msp_byte_offset']=faoff;faoff+=len(b)+2
        else:q['fa_only_msp_byte_offset']=None
    index={'schema':'PyGCMS-Pipeline-v1.4.1-index','software_version':VERSION,
           'source_tag':'v1.4.1 experimental global NNLS; v1.4.0 NIST bridge/QC unchanged',
           'deconvolution':DECONV,'parameters_sha256':settings_hash,
           'msp_encoding':'ASCII CRLF','eligibility_rule':'min 3 retained ions; no identity confirmation',
           'counts':{'GC_runs':len(run_infos),'EGA_runs':len(ega),'candidate_components':len(allsource),
                     'nist_eligible_spectra':len(queries),'FA_eligible_spectra':fa_n},
           'combined_msp':{'all':'inputs/All_GC_unique.msp','fa':'inputs/FA_only_unique.msp'},
           'runs':run_infos,'queries':queries}
    dump_json(inp/'query_index.json',index)
    dump_json(inp/'run_metadata.json',metadata)
    dump_json(audit/'all_run_diagnostics.json',{'created_utc':iso_now(),'version':VERSION,
             'parameters':asdict(settings),'source_input':str(args.input),'GC':allqc,'EGA':ega,
             'NIST_executed':False,'independent_AMDIS_validated':False,
             'note':'Mass closure does not prove peak identities, baseline correctness or chromatographic separation.'})
    dump_csv(audit/'all_components_before_NIST.csv',allsource,['Run_ID','Sample','Phase']+SRC_CSV_FIELDS)
    dump_csv(audit/'run_QA.csv',allqc,list(dict.fromkeys(k for r in allqc for k in r)))
    dump_csv(audit/'EGA_TIC_summary.csv',ega,['run_id','phase','sample_label','source_file','n_scans','rt_start','rt_end','tic_integral'])
    print('Prepared',len(queries),'unique NIST MSP records. No licensed NIST search was performed.')
    print('Elapsed (seconds)',round(time.perf_counter()-t0,1))
    print('NIST input:',inp/'query_index.json')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print('ERROR:',exc,file=sys.stderr);sys.exit(2)
