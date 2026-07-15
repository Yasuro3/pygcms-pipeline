#!/usr/bin/env python3
"""Extract documented HTML control defaults from the archived browser application."""
from __future__ import annotations
import argparse, csv, json, re
from html.parser import HTMLParser
from pathlib import Path
class P(HTMLParser):
    def __init__(self): super().__init__(); self.rows=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower() not in {'input','select','textarea'}: return
        d=dict(attrs); ident=d.get('id') or d.get('name')
        if ident: self.rows.append({'element':tag,'id_or_name':ident,'type':d.get('type',''),'default_value':d.get('value',''),'min':d.get('min',''),'max':d.get('max',''),'step':d.get('step',''),'checked':'checked' in d})
def main():
    a=argparse.ArgumentParser(); a.add_argument('software_dir',type=Path); a.add_argument('--outdir',type=Path,required=True); x=a.parse_args(); x.outdir.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in x.software_dir.rglob('*.html'):
        parser=P(); parser.feed(p.read_text(errors='ignore'))
        for r in parser.rows: r['source_file']=str(p.relative_to(x.software_dir)); rows.append(r)
    fields=['source_file','element','id_or_name','type','default_value','min','max','step','checked']
    with (x.outdir/'ui_parameter_defaults.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    (x.outdir/'ui_parameter_defaults.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
