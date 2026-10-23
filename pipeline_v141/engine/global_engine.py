"""Experimental globally-coupled GC-MS EI spectral separation with conserved intensity.

Method: per-ion noise and EIC extrema -> shape templates -> one GLOBAL, sparse,
nonnegative multivariate fit across the full chromatogram -> spectral/profile duplicate
suppression -> single global refit -> residual feature inventory. Components compete
for the same observed ion counts. For reporting area, overlapping model contributions
are capped together at EACH scan x m/z (conservative shared allocation), never
independently. Thus no intensity is assigned to two components.

NOT NIST AMDIS. A proof of signal accounting is NOT a validation of identities.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from amdis_like import (Settings as OriginalSettings, robust_stein_noise_factor,
                        baseline, perceive, make_seeds, _shape)

@dataclass
class Settings:
    min_rt:float=0.0
    baseline_window_scans:int=501
    baseline_percentile:float=12.0
    baseline_stride:int=10
    smooth_sigma_scans:float=1.2
    noise_segment:int=13
    min_eic_snr:float=5.0
    min_eic_prominence_snr:float=4.0
    min_eic_relative_baseline:float=0.012
    min_peak_width_scans:float=2.5
    max_peak_width_scans:float=250.0
    min_perception_ions:int=3
    min_strong_support_ions:int=2
    strong_ion_snr:float=12.
    min_seed_score:float=15.
    grouping_scans:int=5
    min_seed_distance_scans:int=5
    min_fit_radius_scans:int=22
    max_fit_radius_scans:int=90
    global_fit_iterations:int=5
    extra_fit_iterations:int=4
    global_fit_rel_tol:float=0.001
    amplitude_min_snr:float=6.
    ion_min_snr:float=3.
    ion_min_basepeak_fraction:float=0.012
    min_ms_ions:int=3
    min_component_area_pct:float=0.0003
    duplicate_apex_scans:int=8
    duplicate_spectrum_cosine:float=0.975
    duplicate_chrom_shape_corr:float=0.965
    residual_passes:int=1
    max_extra_residual_seeds:int=32
    residual_min_scan_separation:int=9

@dataclass
class Profile:
    scan:int
    lo:int
    hi:int
    profile:np.ndarray
    seed_score:float
    width:float
    support:int
    residual_pass:int=0

def construct_profile(Y, seed, p:Settings):
    scan=seed['scan'];width=max(seed['width'],3)
    radius=int(np.clip(3.25*width,p.min_fit_radius_scans,p.max_fit_radius_scans))
    lo=max(0,scan-radius);hi=min(Y.shape[0],scan+radius+1)
    sh=_shape(Y,seed,lo,hi)
    if sh.max(initial=0)<=1e-6:return None
    # Avoid tiny irregular ripples from creating artificial negative widths.
    sh=np.maximum(0,gaussian_filter1d(sh,0.7))
    sh[sh<sh.max()*0.015]=0
    if sh.max(initial=0)<=0:return None
    sh/=sh.max()
    return Profile(scan,lo,hi,sh.astype('float32'),float(seed['score']),width,
                   int(len({e['ion'] for e in seed['events']})),int(seed.get('pass',0)))

def fit_global(Y,profiles,p:Settings,initial=None,iterations=None):
    """One shared linear decomposition; NO per-apex independent model fits.
    Global coordinate-descent NNLS for every ion, with the cached full residual.
    Y_{t,m} = sum_k shape_{t,k}*W_{k,m} + residual_{t,m}.
    """
    K=len(profiles); n,m=Y.shape
    W=np.zeros((K,m),dtype='float32') if initial is None else np.asarray(initial,dtype='float32').copy()
    R=Y.astype('float32',copy=True)
    for k,prof in enumerate(profiles):
        if np.any(W[k]): R[prof.lo:prof.hi]-=prof.profile[:,None]*W[k][None,:]
    rank=sorted(range(K),key=lambda k:-profiles[k].seed_score)
    numit=iterations if iterations is not None else p.global_fit_iterations
    history=[]
    for iteration in range(numit):
        delta_sum=0.;total_sum=0.
        for k in rank:
            prof=profiles[k];shape=prof.profile
            norm2=float(shape@shape)
            if norm2<=1e-7:continue
            sub=R[prof.lo:prof.hi,:]
            # 'old' is already accounted for in residual. Add own response back.
            dots=np.asarray(shape@sub,dtype='float32')
            new=np.maximum(0,W[k]+dots/norm2)
            change=new-W[k]
            if np.any(change):
                sub-=shape[:,None]*change[None,:]
                delta_sum+=float(np.sum(np.abs(change),dtype=np.float64))
            W[k]=new
            total_sum+=float(np.sum(np.abs(new),dtype=np.float64))
        history.append(delta_sum/max(1,total_sum))
        if iteration>=2 and history[-1]<p.global_fit_rel_tol:break
    return W,R,history

def collapse_duplicates(profs,W,p:Settings):
    """Require both spectral cosine AND chromatographic shape agreement.
    Distinct maxima without such agreement are never automatically merged.
    """
    bytime=sorted(range(len(profs)),key=lambda i:profs[i].scan)
    keep=np.ones(len(profs),dtype=bool)
    pairs=[]
    for ix,k in enumerate(bytime):
        if not keep[k]:continue
        a=profs[k];wa=W[k];na=float(np.linalg.norm(wa))
        if na<1e-7:continue
        for j in bytime[ix+1:]:
            b=profs[j]
            if b.scan-a.scan>p.duplicate_apex_scans:break
            if not keep[j]:continue
            wb=W[j];nb=float(np.linalg.norm(wb))
            if nb<1e-7:continue
            cosine=float((wa@wb)/(na*nb))
            if cosine<p.duplicate_spectrum_cosine:continue
            lo=max(a.lo,b.lo);hi=min(a.hi,b.hi)
            if hi-lo<4:continue
            pa=a.profile[lo-a.lo:hi-a.lo];pb=b.profile[lo-b.lo:hi-b.lo]
            c=float(np.corrcoef(pa,pb)[0,1]) if np.std(pa)>0 and np.std(pb)>0 else 0
            if c<p.duplicate_chrom_shape_corr:continue
            strength_a=float(wa.sum()*a.profile.sum());strength_b=float(wb.sum()*b.profile.sum())
            rejected=(j if strength_a>=strength_b else k)
            selected=(k if rejected==j else j)
            keep[rejected]=False
            pairs.append((profs[selected].scan,profs[rejected].scan,round(cosine,5),round(c,5)))
            if rejected==k:break
    return [v for i,v in enumerate(profs) if keep[i]], len(profs)-int(keep.sum()),pairs

def intensity_accounting(Y,profiles,W,R,step):
    """Account for the SAME observed ion once, everywhere.
    m_{t,m}=sum shape_{t,k} w_{k,m}, q=min(1,Y/m), allocated_k=shape*w*q.
    Then sum_k allocated_{k,t,m}=min(Y_{t,m},m_{t,m}) <=Y_{t,m}.
    A residual record is retained; clipping alone is NOT fit quality evidence.
    """
    pred=np.maximum(0.,Y-R)
    eps=1e-6
    factor=np.minimum(1.0,Y/np.maximum(pred,eps))
    factor[~np.isfinite(factor)]=0
    areas=np.zeros_like(W)
    for k,prof in enumerate(profiles):
        weights=(prof.profile.astype('float64')@factor[prof.lo:prof.hi,:].astype('float64')) * step
        areas[k,:]=(W[k,:]*weights).astype('float32')
    ysum=float(Y.sum(dtype=np.float64)*step)
    rawpred=float(pred.sum(dtype=np.float64)*step)
    accounted=float(np.minimum(Y,pred).sum(dtype=np.float64)*step)
    over=float(np.maximum(pred-Y,0).sum(dtype=np.float64)*step)
    used=float(areas.sum(dtype=np.float64))
    err=abs(used-accounted)/max(ysum,1.)
    if err>1e-5:raise AssertionError(f'Global mass conservation mismatch: {used} vs {accounted} ({err})')
    if used>ysum*(1+1e-6):raise AssertionError('DOUBLE COUNTED intensity; abort')
    metrics={'total_signal_area':ysum,'unscaled_model_area':rawpred,
             'allocated_component_area':used,'unassigned_signal_area':ysum-used,
             'model_positive_residual_area':ysum-accounted,
             'model_overprediction_area':over,
             'model_overprediction_fraction':over/max(ysum,1),
             'accounted_fraction':accounted/max(ysum,1),
             'allocation_conservation_rel_error':err,
             'model_relative_l2':float(np.linalg.norm(R)/max(np.linalg.norm(Y),1e-10))}
    # Ratio per scanning mass cell is guaranteed <= 1 by construction.
    return areas,metrics, pred, factor

def observed_local_metrics(Y,R,profiles,W,areas,noise):
    metrics=[]
    for k,pf in enumerate(profiles):
        a=areas[k];peak=float(W[k].max(initial=0))
        mz0=int(np.argmax(W[k]))
        SNR=float(peak/max(noise[mz0],1))
        local=Y[pf.lo:pf.hi]
        actual=float(np.linalg.norm(local))
        model=local-R[pf.lo:pf.hi]
        err=float(np.linalg.norm(R[pf.lo:pf.hi]))/max(actual,1e-9)
        own=float(a.sum(dtype=np.float64))
        total=float(model[pf.scan-pf.lo,:].sum())
        purity=float((pf.profile[pf.scan-pf.lo]*W[k].sum())/max(total,1e-8))
        metrics.append((SNR,err,own,min(1.,purity)))
    return metrics

def extraction(rt,raw,mz,settings=None, debug=False):
    p=settings or Settings()
    x=np.asarray(raw,dtype='float32')
    rt=np.asarray(rt,dtype='float64')
    op=OriginalSettings(**{key:getattr(p,key) for key in OriginalSettings.__dataclass_fields__ if hasattr(p,key)})
    bg=baseline(x,op)
    Y=np.maximum(0,x-bg)
    if p.smooth_sigma_scans>0:Y=gaussian_filter1d(Y,p.smooth_sigma_scans,axis=0)
    NF,segments=robust_stein_noise_factor(x,p.noise_segment)
    d=np.abs(np.diff(x,axis=0))
    noise=np.maximum(1,np.maximum(np.median(d,axis=0)/(.954*np.sqrt(2))*.7,NF*np.sqrt(np.median(x,axis=0))*.75)).astype('float32')
    op._computed_noise=noise;op._medianraw=np.median(x,axis=0)
    events=perceive(Y,x,mz,op,noise)
    first=make_seeds(events,len(rt),op,min_rt_scan=int(np.searchsorted(rt,p.min_rt)))
    profs=[q for seed in first if (q:=construct_profile(Y,seed,p)) is not None]
    W,R,hist=fit_global(Y,profs,p)
    # Prevent false redundant coeluting representatives and refit all retained profiles.
    profs,nremoved,removed_pairs=collapse_duplicates(profs,W,p)
    W,R,hist2=fit_global(Y,profs,p)
    residual_added=0;residual_events=0
    if p.residual_passes and len(profs):
        # Residual is seeded only at distinct apex groups, then all original and
        # residual shapes are re-estimated in one global model.
        positive=np.maximum(0,R)
        revents=perceive(gaussian_filter1d(positive,0.6,axis=0),x,mz,op,noise,residual_pass=1)
        residual_events=len(revents)
        extra=make_seeds(revents,len(rt),op,min_rt_scan=int(np.searchsorted(rt,p.min_rt)),
                         prior=[{'scan':p0.scan} for p0 in profs],residual=True)
        extra=[e for e in extra if not any(abs(e['scan']-q.scan)<p.residual_min_scan_separation for q in profs)]
        extra=sorted(extra,key=lambda e:-e['score'])[:p.max_extra_residual_seeds]
        xprofs=[q for seed in extra if (q:=construct_profile(Y,seed,p)) is not None]
        if xprofs:
            residual_added=len(xprofs)
            profs+=xprofs
            W,R,hist3=fit_global(Y,profs,p,iterations=p.extra_fit_iterations)
            profs,nremoved2,removed_pairs2=collapse_duplicates(profs,W,p)
            nremoved+=nremoved2;removed_pairs+=removed_pairs2
            W,R,hist4=fit_global(Y,profs,p,iterations=p.global_fit_iterations)
    step=float(np.median(np.diff(rt)))
    # Eliminate extremely weak / near-zero mode templates BEFORE final mass accounting.
    # Refit the remaining entire chromatogram together, not one peak at a time.
    preliminary_areas,_,_,_=intensity_accounting(Y,profs,W,R,step)
    keep=[k for k in range(len(profs)) if (W[k].max(initial=0)>=p.amplitude_min_snr*max(noise[int(np.argmax(W[k]))],1)
         and preliminary_areas[k].sum(dtype=np.float64)>=max(1.,float(Y.sum(dtype=np.float64)*step)*p.min_component_area_pct/100))]
    pruned_below_detection=len(profs)-len(keep)
    if pruned_below_detection:
        profs=[profs[k] for k in keep]
        W,R,hist5=fit_global(Y,profs,p,iterations=max(p.global_fit_iterations,6))
    areas,metrics,pred,factor=intensity_accounting(Y,profs,W,R,step)
    local_metrics=observed_local_metrics(Y,R,profs,W,areas,noise)
    rows=[];excluded=[]
    for k,pf in enumerate(profs):
        snr,local_err,area,purity=local_metrics[k]
        intensities=areas[k]
        BP=float(intensities.max(initial=0))
        if BP<=0:continue
        # Post-allocation spectrum, not additive area from independent local fits.
        retain=(intensities>=np.maximum(p.ion_min_snr*noise*step,intensities.max()*p.ion_min_basepeak_fraction))
        nions=int(retain.sum());peak_amp=float(W[k].max(initial=0))
        reason=[]
        if snr<p.amplitude_min_snr:reason.append('WEAK_PEAK_SNR')
        if nions<p.min_ms_ions:reason.append('INSUFFICIENT_IONS')
        if area < metrics['total_signal_area']*p.min_component_area_pct/100:reason.append('TRACE_AREA')
        if local_err>0.9:reason.append('HIGH_LOCAL_RESIDUAL')
        if purity<0.15:reason.append('LOW_APEX_PURITY')
        # Retain trace/low-ion modes for accounting, but flag; NIST eligibility
        # remains separately controlled by >=3 fitted ions.
        order=np.flatnonzero(retain)
        order=order[np.argsort(intensities[order])[::-1]]
        rows.append({'scan':pf.scan,'rt_min':float(rt[pf.scan]),'mass':np.asarray(mz[order],dtype=int).tolist(),
           'intensities':np.asarray(intensities[order],dtype=float).tolist(),
           'ion_count':int(len(order)),'allocated_area':area,
           'all_ion_area':area,'apex_snr':snr,'fit_l2_local':local_err,'apex_purity':purity,
           'seed_score':pf.seed_score,'pass':pf.residual_pass,'flags':';'.join(reason),
           'seed_support':pf.support,'base_peak_mz':int(mz[np.argmax(intensities)]),
           'raw_component_peak_apex':peak_amp})
    rows.sort(key=lambda c:(c['scan'],-c['allocated_area']))
    for i,c in enumerate(rows,1):c['component_index']=i
    exported_area=sum((v['allocated_area'] for v in rows))
    diag={**metrics,'components':len(rows), 'search_eligible':sum(v['ion_count']>=p.min_ms_ions for v in rows),
          'all_templates':len(profs),'excluded_templates':pruned_below_detection,
          'exported_component_area':exported_area,
          'exported_fraction':exported_area/max(metrics['total_signal_area'],1),
          'area_closure_error':abs(exported_area-metrics['allocated_component_area'])/max(metrics['total_signal_area'],1),
          'removed_coeluting_redundant':nremoved,'seed_events':len(events),'first_seeds':len(first),
          'residual_events':residual_events,'residual_seeds_added':residual_added,
          'nf_factor':NF,'nf_segments':segments,'median_ion_count':float(np.median([v['ion_count'] for v in rows])) if rows else 0,
          'locally_high_residual_count':sum('HIGH_LOCAL_RESIDUAL' in v['flags'] for v in rows),
          'source_signal_area':float(x.sum(dtype=np.float64)*step),
          'baseline_area':float(bg.sum(dtype=np.float64)*step),
          'smooth_integral_impact':float(Y.sum(dtype=np.float64)*step)-float(np.maximum(0,x-bg).sum(dtype=np.float64)*step),
          'nnls_iterations':len(hist)+len(hist2)}
    if debug:return rows,diag,{'Y':Y,'bg':bg,'pred':pred,'R':R,'profiles':profs,'W':W,'factor':factor,'areas':areas,'events':events,'removed_pairs':removed_pairs,'excluded':excluded,'noise':noise}
    return rows,diag
