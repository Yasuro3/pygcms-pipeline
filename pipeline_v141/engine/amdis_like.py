"""AMDIS-principle-inspired, open implementation for Shimadzu full-scan GC-MS.

Not NIST AMDIS software. Implements: 13-scan robust ion-count noise factor,
EIC local maxima in noise units, co-maximization/sharpness-based model ion
perception, mass-wise simultaneous nonnegative model fitting with a linear
background and conservative residual-seeded second pass.

Pure spectra are hypotheses and must be confirmed independently.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from scipy.ndimage import gaussian_filter1d, percentile_filter
from scipy.signal import find_peaks
import numpy as np

@dataclass
class Settings:
    min_rt: float=2.0
    noise_segment: int=13
    baseline_window_scans: int=501
    baseline_percentile: float=12.0
    baseline_stride: int=10
    smooth_sigma_scans: float=1.2
    min_eic_snr: float=5.0
    min_eic_prominence_snr: float=4.0
    min_eic_relative_baseline: float=0.012
    min_peak_width_scans: float=2.5
    max_peak_width_scans: float=250.0
    min_perception_ions: int=3
    min_strong_support_ions: int=2
    strong_ion_snr: float=12.0
    min_seed_score: float=15.0
    grouping_scans: int=5
    min_seed_distance_scans: int=5
    max_fit_neighbor_components: int=9
    max_local_radius_scans: int=95
    min_ms_ion_snr: float=4.0
    min_ms_intensity_fraction: float=0.02
    min_library_ions: int=3
    minimal_component_snr: float=6.0
    max_residual_passes: int=1
    residual_min_gain: float=0.006
    residual_seed_snr_multiplier: float=1.3
    coelution_shape_corr_warning: float=0.96


def robust_stein_noise_factor(x, seg=13):
    """Stein AMDIS concept: 13-scan segments that cross their mean >= half."""
    n,m=x.shape
    count=(n//seg)*seg
    a=x[:count,:].reshape(-1,seg,m)
    mean=a.mean(axis=1)
    crossings=(np.diff(a>=mean[:,None,:],axis=1)!=0).sum(axis=1)
    good=(np.min(a,axis=1)>0)&(crossings>=seg//2+1)
    nf=np.median(np.abs(a-mean[:,None,:]),axis=1)/np.sqrt(np.maximum(mean,1))
    goodnf=nf[good & (nf>0) & np.isfinite(nf)]
    if not len(goodnf):return 1.0,0
    return float(np.median(goodnf)),int(len(goodnf))


def baseline(x,p:Settings):
    """Long-window low quantile gives conservative dynamic baseline without
    modeling chromatographic peaks as background. Downsample to keep fast."""
    n=x.shape[0]
    idx=np.arange(0,n,p.baseline_stride)
    if idx[-1]!=n-1:idx=np.r_[idx,n-1]
    w=max(7,int(np.ceil(p.baseline_window_scans/p.baseline_stride)))
    if w%2==0:w+=1
    b=percentile_filter(x[idx,:],percentile=p.baseline_percentile,size=(w,1),mode='nearest')
    b=gaussian_filter1d(b, max(1,30/p.baseline_stride),axis=0,mode='nearest')
    ci=np.arange(n)/p.baseline_stride
    nearest=np.minimum((np.arange(n)//p.baseline_stride),len(idx)-2)
    alpha=((np.arange(n)-idx[nearest])/np.maximum(idx[nearest+1]-idx[nearest],1)).astype(np.float32)
    return (b[nearest,:]*(1-alpha[:,None])+b[nearest+1,:]*alpha[:,None]).astype(np.float32)


def perceive(Y, raw, mz, p:Settings, noise, *, residual_pass=0):
    """EIC-centered component perception with approximate noise-unit gating."""
    n,m=Y.shape
    out=[]
    for j in range(m):
        ion=Y[:,j]
        threshold=float(noise[j])*(p.residual_seed_snr_multiplier if residual_pass else 1.)
        floor=float(p._medianraw[j])*p.min_eic_relative_baseline
        height_thr=max(p.min_eic_snr*threshold, floor)
        prom_thr=max(p.min_eic_prominence_snr*threshold,floor)
        if ion.max(initial=0)<height_thr:continue
        peaks,prop=find_peaks(ion,
            height=height_thr,
            prominence=prom_thr,
            width=(p.min_peak_width_scans,p.max_peak_width_scans),
            distance=3)
        for k,t in enumerate(peaks):
            height=float(prop['peak_heights'][k]);width=float(prop['widths'][k]); prom=float(prop['prominences'][k])
            # AMDIS sharpness based on both sides of apex in noise units.
            A=max(float(raw[t,j]),1.)
            nf=max(float(noise[j])/np.sqrt(A),0.001)
            sl=max((A-float(raw[max(0,t-d),j]))/(d*nf*np.sqrt(A)) for d in range(2,min(9,t+1))) if t>3 else 0.
            sr=max((A-float(raw[min(n-1,t+d),j]))/(d*nf*np.sqrt(A)) for d in range(2,min(9,n-t))) if t<n-4 else 0.
            sharp=max(0.,(sl+sr)/2.)
            snr=prom/max(float(noise[j]),1.)
            out.append({'scan':int(t),'ion':int(j),'mz':int(mz[j]),'snr':float(snr),
              'peak_height':height,'prom':prom,'width':width,'sharpness':float(sharp)})
    return out


def make_seeds(events,n,p:Settings, min_rt_scan=0,prior=None,residual=False):
    if not events:return []
    timeevents={}
    hist=np.zeros(n,dtype=np.float32)
    for e in events:
        t=e['scan']
        if t<min_rt_scan:continue
        timeevents.setdefault(t,[]).append(e)
        # Prevent intense single m/z from dominating a putative component.
        hist[t]+=min(9.,np.log1p(e['snr'])*1.55)
    sm=gaussian_filter1d(hist,1.5)
    prominent,_=find_peaks(sm,height=p.min_seed_score*.5,
                           prominence=p.min_seed_score*.15,distance=5)
    # Distinct ion apex events must remain seed candidates even where two
    # partially coeluting peaks are merged in the smoothed summed chromatogram.
    candidates_scans=set(int(i) for i in prominent)
    for t,elist in timeevents.items():
        if any(e['snr']>=12 for e in elist):candidates_scans.add(int(t))
    candidates=[]
    for t in sorted(candidates_scans):
        chosen={}
        for t2 in range(max(min_rt_scan,t-p.grouping_scans),min(n,t+p.grouping_scans+1)):
            for e in timeevents.get(t2,[]):
                j=e['ion']
                if j not in chosen or e['prom']>chosen[j]['prom']:chosen[j]=e
        if len(chosen)<p.min_perception_ions:continue
        if sum(1 for e in chosen.values() if e['snr']>=p.strong_ion_snr)<p.min_strong_support_ions:continue
        ev=sorted(chosen.values(),key=lambda e:(e['sharpness']*min(e['snr'],70)),reverse=True)
        top=ev[:min(len(ev),20)]
        center=int(round(np.median([v['scan'] for v in top[:min(7,len(top))]])))
        if prior and any(abs(z['scan']-center)<=p.min_seed_distance_scans for z in prior):continue
        score=float(sum(min(9.,np.log1p(e['snr'])*1.5) for e in top))
        if score<p.min_seed_score:continue
        candidates.append({'scan':center,'score':round(score,2),'width':float(np.median([e['width'] for e in top[:7]])),
                 'events':ev,'pass':int(residual)})
    # Remove duplicates, but keep different EIC signatures a few scans apart.
    kept=[];bytime={}
    for c in sorted(candidates,key=lambda c:-c['score']):
        redundant=False
        top={e['ion'] for e in c['events'][:8]}
        radius=int(np.clip(c['width']*1.75,8,26))
        for tt in range(c['scan']-radius,c['scan']+radius+1):
            for v in bytime.get(tt,[]):
                other={e['ion'] for e in v['events'][:8]}
                jac=len(top&other)/max(len(top|other),1)
                # do not merge distinct coeluting ion signatures
                if abs(v['scan']-c['scan'])<=5 or (jac>0.48 and abs(v['scan']-c['scan'])<=max(8,min(radius,24))):redundant=True;break
            if redundant:break
        if not redundant:
            kept.append(c);bytime.setdefault(c['scan'],[]).append(c)
    return sorted(kept,key=lambda c:c['scan'])


def _shape(Y, seed, lo,hi):
    # Sharpness-ranked model-ion profiles; only ions within 75% max sharpness.
    ev=seed['events'];sh=max((e['sharpness'] for e in ev),default=0)
    anchors=[e for e in ev if e['sharpness']>=0.75*sh and abs(e['scan']-seed['scan'])<=4]
    if len(anchors)<2:anchors=ev[:5]
    anchors=sorted(anchors,key=lambda e:e['snr']*max(e['sharpness'],0.1),reverse=True)[:7]
    shapes=[];weights=[]
    for e in anchors:
        y=np.maximum(0.,Y[lo:hi,e['ion']])
        amp=max(float(y.max(initial=0)),1)
        shapes.append(y/amp)
        weights.append(min(8.,np.sqrt(e['snr'])))
    if not shapes:return np.zeros(hi-lo,dtype=np.float32)
    # Weighted mean instead of upper envelope: attenuates interfering ions.
    S=np.stack(shapes)
    v=np.average(S,axis=0,weights=weights)
    v=gaussian_filter1d(v,0.75)
    if v.max(initial=0)>0:v/=v.max()
    return np.asarray(v,dtype=np.float32)


def _nnls_with_linear_baseline(P,Y,iterations=28):
    """Partial-out unconstrained linear nuisance background, solve positive components."""
    L,K=P.shape
    t=np.linspace(-1,1,L).astype(np.float64)
    B=np.stack([np.ones(L),t],axis=1)
    BtB=np.linalg.inv(B.T@B)
    Bty=B.T@Y
    Y0=Y-B@(BtB@Bty)
    P0=P-B@(BtB@(B.T@P))
    G=P0.T@P0
    H=P0.T@Y0
    # coordinate descent gives NNLS-like solution; k<=9, hundreds of ions.
    X=np.maximum(0,H/np.maximum(np.diag(G)[:,None],1e-5))
    for i in range(iterations):
        for k in range(K):
            xk=(H[k]-(G[k]@X)+G[k,k]*X[k])/max(G[k,k],1e-7)
            X[k]=np.maximum(0,xk)
    base_coef=BtB@(Bty-B.T@P@X)
    fit=np.maximum(P@X+B@base_coef,0)
    fit_components=P@X
    return X,fit,fit_components


def extract(Y, raw, mz, rt, seeds, p:Settings, *, signal_for_fitting=None):
    n,m=Y.shape
    components=[]
    predicted=np.zeros((n,m),dtype=np.float32)
    if not seeds:return components,predicted
    scanstep=float(np.median(np.diff(rt)))
    for seed in seeds:
        peak=seed['scan'];width=seed['width']
        radius=int(np.clip(width*3.0,24,p.max_local_radius_scans))
        lo=max(0,peak-radius);hi=min(n,peak+radius+1)
        neighbors=[z for z in seeds if abs(z['scan']-peak)<=radius and z['scan']>=lo and z['scan']<hi]
        if len(neighbors)>p.max_fit_neighbor_components:
            # Cannot claim all neighbours resolved if capacity exhausted.
            neighbors=sorted(neighbors,key=lambda z:(abs(z['scan']-peak),-z['score']))[:p.max_fit_neighbor_components]
        neighbors.sort(key=lambda z:z['scan'])
        ki=next(i for i,z in enumerate(neighbors) if z is seed)
        P=np.stack([_shape(Y,z,lo,hi) for z in neighbors],axis=1).astype(np.float64)
        if P[:,ki].max(initial=0)<0.001:continue
        Corr=np.corrcoef(P.T) if len(neighbors)>1 else np.zeros((1,1))
        q=float(np.nanmax(np.delete(Corr[ki,:],ki))) if len(neighbors)>1 else 0.
        try:
            X,fullfit,compfit=_nnls_with_linear_baseline(P,Y[lo:hi,:].astype(np.float64))
        except (ValueError,np.linalg.LinAlgError):continue
        amps=np.maximum(X[ki,:],0)
        noise=np.asarray(p._computed_noise,dtype=np.float32)
        ampmax=float(amps.max(initial=0))
        if ampmax<=0:continue
        keep=(amps>=np.maximum(p.min_ms_ion_snr*noise,ampmax*p.min_ms_intensity_fraction))&(mz>=35)&(mz<=500)
        ions=np.flatnonzero(keep)
        if not len(ions):continue
        order=ions[np.argsort(amps[ions])[::-1]]
        eicidx=order[:min(10,len(order))]
        obs=Y[lo:hi,eicidx]
        pred=fullfit[:,eicidx]
        qfit=1.-np.linalg.norm(obs-pred)/max(np.linalg.norm(obs),1e-12)
        onpeak=amps[eicidx]*P[peak-lo,ki]
        mixture=compfit[peak-lo,eicidx]
        purity=float(np.median(np.minimum(onpeak/(mixture+1e-9),1.)))
        profile_integral=float(np.trapezoid(P[:,ki],rt[lo:hi]))
        # contribution for each component is not allowed to disappear due to local baseline;
        # predicted is diagnostic, clipped only when reporting area fractions.
        peakSN=ampmax/max(float(noise[order[0]]),1)
        if peakSN<p.minimal_component_snr:continue
        predicted[lo:hi,:]+=np.maximum(0.,P[:,ki:ki+1]@amps[None,:]).astype('float32')
        components.append({'scan':int(peak),'rt_min':float(rt[peak]),'mass':mz[order].astype(int).tolist(),
         'intensities':amps[order].astype(float).tolist(), 'ion_count':len(order),
         'base_peak':int(mz[order[0]]),'base_peak_intensity':ampmax,
         'linear_component_response':float(amps[order].sum()),
         'integrated_area_counts_min':float(amps[order].sum()*profile_integral),
         'fit_quality':round(float(qfit),4),'local_ion_purity':round(purity,4),
         'regional_residual_fraction':round(float(np.linalg.norm(obs-pred)/max(np.linalg.norm(obs),1e-9)),4),
         'support_ions':int(len({e['ion'] for e in seed['events']})),
         'neighbor_count':len(neighbors)-1,'max_profile_correlation_to_neighbor':round(float(q),4),
         'support_score':seed['score'],'peak_snr':round(float(peakSN),2),'pass':seed['pass'],
         'status':'review' if (q>p.coelution_shape_corr_warning or qfit<.50 or purity<.4) else 'tentative',
         'flag':';'.join(x for x,yes in [('UNRESOLVED_SHAPE' ,q>p.coelution_shape_corr_warning),
                                       ('LOW_FIT',qfit<.5),('LOW_LOCAL_PURITY',purity<.4)] if yes)})
    return components,predicted


def deconvolve(rt,raw_eic,mz,params:Settings|None=None,debug=False):
    p=params or Settings()
    # Keep param object serializable; _computed_noise is scratch only.
    x=np.asarray(raw_eic,dtype=np.float32)
    bg=baseline(x,p)
    corrected=np.maximum(0,x-bg)
    Y=gaussian_filter1d(corrected,p.smooth_sigma_scans,axis=0)
    NF,good=robust_stein_noise_factor(x,p.noise_segment)
    # Individual ion noise from scan-to-scan median differences, protected by AMDIS NF.
    d=np.abs(np.diff(x,axis=0))
    diffsig=np.median(d,axis=0)/(.954*np.sqrt(2))
    perion=np.maximum(1.0,np.maximum(diffsig*.7, NF*np.sqrt(np.median(x,axis=0))*.75)).astype(np.float32)
    p._computed_noise=perion
    p._medianraw=np.median(x,axis=0)
    start=int(np.searchsorted(rt,p.min_rt))
    events=perceive(Y,x,mz,p,perion)
    first=make_seeds(events,len(rt),p,min_rt_scan=start)
    comps,pred=extract(Y,x,mz,rt,first,p)
    original_n=len(comps)
    residual_events=[];residual_seeds=[];added=[];redone=0
    if p.max_residual_passes:
        # Residual is a discovery aid, not "unassigned area" proof.  Use positive
        # residuals only and prefer new RT evidence to avoid split duplicates.
        remainder=np.maximum(Y-np.minimum(pred,Y),0)
        residual_events=perceive(remainder,x,mz,p,perion,residual_pass=1)
        residual_seeds=make_seeds(residual_events,len(rt),p,min_rt_scan=start,prior=first,residual=True)
        if residual_seeds:
            # Fit against initial component neighbours to avoid assigning their ions twice.
            allseeds=sorted(first+residual_seeds,key=lambda s:s['scan'])
            more,_=extract(Y,x,mz,rt,allseeds,p)
            prior_by_scan={c['scan']:c for c in comps}
            all_current=[]
            for c in more:
                if c['scan'] in prior_by_scan:
                    all_current.append(c)
                elif c['pass']>0:
                    if c['base_peak_intensity']>=3*perion[np.flatnonzero(mz==c['base_peak'])[0]]:
                        all_current.append(c);added.append(c)
            comps=all_current
            redone=1
    # Avoid supersplit duplicates only when near-identical spectra and nearly identical RT.
    uniq=[];removed=0
    for c in sorted(comps,key=lambda c:-c['support_score']):
        cmap=dict(zip(c['mass'],c['intensities'])); dup=False
        for v in uniq:
            if abs(c['scan']-v['scan'])>4:continue
            vm=dict(zip(v['mass'],v['intensities']))
            keys=set(cmap)&set(vm)
            if len(keys)<3:continue
            a=np.asarray([cmap[k] for k in keys]);b=np.asarray([vm[k] for k in keys]);cs=float(a@b/(np.linalg.norm(a)*np.linalg.norm(b)+1e-15))
            if cs>0.985 and len(keys)/min(len(cmap),len(vm))>.80:
                dup=True;removed+=1;break
        if not dup:uniq.append(c)
    uniq.sort(key=lambda v:(v['scan'],-v['support_score']))
    for i,c in enumerate(uniq,1):c['component_index']=i
    # Diagnostic area: use only unique fitted candidates, refit with same method;
    # residual/coverage below is an operational model signal metric.
    signalarea=float(Y.sum(dtype=np.float64)); explained=float(np.minimum(Y,pred).sum(dtype=np.float64))
    diag={'model':'AMDIS-principle-inspired; not NIST AMDIS software',
      'noise_factor_13scan':round(NF,5),'noise_segments':good,
      'area_signal_baseline_corrected':signalarea,
      'area_model_covered_first_pass':explained,
      'first_pass_area_coverage_fraction':explained/max(signalarea,1),
      'raw_tic_area_sum':float(x.sum(dtype=np.float64)),
      'baseline_area_sum':float(bg.sum(dtype=np.float64)),
      'ion_events':len(events),'ion_events_pass1':len(events),'seed_candidates_pass1':len(first),
      'first_pass_components':original_n,'ion_events_residual':len(residual_events),
      'residual_seed_candidates':len(residual_seeds),'residual_refit':redone,
      'added_residual_components':len(added),'duplicate_removed':removed,
      'components':len(uniq),'library_ready':sum(c['ion_count']>=p.min_library_ions for c in uniq),
      'review_flags':sum(c['status']!='tentative' for c in uniq),
      'median_ions':float(np.median([c['ion_count'] for c in uniq])) if uniq else 0}
    del p._computed_noise
    del p._medianraw
    if debug:return uniq,diag,{'signal':Y,'baseline':bg,'first_pred':pred,'residual':np.maximum(Y-np.minimum(Y,pred),0),
                                'events':events,'residual_events':residual_events,'first_seeds':first}
    return uniq,diag
