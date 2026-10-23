"""Standards-based mzML (MS1) reader for the public PyGCMS v1.4.1 release.

Only XML mzML with base64 float binary arrays is supported. No Shimadzu QGD
reader, proprietary format decoder, vendor DLL or private converter is used.
The GC EI mass spectra are binned to nominal m/z 35--550. Responses remain
instrument signals, not concentrations.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree as ET
import base64
import zlib

import numpy as np


@dataclass
class MzMLData:
    rt: np.ndarray
    tic: np.ndarray
    eic: np.ndarray
    mz: np.ndarray
    meta: dict


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _cv(element):
    return {x.attrib.get("accession"): x for x in element.iter() if _tag(x) == "cvParam"}


def _decode_array(element):
    params = _cv(element)
    if "MS:1000514" in params:
        kind = "mz"
    elif "MS:1000515" in params:
        kind = "intensity"
    else:
        return None, None

    dtype = np.dtype("<f8") if "MS:1000523" in params else (
        np.dtype("<f4") if "MS:1000521" in params else None
    )
    if dtype is None:
        raise ValueError("mzML: only 32-/64-bit floating-point arrays are supported")
    if "MS:1000140" in params:
        dtype = dtype.newbyteorder(">")
    encodings = {p.attrib.get("accession", "") for p in element.iter()
                 if _tag(p) == "cvParam"}
    if any(e.startswith("MS:10023") for e in encodings) or any(
        "numpress" in p.attrib.get("name", "").lower()
        for p in element.iter() if _tag(p) == "cvParam"
    ):
        raise ValueError("mzML MS-Numpress encoding is not supported; re-export as plain/zlib float mzML")
    allowed_compression = {"MS:1000574", "MS:1000576"}
    compression_codes = {p.attrib.get("accession") for p in element.iter()
                         if _tag(p) == "cvParam" and "compression" in p.attrib.get("name", "").lower()}
    if compression_codes - allowed_compression:
        raise ValueError("mzML has unsupported compression: " + str(compression_codes - allowed_compression))
    if "MS:1000574" in params and "MS:1000576" in params:
        raise ValueError("mzML contains conflicting compression declarations")
    binary = next((e.text for e in element if _tag(e) == "binary"), "") or ""
    try:
        raw = base64.b64decode("".join(binary.split()), validate=True)
        if "MS:1000574" in params:
            raw = zlib.decompress(raw)
        if len(raw) % dtype.itemsize:
            raise ValueError("decoded length is not a whole number of float elements")
        arr = np.frombuffer(raw, dtype=dtype).astype(np.float64)
    except (ValueError, zlib.error) as exc:
        raise ValueError(f"Invalid mzML {kind} binary: {exc}") from exc
    return kind, arr


def _start_time(spectrum):
    for child in spectrum:
        if _tag(child) != "scanList":
            continue
        for scan in child:
            if _tag(scan) != "scan":
                continue
            for c in scan:
                if _tag(c) == "cvParam" and c.attrib.get("accession") == "MS:1000016":
                    value = float(c.attrib["value"])
                    unit = c.attrib.get("unitAccession", "UO:0000031")
                    if unit == "UO:0000010":
                        return value / 60.0
                    if unit == "UO:0000031":
                        return value
                    if unit == "UO:0000032":
                        return value * 60.0
                    raise ValueError("Unsupported mzML scan-time unit " + unit)
    raise ValueError("MS1 spectrum missing scan start time (MS:1000016)")


def decode_mzml(raw: bytes) -> MzMLData:
    """Decode XML mzML to (scan x nominal mass) matrix with RT in minutes."""
    if not isinstance(raw, bytes) or len(raw) < 64:
        raise ValueError("Empty or invalid mzML data")
    if raw[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise ValueError("This is an OLE2/vendor raw file, not mzML")
    if b"<mzML" not in raw[:65536] and b"<indexedmzML" not in raw[:65536]:
        raise ValueError("Input must be XML mzML; conversion is required for vendor-native files")
    times, scans, tics = [], [], []
    count = 0
    ignored_ms2 = 0
    lo, hi = 35, 550
    mzaxis = np.arange(lo, hi + 1, dtype=np.int16)
    try:
        parser = ET.iterparse(BytesIO(raw), events=("end",))
        for _, spectrum in parser:
            if _tag(spectrum) != "spectrum":
                continue
            count += 1
            # Spectrum-level CV is distinct from scan/instrument CV.
            direct_cv = {c.attrib.get("accession"): c for c in spectrum
                         if _tag(c) == "cvParam"}
            level = direct_cv.get("MS:1000511")
            if level is not None and int(level.attrib.get("value", "1")) != 1:
                ignored_ms2 += 1
                spectrum.clear()
                continue
            rt = _start_time(spectrum)
            data = {}
            for child in spectrum:
                if _tag(child) != "binaryDataArrayList":
                    continue
                for entry in child:
                    if _tag(entry) != "binaryDataArray":
                        continue
                    k, vals = _decode_array(entry)
                    if k is not None:
                        if k in data:
                            raise ValueError("Duplicate mzML " + k + " array")
                        data[k] = vals
            if "mz" not in data or "intensity" not in data:
                raise ValueError("MS1 spectrum lacks m/z or intensity array")
            masses, signals = data["mz"], data["intensity"]
            if len(masses) != len(signals):
                raise ValueError("mzML m/z and intensity array lengths differ")
            if not np.isfinite(rt):
                raise ValueError("Nonfinite scan start time")
            if np.any(~np.isfinite(masses)) or np.any(~np.isfinite(signals)):
                raise ValueError("Nonfinite mzML mass/intensity value")
            if np.any(signals < 0):
                raise ValueError("Negative mzML intensity is unsupported; check export")
            nominal = np.floor(masses + 0.5).astype(np.int32)
            valid = (nominal >= lo) & (nominal <= hi) & (signals > 0)
            row = np.zeros(len(mzaxis), dtype=np.float32)
            np.add.at(row, nominal[valid] - lo, signals[valid].astype(np.float32))
            times.append(rt)
            scans.append(row)
            tics.append(float(signals.sum()))
            spectrum.clear()
    except ET.ParseError as exc:
        raise ValueError("Invalid mzML XML: " + str(exc)) from exc
    if len(scans) < 3:
        raise ValueError("At least three MS1 mzML spectra are required for GC deconvolution")
    rt = np.asarray(times, dtype=np.float64)
    if np.any(np.diff(rt) <= 0):
        raise ValueError("mzML MS1 retention times must increase strictly")
    return MzMLData(rt=rt, tic=np.asarray(tics, dtype=np.float64),
                    eic=np.stack(scans, axis=0), mz=mzaxis,
                    meta={"source_records": count,
                          "selected_records": len(scans),
                          "ignored_non_ms1": ignored_ms2,
                          "source_format": "mzML",
                          "nominal_mz_low": lo, "nominal_mz_high": hi,
                          "tic_definition": "sum of mzML MS1 intensity array per scan"})
