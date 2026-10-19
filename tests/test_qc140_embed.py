#!/usr/bin/env python3
"""Require exact canonical/embedded engine equality and coherent release metadata."""
from pathlib import Path
import subprocess,sys,json
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts/embed_qc140.py'),'--check'],check=True)
cff=(ROOT/'CITATION.cff').read_text(encoding='utf-8')
assert '\nversion: 1.4.0\n' in cff
m=json.loads((ROOT/'zenodo_metadata.json').read_text(encoding='utf-8'))['metadata']
assert m['version']=='1.4.0'
assert '2.2.0' in m['description']
print('PASS: v1.4.0 embedded source and release metadata agree')
