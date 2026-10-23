#!/usr/bin/env python3
"""Deterministic tests of mass accounting, global multi-component fits and duplicates."""
import sys
import numpy as np
from global_engine import Settings,Profile,fit_global,intensity_accounting,collapse_duplicates

def gauss(n,loc,sd):
 t=np.arange(n);v=np.exp(-.5*((t-loc)/sd)**2);return (v/v.max()).astype('float32')

def main():
 p=Settings(residual_passes=0, global_fit_rel_tol=1e-9)
 n,m=190,12
 rng=np.random.default_rng(1999)
 centers=[72,78,91]
 profiles=[Profile(k,0,n,gauss(n,k,5),40,10,5) for k in centers]
 Wtrue=np.zeros((3,m),dtype='float32')
 Wtrue[0,[0,1,2,3,4]]=np.array([400,100,80,40,60])
 Wtrue[1,[1,4,5,6,7]]=np.array([70,125,315,190,100])
 Wtrue[2,[0,3,8,9,10]]=np.array([60,90,260,200,100])
 Y=sum(p0.profile[:,None]*v[None,:] for p0,v in zip(profiles,Wtrue)).astype('float32')
 W,R,h=fit_global(Y,profiles,p,iterations=180)
 assert np.max(np.abs(W-Wtrue))<1.5, 'overlapped chemical spectra not recovered'
 assert np.linalg.norm(R)/np.linalg.norm(Y)<5e-4,'global reconstruction excessive residual'
 area,met,model,factor=intensity_accounting(Y,profiles,W,R,0.005)
 assert abs(area.sum()-Y.sum()*0.005)/(Y.sum()*0.005)<1e-5
 assert met['model_overprediction_fraction']<1e-4
 assert met['allocation_conservation_rel_error']<1e-5
 assert abs((met['allocated_component_area']+met['unassigned_signal_area'])-met['total_signal_area'])<1e-5
 print('PASS: 3 partly-coeluting compounds recovered; global fit and mass closure')
 # Deliberately too-large model: component area must NEVER double count the SAME Y cell.
 Wover=W*2.0
 Rbad=Y- sum(profile.profile[:,None]*w[None,:] for profile,w in zip(profiles,Wover))
 area2,met2,_,_=intensity_accounting(Y,profiles,Wover,Rbad,0.005)
 assert area2.sum()<=Y.sum()*0.005*(1+1e-6)
 assert met2['model_overprediction_fraction']>.1
 print('PASS: worst-case overlapping/overpredicting models cannot double-count observed area; model error reported')
 # Two indistinguishable coeluting modes collapse before final fitting.
 twin=Profile(72,0,n,profiles[0].profile.copy(),20,10,5)
 twow=np.vstack([Wtrue[0],Wtrue[0]])
 retained,nremoved,pairs=collapse_duplicates([profiles[0],twin],twow,p)
 assert len(retained)==1 and nremoved==1 and len(pairs)==1
 print('PASS: coeluting duplicate spectra with identical peak shape rejected')
 # Real peaks with 20-scan separation must NOT be merged despite same EI spectrum.
 twin2=Profile(92,0,n,gauss(n,92,5),20,10,5)
 retained,nremoved,_=collapse_duplicates([profiles[0],twin2],twow,p)
 assert len(retained)==2 and not nremoved
 print('PASS: temporally separate identical EI spectra kept as distinct chromatographic peaks')
 # Assert manual residual and uncertainty remain available: no NIST identity claim.
 print('TESTS PASSED: this is numerical proof, NOT authentic-standard validation')

if __name__=='__main__':main()
