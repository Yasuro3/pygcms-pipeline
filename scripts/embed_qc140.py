#!/usr/bin/env python3
"""Synchronize canonical QC JS sources into the self-contained application."""
from pathlib import Path
import argparse,re
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
path=ROOT/'software/index.html';text=path.read_text(encoding='utf-8');updated=text
for marker,filename in [('QC140_ENGINE','qc140.js'),('QC140_UI','qc140_ui.js')]:
 source=(ROOT/'software'/filename).read_text(encoding='utf-8')
 value=f'<!-- {marker}_BEGIN -->\n<script>\n{source}\n</script>\n<!-- {marker}_END -->'
 pattern=rf'<!-- {marker}_BEGIN -->.*?<!-- {marker}_END -->'
 if len(re.findall(pattern,updated,re.S))!=1:raise SystemExit('Missing/duplicate embed marker '+marker)
 updated=re.sub(pattern,lambda m:value,updated,flags=re.S)
if args.check:
 if text!=updated:raise SystemExit('FAIL: canonical QC engine and embedded source differ')
 print('PASS: canonical QC engine and adapter match embedded source')
else:path.write_text(updated,encoding='utf-8');print('QC engine and adapter embedded')
