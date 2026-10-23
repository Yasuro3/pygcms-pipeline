#!/usr/bin/env python3
"""Read-only smoke tests for XML mzML MS1 importer; no vendor files."""
from __future__ import annotations
import base64
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mzml_native import decode_mzml

def binary(vals, compression=False, f32=False):
    fmt="<"+("f" if f32 else "d")*len(vals)
    b=struct.pack(fmt,*vals)
    if compression:b=zlib.compress(b)
    return base64.b64encode(b).decode("ascii")

def array(kind, vals, compression):
    accession="MS:1000514" if kind=="mz" else "MS:1000515"
    return ('<binaryDataArray><cvParam accession="'+accession+'"/>'
            '<cvParam accession="MS:1000523" name="64-bit float"/>'
            '<cvParam accession="'+("MS:1000574" if compression else "MS:1000576")+
            '" name="'+("zlib compression" if compression else "no compression")+'"/>'
            '<binary>'+binary(vals,compression)+'</binary></binaryDataArray>')

def fake():
    spectra=[]
    for idx in range(4):
        # Alternating zlib and uncompressed arrays; seconds retention unit.
        arrays=array("mz",[45.,60.,73.],bool(idx%2))+array("intensity",[10.,20.+idx,30.],bool(idx%2))
        spectra.append('<spectrum index="'+str(idx)+'"><cvParam accession="MS:1000511" name="ms level" value="1"/>'
                       '<scanList><scan><cvParam accession="MS:1000016" name="scan start time" value="'+str(idx*6)+
                       '" unitAccession="UO:0000010"/></scan></scanList>'
                       '<binaryDataArrayList>'+arrays+'</binaryDataArrayList></spectrum>')
    return ('<?xml version="1.0"?><mzML><run><spectrumList count="4">'+
            ''.join(spectra)+'</spectrumList></run></mzML>').encode("utf-8")

def main():
    d=decode_mzml(fake())
    assert d.eic.shape==(4,516)
    assert abs(float(d.rt[-1])-.3)<1e-8
    assert abs(float(d.eic[2,60-35])-22)<1e-6
    assert d.meta["selected_records"]==4
    print("PASS mzML XML / uncompressed+zlib / seconds / nominal m/z")
    try:decode_mzml(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"+b"0"*200)
    except ValueError as exc:assert "not mzML" in str(exc)
    else:raise AssertionError("Proprietary OLE2 not rejected")
    print("PASS native vendor format refused")
    fixture=Path(__file__).resolve().parents[2]/"data/example/synthetic_gc_ms.mzML"
    if fixture.exists():
        ds=decode_mzml(fixture.read_bytes())
        assert ds.meta["selected_records"]>=100
        print("PASS bundled synthetic mzML")
    print("Tests passed: input parsing only; no analytical accuracy claim.")

if __name__=="__main__":
    main()
