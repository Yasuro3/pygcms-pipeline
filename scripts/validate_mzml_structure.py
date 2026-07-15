#!/usr/bin/env python3
"""Audit an mzML file against the restricted reader scope documented for PyGCMS Pipeline."""
from __future__ import annotations
import argparse, base64, json, re, struct, zlib
from pathlib import Path
import xml.etree.ElementTree as ET

ACC={'ms_level':'MS:1000511','scan_start_time':'MS:1000016','mz_array':'MS:1000514','intensity_array':'MS:1000515','float32':'MS:1000521','float64':'MS:1000523','zlib':'MS:1000574','no_compression':'MS:1000576','numpress_linear':'MS:1002312','numpress_pic':'MS:1002313','numpress_slof':'MS:1002314','centroid':'MS:1000127','profile':'MS:1000128'}
def local(tag): return tag.rsplit('}',1)[-1]
def cvparams(el): return [x for x in el.iter() if local(x.tag)=='cvParam']
def accessions(el): return {x.attrib.get('accession','') for x in cvparams(el)}
def decode_array(bda):
    acc=accessions(bda); binary=next((x for x in bda if local(x.tag)=='binary'),None)
    if binary is None: return None,{'error':'binary element missing'}
    raw=base64.b64decode((binary.text or '').strip()) if (binary.text or '').strip() else b''
    if ACC['zlib'] in acc: raw=zlib.decompress(raw)
    if any(ACC[k] in acc for k in ('numpress_linear','numpress_pic','numpress_slof')): return None,{'error':'MS-Numpress is outside the supported scope'}
    size=4 if ACC['float32'] in acc else 8 if ACC['float64'] in acc else None
    if not size: return None,{'error':'floating-point precision not declared'}
    if len(raw)%size: return None,{'error':'decoded byte length is not divisible by precision'}
    fmt='<'+('f' if size==4 else 'd')*(len(raw)//size)
    vals=list(struct.unpack(fmt,raw)) if raw else []
    role='mz' if ACC['mz_array'] in acc else 'intensity' if ACC['intensity_array'] in acc else 'other'
    return vals,{'role':role,'precision':size*8,'zlib':ACC['zlib'] in acc,'length':len(vals)}
def main():
    p=argparse.ArgumentParser(); p.add_argument('mzml',type=Path); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    result={'file':str(a.mzml),'status':'PASS','spectra':0,'ms1_spectra':0,'profile_spectra':0,'centroid_spectra':0,'errors':[],'warnings':[],'retention_time_units':{},'array_precisions':{},'zlib_arrays':0}
    try: root=ET.parse(a.mzml).getroot()
    except Exception as e: result['status']='FAIL'; result['errors'].append(f'XML parse error: {e}'); root=None
    if root is not None:
      # referenceableParamGroupRef is legal mzML but outside current browser-reader scope.
      if any(local(x.tag)=='referenceableParamGroupRef' for x in root.iter()): result['warnings'].append('referenceableParamGroupRef detected; current browser reader may not resolve all inherited CV parameters.')
      for sp in (x for x in root.iter() if local(x.tag)=='spectrum'):
        result['spectra']+=1; acc=accessions(sp)
        ms=[x for x in cvparams(sp) if x.attrib.get('accession')==ACC['ms_level']]
        level=None
        if ms:
            try: level=int(float(ms[0].attrib.get('value','')))
            except: pass
        if level!=1:
            result['errors'].append(f"Spectrum {sp.attrib.get('id',result['spectra'])}: explicit ms level 1 is required; found {level!r}."); continue
        result['ms1_spectra']+=1
        if ACC['profile'] in acc: result['profile_spectra']+=1
        if ACC['centroid'] in acc: result['centroid_spectra']+=1
        st=[x for x in cvparams(sp) if x.attrib.get('accession')==ACC['scan_start_time']]
        if not st: result['errors'].append(f"Spectrum {sp.attrib.get('id',result['spectra'])}: scan start time missing.")
        else:
            u=st[0].attrib.get('unitAccession') or st[0].attrib.get('unitName') or 'unspecified'; result['retention_time_units'][u]=result['retention_time_units'].get(u,0)+1
        arrays={}
        for bda in (x for x in sp.iter() if local(x.tag)=='binaryDataArray'):
            try: vals,info=decode_array(bda)
            except Exception as e: vals,info=None,{'error':str(e)}
            if 'error' in info: result['errors'].append(f"Spectrum {sp.attrib.get('id')}: {info['error']}"); continue
            arrays[info['role']]=info['length']; result['array_precisions'][str(info['precision'])]=result['array_precisions'].get(str(info['precision']),0)+1; result['zlib_arrays']+=int(info['zlib'])
        if 'mz' not in arrays or 'intensity' not in arrays: result['errors'].append(f"Spectrum {sp.attrib.get('id')}: m/z or intensity array missing.")
        elif arrays['mz']!=arrays['intensity']: result['errors'].append(f"Spectrum {sp.attrib.get('id')}: m/z/intensity lengths differ ({arrays['mz']} vs {arrays['intensity']}).")
        try:
            default_len=int(sp.attrib.get('defaultArrayLength',''))
            if arrays.get('mz') is not None and default_len!=arrays['mz']: result['errors'].append(f"Spectrum {sp.attrib.get('id')}: defaultArrayLength={default_len}, decoded length={arrays['mz']}.")
        except: result['warnings'].append(f"Spectrum {sp.attrib.get('id')}: defaultArrayLength is absent or non-integer.")
      if result['profile_spectra']: result['warnings'].append('Profile spectra are present. The application reduces m/z values to nominal-mass bins and does not preserve accurate-mass profile information.')
      if result['errors']: result['status']='FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    raise SystemExit(0 if result['status']=='PASS' else 2)
if __name__=='__main__': main()
