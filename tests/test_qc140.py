#!/usr/bin/env python3
"""Browser/invariant tests for v1.4.0 QC, classification and reporting; synthetic only."""
from pathlib import Path
import csv,io,json,tempfile,zipfile
from browser_utils import launch_chromium
try:from playwright.sync_api import sync_playwright
except ImportError:print('SKIP: Playwright required');raise SystemExit(77)
ROOT=Path(__file__).resolve().parents[1]
with sync_playwright() as p:
 b=launch_chromium(p);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.set_content((ROOT/'software/index.html').read_text(),wait_until='load')
 out=page.evaluate('''()=>{
 const E=PyGCMSQC140, tests=[];const check=(v,n)=>{if(!v)throw Error(n);tests.push(n)};
 const c=(name,formula,cas='')=>applyCandidateContexts({name,formula,cas,paperClass:'',cat:'P'},{overrideCat:true});
 for(const [n,f,cas,g] of [['1,3-Cyclohexadiene','C6H8','592-57-4','F'],['1,4-Dioxane','C4H8O2','123-91-1','R'],['1,4-Cyclohex-2-enedione','C6H6O2','4505-38-8','R'],['1,4-Dioxane-2,5-dione, 3,3,6,6-tetramethyl-','C8H12O4','6713-72-0','R'],['Methacrylic anhydride','C8H10O3','760-93-0','R'],['1H-Indene, octahydro-, trans-','C9H16','','F'],['1-Buten-3-yne','C4H4','689-97-4','F'],['Benzene','C6H6','71-43-2','A'],['Toluene','C7H8','108-88-3','A'],['Pyridine','C5H5N','110-86-1','N'],['Thiophene','C4H4S','110-02-1','S']])check(c(n,f,cas).reportingGroup140===g,'structure: '+n);
 check(c('Hexadecanenitrile','C16H31N','629-79-8').finalPaperClass9==='Nitriles','Nitrile structural class');
 check(c('2-Cyclopenten-1-one, 2-methyl-','C6H8O').finalPaperClass9==='Carbonyls','Cyclopentenone not furan');
 const stable=c('1,4-Dioxane','C4H8O2','123-91-1');const before=JSON.stringify(stable);applyCandidateContexts(stable,{overrideCat:true});const after=JSON.stringify(stable);check(stable.cat==='O'&&stable.reportingGroup140==='R','late writer cannot restore wrong OAr');
 const repeated=c('1,4-Dioxane','C4H8O2','123-91-1');for(let i=0;i<5;i++)applyCandidateContexts(repeated,{overrideCat:true});check((String(repeated.catEvid).match(/corrected-model:SATURATED_ETHER_NOT_O_AROMATIC/g)||[]).length===1,'correction evidence does not grow on repeat');check(c('1,4-Dioxane','H8C4O2','123-91-1').reportingGroup140==='R','equivalent formula order accepted');
 check(E.parseFormula('C6H6').C===6&&E.parseFormula('C6H6?')===null,'strict formula parser');check(E.validCAS('0')===''&&E.validCAS('71-43-2')==='71-43-2','CAS checksum');
 const rows=[{No:1,Compound:'Phenol',Formula:'C6H6O',NIST_CAS:'108-95-2',NIST_MF:900,PureIons:4,RT_min:7,TotalIntensity:1000,AI_Reason:'Original reason, preserve me'}, {No:2,Compound:'Phenol',Formula:'C6H6O',NIST_CAS:'108-95-2',NIST_MF:910,PureIons:4,RT_min:7.01,TotalIntensity:100}, {No:3,Compound:'Odd fluorinated compound',Formula:'C22H28FNO',NIST_CAS:'',NIST_MF:999,PureIons:1,RT_min:26,TotalIntensity:10}, {No:4,Compound:'Toluene',Formula:'C7H8',NIST_CAS:'108-88-3',NIST_MF:900,PureIons:4,RT_min:3,TotalIntensity:500}, {No:5,Compound:'Pyridine',Formula:'C5H5N',NIST_CAS:'110-86-1',NIST_MF:799,PureIons:7,RT_min:4,TotalIntensity:400}];
 const originals=JSON.stringify(rows),csv=E.csv(rows);check(E.parseCSV(csv).rows[0].AI_Reason==='Original reason, preserve me','quoted CSV roundtrip');
 const files=[{name:'A_TD_results.csv',text:csv},{name:'A_PY_results.csv',text:E.csv(rows.slice(0,1))}];const manifest=[{Sample:'A_TD',Phase:'TD',Pair_ID:'A',Method_ID:'GC1',Mass_mg:'5'},{Sample:'A_PY',Phase:'PY',Pair_ID:'A',Method_ID:'GC1',Mass_mg:'5'},{Sample:'B_TD',Phase:'TD',Pair_ID:'B',Method_ID:'GC1',Zero_component_run:'true'},{Sample:'B_PY',Phase:'PY',Pair_ID:'B',Method_ID:'GC1',Zero_component_run:'true'}];
 const result=E.run(files,{},manifest,row=>QC140.classifier(row));check(result.metadata.inputRecords===6,'all records retained in audit');check(result.metadata.qualifyingRecords===3,'MF, ions and original exclusions applied');check(JSON.stringify(rows)===originals,'input objects immutable');
 const ph=result.catalogue.find(r=>r.Original_candidate_names==='Phenol');check(ph.TD_n===1&&ph.TD_N===2&&ph.TD_frequency_pct===50,'one count per run, includes zero run');check(ph.Either_n===1&&ph.Paired_N===2&&ph.Either_frequency_pct===50,'paired union, no double count');check(!result.catalogue.some(r=>r.Original_candidate_names==='Odd fluorinated compound'),'one-ion MF999 not reportable');check(result.audit[0].AI_Reason===rows[0].AI_Reason,'original reason preserved');check(result.audit[2].NIST_MF==='999'&&result.audit[2].Compound===rows[2].Compound,'rejected label and score remain archived');
 check(Math.abs(result.runSummary[0].Prethreshold_response-1510)<1e-9,'prethreshold denominator frozen before MF filtering');
 for(const mode of ['corrected_candidate_conditional','identity_conservative']){const a=result.groupSummary.filter(r=>r.Sample==='A_TD'&&r.Mode===mode);check(Math.abs(a.reduce((s,r)=>s+(r.Response_fraction_pct||0),0)-100)<1e-8,'group closure '+mode);}
 let duplicate=false;try{E.run([files[0],files[0]],{},[],row=>QC140.classifier(row));}catch(e){duplicate=/Duplicate component/.test(e.message);}check(duplicate,'duplicate input rejected');
 let missing=false;try{E.run(files,{},[{Sample:'missing',Phase:'TD'}],row=>QC140.classifier(row));}catch(e){missing=/Missing input/.test(e.message);}check(missing,'missing manifest run rejected');
 let invalid=false;try{E.validateSettings({minMF:1000});}catch(e){invalid=true;}check(invalid,'invalid QC setting rejected');
 const bad=[{No:1,Compound:'Pyridine',Formula:'C5H5N',TotalIntensity:1000,NIST_MF:900}];const br=E.run([{name:'X_results.csv',text:E.csv(bad)}],{},[],row=>QC140.classifier(row));check(br.metadata.qualifyingRecords===0,'missing ion count not invented');
 const rt=rows.slice(0,2).map((r,i)=>({...r,RT_min:i?22:7}));const rr=E.run([{name:'X_PY_results.csv',text:E.csv(rt)}],{},[],row=>QC140.classifier(row));check(rr.catalogue[0].Identification_status==='WITHHOLD_EXACT_NAME','multiple RT bands withhold precise name');check(rr.groupSummary.find(x=>x.Mode==='identity_conservative'&&x.Group==='R').Response===1100,'withheld exact identity carried in R');
 const hal=[{No:1,Compound:'Unusual fluorinated compound',Formula:'C10H10FNO',RT_min:15,TotalIntensity:500,NIST_MF:900,PureIons:5}];const hr=E.run([{name:'H_PY_results.csv',text:E.csv(hal)}],{},[],row=>QC140.classifier(row));check(hr.metadata.qualifyingRecords===1&&hr.catalogue[0].Identification_status==='WITHHOLD_EXACT_NAME','halogen flags, not deletion');
 check(!E.htmlTable(result).includes(rows[0].AI_Reason),'print table uses safe summary');let auditInput=false;try{E.run([{name:'audit.csv',text:E.csv(result.audit)}]);}catch(e){auditInput=/already a QC audit/.test(e.message);}check(auditInput,'reimport cannot overwrite old QC history');
 const mixed=E.run([{name:'X_TD_results.csv',text:E.csv(rows.slice(0,1))},{name:'X_PY_results.csv',text:E.csv(rt)}],{},[],row=>QC140.classifier(row));check(mixed.groupSummary.filter(r=>r.Mode==='identity_conservative'&&r.Group==='R').reduce((s,r)=>s+r.Response,0)===2100,'catalogue conservative class agrees across all occurrences');
 QC140.state.files=files;QC140.state.manifest=manifest;return {tests,expected:result.metadata};
 }''')
 page.evaluate('QC140.open()');page.evaluate('QC140.execute()');assert 'candidate-label keys' in page.locator('#q140status').inner_text()
 with tempfile.TemporaryDirectory() as td:
  with page.expect_download() as dl:page.locator('button',has_text='3. Export complete QC report ZIP').click()
  path=Path(td)/'reports.zip';dl.value.save_as(path)
  with zipfile.ZipFile(path) as z:
   assert z.testzip() is None;assert '01_component_QC_audit.csv' in z.namelist();assert '10_printable_inventory.html' in z.namelist()
   d=json.loads(z.read('09_processing_manifest.json'));assert d['candidateKeys']==1
 out['tests'].append('browser ZIP export integrity')
 assert not errors,errors
 b.close()
print('PASS: v1.4.0 QC —',len(out['tests']),'assertion groups, synthetic data, browser UI and ZIP export.')
