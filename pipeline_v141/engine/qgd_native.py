"""Read-only Shimadzu QGD/OLE2 parser.  Format ported from released
PyGCMS Pipeline v1.4.0 direct-QGD reader; no vendor DLL required.
Raw TIC, time and data decoding are checked against vendor TIC per scan.
This module does not identify chemical compounds.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct
import numpy as np

END=0xfffffffa
SIG=b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
ENC={1:(6,3),2:(4,2),3:(5,3)}

class CFB:
 def __init__(self,raw:bytes):
  self.b=raw
  if raw[:8]!=SIG: raise ValueError('Not OLE2 (QGD)')
  u16=lambda off:struct.unpack_from('<H',raw,off)[0]
  u32=lambda off:struct.unpack_from('<I',raw,off)[0]
  self.sec=1<<u16(30);self.mini=1<<u16(32)
  if self.sec not in (512,4096): raise ValueError('Unsupported OLE2 sector size')
  def off(v):return (v+1)*self.sec
  self.off=off
  difat=[u32(76+i*4) for i in range(109) if u32(76+i*4)<END]
  ds=u32(68)
  for _ in range(u32(72)):
   if ds>=END:break
   pos=off(ds)
   difat += [u32(pos+4*i) for i in range(self.sec//4-1) if u32(pos+4*i)<END]
   ds=u32(pos+self.sec-4)
  self.fat=np.concatenate([np.frombuffer(raw,offset=off(d),count=self.sec//4,dtype='<u4') for d in difat]).copy()
  def chain(st):
   out=[];p=st
   while p<END:
    if p>=len(self.fat) or len(out)>len(self.fat)+2:raise ValueError('CFB bad FAT chain')
    out.append(int(p));p=int(self.fat[p])
   return out
  self.chain=chain
  def read_fat(st,size):
   if size==0:return b''
   parts=[];left=size
   for si in chain(st):
    n=min(left,self.sec);start=off(si)
    parts.append(raw[start:start+n]);left-=n
    if left<=0:break
   out=b''.join(parts)
   if len(out)!=size:raise ValueError('CFB short FAT stream')
   return out
  self.read_fat=read_fat
  msize=u32(64)*self.sec
  self.minifat=np.frombuffer(read_fat(u32(60),msize),dtype='<u4') if msize and u32(60)<END else np.array([],dtype=np.uint32)
  dir_indices=chain(u32(48))
  directory=read_fat(u32(48),len(dir_indices)*self.sec)
  entries=[]
  for pos in range(0,len(directory),128):
   b=directory[pos:pos+128];nl=struct.unpack_from('<H',b,64)[0]
   name=b[:max(0,nl-2)].decode('utf-16le',errors='replace') if nl else ''
   entries.append((name,b[66],*struct.unpack_from('<III',b,68),struct.unpack_from('<I',b,116)[0],struct.unpack_from('<Q',b,120)[0]))
  self.entries=entries
  root=entries[0]
  self.ministream=read_fat(root[5],root[6]) if root[6] else b''
  self.cutoff=u32(56)
  paths={}
  def walk(idx,parent='',depth=0):
   if idx>=len(entries):return
   if depth>len(entries):raise ValueError('CFB directory loop')
   name,typ,left,right,child,st,size=entries[idx]
   walk(left,parent,depth+1)
   full=(parent+'/' if parent else '')+name
   if typ==2:paths[full]=(st,size)
   elif typ==1:walk(child,full,depth+1)
   walk(right,parent,depth+1)
  walk(root[4]);self.paths=paths
 def read(self,path):
  if path not in self.paths:raise KeyError('QGD stream not found: '+path)
  st,size=self.paths[path]
  if size>=self.cutoff:return self.read_fat(st,size)
  out=bytearray();idx=st
  while idx<END and len(out)<size:
   if idx>=len(self.minifat):raise ValueError('CFB bad miniFAT chain')
   pos=idx*self.mini;out+=self.ministream[pos:pos+min(self.mini,size-len(out))]
   idx=int(self.minifat[idx])
  if len(out)!=size:raise ValueError('CFB short mini stream')
  return bytes(out)

def _record(raw,start,end):
 if start+32>end:raise ValueError('Truncated spectrum header')
 flag,npts=struct.unpack_from('<HH',raw,start+20)
 if flag not in ENC or start+32+npts*ENC[flag][0]>end:
  flag,npts=struct.unpack_from('<HH',raw,start+24)
 if flag not in ENC or start+32+npts*ENC[flag][0]>end:raise ValueError('Unknown/corrupt QGD intensity format')
 channel=struct.unpack_from('<H',raw,start+8)[0]
 return flag,npts,channel

@dataclass
class QGDData:
 rt:np.ndarray
 tic:np.ndarray
 eic:np.ndarray
 mz:np.ndarray
 meta:dict

def decode_qgd(raw:bytes,checksum:bool=True)->QGDData:
 """Preserves all selected-channel nominal mass spectra and vendor TIC."""
 c=CFB(raw)
 rt=np.frombuffer(c.read('GCMS Raw Data/Retention Time'),dtype='<i4').astype(np.float64)/60000
 idx=np.frombuffer(c.read('GCMS Raw Data/Spectrum Index'),dtype='<u4')
 tic=np.frombuffer(c.read('GCMS Raw Data/TIC Data'),dtype='<u8').copy()
 spectra=c.read('GCMS Raw Data/MS Raw Data')
 n=len(rt)
 if not (len(idx)==len(tic)==n):raise ValueError('Inconsistent scan counts')
 if not np.all(idx[1:]>idx[:-1]):raise ValueError('Unsorted spectrum offsets')
 info=[]; groups={}
 for j in range(n):
  flag,pts,ch=_record(spectra,int(idx[j]),int(idx[j+1]) if j<n-1 else len(spectra))
  info.append((flag,pts,ch));groups.setdefault(ch,[]).append(j)
 order=sorted(groups,key=lambda ch:(-np.median([info[i][1] for i in groups[ch]]),-len(groups[ch]),ch))
 selected=order[0]
 js=groups[selected]
 # 35-500 for DS, 50-500 for SS/EGA; preserve native bounds.
 # m/z nominal range is determined from actual decoded positions; wider allocation is harmless.
 lo=35;hi=550
 matrix=np.zeros((len(js),hi-lo+1),dtype=np.float32)
 mismatch=0;saturated=0;rawmzlo=1e6;rawmzhi=0
 for k,j in enumerate(range(n)):
  flag,pts,ch=info[j];rec,width=ENC[flag]
  start=int(idx[j])+32
  b=memoryview(spectra)[start:start+pts*rec]
  if flag==1:
   a=np.frombuffer(b,dtype=[('mz','<u2'),('low','<u2'),('hi','u1'),('sat','u1')])
  elif flag==2:a=np.frombuffer(b,dtype=[('mz','<u2'),('low','<u2')])
  else:a=np.frombuffer(b,dtype=[('mz','<u2'),('low','<u2'),('hi','u1')])
  m=a['mz'].astype(np.uint16,copy=False)
  v=a['low'].astype(np.uint32)
  if width==3:v+=a['hi'].astype(np.uint32)*65536
  sm=int(np.sum(v,dtype=np.uint64))
  if sm!=int(tic[j]):mismatch+=1
  if flag==1 and np.any(a['sat'] & 0x80):saturated+=1
  if ch==selected:
   rawmzlo=min(rawmzlo,float(m.min(initial=65535))/20)
   rawmzhi=max(rawmzhi,float(m.max(initial=0))/20)
   nominal=(m.astype(np.int32)+10)//20
   keep=(nominal>=lo)&(nominal<=hi)&(v>0)
   np.maximum.at(matrix[k],nominal[keep]-lo,v[keep].astype(np.float32))
 if checksum and mismatch:raise ValueError(f'QGD saved TIC mismatch {mismatch}/{n}')
 meta={'source_records':n,'selected_records':len(js),'channels':[{'channel':ch,'n_records':len(inds),'median_points':float(np.median([info[i][1] for i in inds]))} for ch,inds in groups.items()],
       'selected_channel':int(selected),'tic_mismatches':mismatch,'saturated_records':saturated,'native_mz_low':rawmzlo,'native_mz_high':rawmzhi}
 return QGDData(rt[js],tic[js],matrix,np.arange(lo,hi+1,dtype=np.int16),meta)
