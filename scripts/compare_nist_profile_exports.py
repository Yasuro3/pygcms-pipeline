#!/usr/bin/env python3
"""Compare licensed NIST results exported from deconvolution profiles.

Run the same sample under default/permissive/selective presets with the same
licensed NIST build, libraries, search options and top-N. Export each results
CSV, then run this script. It reports apex-matched top-hit/class agreement.
The script contains no NIST data and does not perform a library search.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd


def load(path: Path, label: str) -> pd.DataFrame:
    df=pd.read_csv(path, encoding='utf-8-sig')
    need={'Scan','RT_min','Compound','NIST_Rank','PaperClass9','LiteratureMarkerClass'}
    missing=need-set(df.columns)
    if missing: raise SystemExit(f'{path}: missing columns {sorted(missing)}')
    df=df.copy(); df['profile']=label; return df


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--default',type=Path,required=True)
    ap.add_argument('--permissive',type=Path,required=True)
    ap.add_argument('--selective',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    base=load(a.default,'default')
    rows=[]
    for path,label in [(a.permissive,'permissive'),(a.selective,'selective')]:
        other=load(path,label)
        m=base.merge(other,on='Scan',suffixes=('_default','_'+label))
        rows.append({
            'comparison':f'default_vs_{label}',
            'common_apexes':len(m),
            'top_hit_agreement_pct':100*(m['Compound_default'].fillna('')==m[f'Compound_{label}'].fillna('')).mean() if len(m) else float('nan'),
            'paper9_agreement_pct':100*(m['PaperClass9_default'].fillna('')==m[f'PaperClass9_{label}'].fillna('')).mean() if len(m) else float('nan'),
            'literature_group_agreement_pct':100*(m['LiteratureMarkerClass_default'].fillna('')==m[f'LiteratureMarkerClass_{label}'].fillna('')).mean() if len(m) else float('nan'),
        })
    pd.DataFrame(rows).to_csv(a.out/'licensed_nist_profile_comparison.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    return 0
if __name__=='__main__': raise SystemExit(main())
