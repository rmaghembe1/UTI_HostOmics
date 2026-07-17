#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sys, zipfile
from pathlib import Path
from typing import Dict, List, Sequence, Tuple
from xml.etree import ElementTree as ET
import pandas as pd

VERSION='U27B3D1_v1.0_2026-07-16'
TAG='phaseU27B3D1_manuscript_wide_content_structure_audit'
DEFAULT_MANUSCRIPT='__UTI_HOSTOMICS_PROJECT_ROOT__/09_manuscript_docx/phaseU27B3C41_integrated_figure_section_cleanup/UTI_HostOmics_preZotero_manuscript_v5_2_U27B3C41_figure_section_cleaned.docx'
W_NS='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; NS={'w':W_NS}
SECTION_ALIASES={
'abstract':'Abstract','introduction':'Introduction','methods':'Methods','materials and methods':'Methods','results':'Results','discussion':'Discussion','limitations':'Limitations','future directions':'Future directions','concluding model':'Concluding model','conclusion':'Conclusion','conclusions':'Conclusion','data availability':'Data availability','code availability':'Code availability','ethics statement':'Ethics statement','author contributions':'Author contributions','competing interests':'Competing interests','funding':'Funding','acknowledgements':'Acknowledgements','acknowledgments':'Acknowledgements','figures':'Figures','supplementary tables':'Supplementary tables','remaining reference gaps after citation-key cleanup':'Reference gap register','reference table for zotero finalization':'Reference table'}
FROZEN_DATASETS={'GSE112098':'human urinary/systemic inflammatory comparator','GSE280297':'mouse pregnancy-associated UTI model','GSE168600':'mouse recurrent or prior-exposure bladder model','GSE252321':'single-cell UPEC experiment'}
OBSOLETE={
'GSE186800':'Earlier recurrence-trigger identifier; replace with the frozen GSE168600 architecture where appropriate.',
'GSE261018':'Held diagnostic dataset; exclude from the final formal architecture.',
'17 modules':'Earlier compact validation story; replace with the 78-submodule, 10-axis evidence architecture.',
'17 validated modules':'Earlier compact validation story.',
'phase u5':'Obsolete early-phase analysis language.','phase u6':'Obsolete early-phase analysis language.','phase u7':'Obsolete early-phase analysis language.','phase u8':'Obsolete early-phase analysis language.','phase u9':'Obsolete early-phase analysis language.','phase u10':'Obsolete traceability language.','phase u11':'Obsolete traceability language.','phase u12':'Obsolete methods language.','phase u13':'Obsolete discussion-scaffold language.','04_scripts/':'Obsolete project path; current scripts are under 10_scripts/.','six-figure':'Obsolete architecture; the frozen package has 8 figures.'}
CURRENT_CONCEPTS={
'expanded_submodule_architecture':('78 curated submodules','ten biological axes'),
'recurrent_infection_core':('TLR4','leptin','PI3K-AKT'),
'pregnancy_branch_selectivity':('branch-selective','steroid','preterm'),
'single_cell_reconstruction':('27,385','18 clusters','14 refined subtypes'),
'complement_architecture':('C3a/C5a','opsonophagocytosis','complement'),
'metabolic_boundary':('transcriptionally inferred','flux'),
'single_cell_boundary':('n=2','0.333'),
'cross_dataset_boundary':('analyzed independently','standardized effects','directional concordance')}
TREATMENT={'Front matter':'REPLACE_OR_UPDATE','Abstract':'REPLACE','Introduction':'MAJOR_REVISION','Methods':'REPLACE','Results':'FREEZE_EXCEPT_COPYEDITING','Discussion':'REPLACE','Limitations':'REPLACE_OR_EXPAND','Future directions':'REPLACE_OR_EXPAND','Concluding model':'REPLACE','Conclusion':'REPLACE','Data availability':'REPLACE','Code availability':'REPLACE','Ethics statement':'RETAIN_WITH_JOURNAL_REFINEMENT','Author contributions':'RETAIN_PENDING_AUTHOR_CONFIRMATION','Competing interests':'RETAIN_PENDING_FINALIZATION','Funding':'REPLACE_WITH_CONFIRMED_FUNDING','Acknowledgements':'RETAIN_PENDING_FINALIZATION','Figures':'FREEZE','Supplementary tables':'REPLACE_AND_RENUMBER','Reference gap register':'RETAIN_TEMPORARILY','Reference table':'RETAIN_TEMPORARILY'}

def log(m): print(f'[U27B3D1] {m}',flush=True)
def sha256(p:Path)->str:
 d=hashlib.sha256();
 with p.open('rb') as h:
  for b in iter(lambda:h.read(1024*1024),b''): d.update(b)
 return d.hexdigest()
def norm(t): return re.sub(r'\s+',' ',str(t)).strip()
def ptext(p):
 s=[]
 for n in p.iter():
  local=n.tag.rsplit('}',1)[-1]
  if local=='t': s.append(n.text or '')
  elif local=='tab': s.append('\t')
  elif local in {'br','cr'}: s.append('\n')
 return norm(''.join(s))
def pstyle(p):
 ppr=p.find('w:pPr',NS)
 if ppr is None:return ''
 st=ppr.find('w:pStyle',NS)
 return '' if st is None else st.attrib.get(f'{{{W_NS}}}val','')
def detect(t):
 c=re.sub(r'^\d+(?:\.\d+)*\s*','',norm(t).lower()).rstrip(':.')
 if c in SECTION_ALIASES:return SECTION_ALIASES[c]
 if c.startswith('figure 1.') and 'study architecture' in c:return 'Figures'
 return ''
def read_docx(path:Path):
 with zipfile.ZipFile(path) as z:
  root=ET.fromstring(z.read('word/document.xml')); body=root.find('w:body',NS)
  if body is None: raise RuntimeError('No word/body element found.')
  rows=[]; pi=0; ti=0
  for bi,e in enumerate(list(body)):
   local=e.tag.rsplit('}',1)[-1]
   if local=='p':
    tx=ptext(e); rows.append({'body_index':bi,'element_type':'paragraph','paragraph_index':pi,'table_index':'','text':tx,'style_id':pstyle(e),'detected_section':detect(tx),'word_count':len(re.findall(r"\b[\w'-]+\b",tx)),'character_count':len(tx),'has_drawing':any(n.tag.rsplit('}',1)[-1] in {'drawing','pict'} for n in e.iter())}); pi+=1
   elif local=='tbl':
    tx=ptext(e); rows.append({'body_index':bi,'element_type':'table','paragraph_index':'','table_index':ti,'text':tx,'style_id':'','detected_section':'','word_count':len(re.findall(r"\b[\w'-]+\b",tx)),'character_count':len(tx),'has_drawing':False}); ti+=1
  media=sum(1 for n in z.namelist() if n.startswith('word/media/') and not n.endswith('/'))
 return pd.DataFrame(rows),pi,media
def boundaries(frame):
 p=frame[frame.element_type=='paragraph']; d=p[p.detected_section.astype(str)!=''].sort_values('body_index')
 rec=[]
 if d.empty:return pd.DataFrame()
 arr=d.to_dict('records'); first=int(arr[0]['body_index'])
 if first>0:rec.append({'section':'Front matter','heading_body_index':'','content_start_body_index':0,'content_end_body_index':first-1})
 for i,r in enumerate(arr):
  start=int(r['body_index'])+1; end=int(arr[i+1]['body_index'])-1 if i+1<len(arr) else int(frame.body_index.max())
  rec.append({'section':r['detected_section'],'heading_body_index':int(r['body_index']),'content_start_body_index':start,'content_end_body_index':end})
 out=[]
 for r in rec:
  sub=frame[frame.body_index.between(int(r['content_start_body_index']),int(r['content_end_body_index']))]
  out.append({**r,'content_elements':len(sub),'content_paragraphs':int((sub.element_type=='paragraph').sum()),'content_tables':int((sub.element_type=='table').sum()),'word_count':int(sub.word_count.sum()),'text':'\n'.join(sub.text.fillna('').astype(str))})
 return pd.DataFrame(out)
def sec_text(b,section):
 r=b[b.section==section]; return '' if r.empty else '\n'.join(r.text.fillna('').astype(str))
def contains_all(text,terms):
 low=text.lower(); return all(t.lower() in low for t in terms)
def fig_nums(text): return sorted({int(m.group(1)) for m in re.finditer(r'\bFigure\s+([1-9]\d*)',text,re.I)})

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--project-root',default='__UTI_HOSTOMICS_PROJECT_ROOT__'); ap.add_argument('--manuscript',default=DEFAULT_MANUSCRIPT); a=ap.parse_args()
 project=Path(a.project_root).resolve(); manuscript=Path(a.manuscript).resolve()
 if not manuscript.exists(): raise FileNotFoundError(f'Cleaned v5.2 manuscript not found: {manuscript}')
 outt=project/'06_tables'/TAG; outm=project/'03_metadata'/TAG; outr=project/'05_results'/TAG
 for d in (outt,outm,outr): d.mkdir(parents=True,exist_ok=True)
 frame,pc,media=read_docx(manuscript); b=boundaries(frame)
 frame.to_csv(outt/'UTI_HostOmics_U27B3D1_document_element_inventory.tsv',sep='\t',index=False)
 b.drop(columns=['text']).to_csv(outt/'UTI_HostOmics_U27B3D1_section_boundary_inventory.tsv',sep='\t',index=False)
 full='\n'.join(frame.text.fillna('').astype(str)); treatment=[]
 for _,r in b.iterrows():
  section=str(r.section); text=str(r.text); low=text.lower(); obs=[t for t in OBSOLETE if t.lower() in low]; req=[cid for cid,terms in CURRENT_CONCEPTS.items() if contains_all(text,terms)]
  treatment.append({'section':section,'word_count':int(r.word_count),'content_paragraphs':int(r.content_paragraphs),'content_tables':int(r.content_tables),'recommended_treatment':TREATMENT.get(section,'REVIEW_AND_CLASSIFY'),'obsolete_hits':'; '.join(obs),'current_required_concepts_present':'; '.join(req),'contains_GSE168600':'gse168600' in low,'contains_GSE186800':'gse186800' in low,'contains_78_submodules':('78 curated submodules' in low or '78 submodules' in low),'contains_10_axes':('ten biological axes' in low or '10 biological axes' in low),'contains_figure_1_to_8':set(range(1,9)).issubset(set(fig_nums(text)))})
 tf=pd.DataFrame(treatment); tf.to_csv(outt/'UTI_HostOmics_U27B3D1_section_treatment_map.tsv',sep='\t',index=False)
 obs=[]
 for term,ex in OBSOLETE.items():
  count=len(list(re.finditer(re.escape(term),full,re.I))); obs.append({'term':term,'occurrence_count':count,'present':bool(count),'required_action':ex})
 of=pd.DataFrame(obs); of.to_csv(outt/'UTI_HostOmics_U27B3D1_obsolete_term_path_audit.tsv',sep='\t',index=False)
 ds=[]
 for s in tf.section:
  text=sec_text(b,s).lower()
  for dataset,role in FROZEN_DATASETS.items(): ds.append({'section':s,'dataset':dataset,'frozen_role':role,'present':dataset.lower() in text})
 pd.DataFrame(ds).to_csv(outt/'UTI_HostOmics_U27B3D1_dataset_section_consistency_audit.tsv',sep='\t',index=False)
 concepts=[]
 for s in tf.section:
  text=sec_text(b,s)
  for cid,terms in CURRENT_CONCEPTS.items(): concepts.append({'section':s,'concept_id':cid,'required_terms':'; '.join(terms),'present':contains_all(text,terms)})
 pd.DataFrame(concepts).to_csv(outt/'UTI_HostOmics_U27B3D1_current_concept_coverage_audit.tsv',sep='\t',index=False)
 results=sec_text(b,'Results'); figures=sec_text(b,'Figures'); refs=fig_nums(results); caps=fig_nums(figures)
 ff=pd.DataFrame([{'figure_number':n,'referenced_in_results':n in refs,'caption_present_in_figures_section':n in caps,'expected_in_frozen_package':True} for n in range(1,9)])
 ff.to_csv(outt/'UTI_HostOmics_U27B3D1_figure_consistency_audit.tsv',sep='\t',index=False)
 supp=sec_text(b,'Supplementary tables'); sn=sorted({int(m.group(1)) for m in re.finditer(r'\bTable\s+S(\d+)',supp,re.I)})
 pd.DataFrame([{'supplementary_table':f'Table S{n}','present':True,'recommended_action':'Rebuild and renumber against frozen U26-U27 outputs.'} for n in sn]).to_csv(outt/'UTI_HostOmics_U27B3D1_supplementary_table_audit.tsv',sep='\t',index=False)
 av=[]
 for s in ('Data availability','Code availability'):
  text=sec_text(b,s).lower(); av.append({'section':s,'text_present':bool(norm(text)),'contains_GSE186800':'gse186800' in text,'contains_GSE168600':'gse168600' in text,'contains_04_scripts':'04_scripts/' in text,'contains_10_scripts':'10_scripts/' in text,'recommended_treatment':'REPLACE'})
 pd.DataFrame(av).to_csv(outt/'UTI_HostOmics_U27B3D1_availability_statement_audit.tsv',sep='\t',index=False)
 vp=[]
 for pat in (r'draft manuscript v4\.1',r'pre-zotero manuscript v4',r'generated:\s*2026-07-09',r'draft generated 2026-07-09'):
  c=len(list(re.finditer(pat,full,re.I))); vp.append({'pattern':pat,'occurrence_count':c,'present':bool(c),'recommended_action':'Update in the v6.0 derivative.'})
 pd.DataFrame(vp).to_csv(outt/'UTI_HostOmics_U27B3D1_version_label_audit.tsv',sep='\t',index=False)
 recon=[(1,'Front matter','Update version label, title, author block, affiliations and keywords.'),(2,'Abstract','Rewrite around four frozen datasets, 78 submodules, recurrent TLR4-leptin-PI3K-AKT core, pregnancy steroid decoupling, cellular localization and complement.'),(3,'Introduction','Refocus on endocrine-metabolic-immune integration, pregnancy outcomes, cell-source localization and complement.'),(4,'Methods','Reconstruct from U26-U27 provenance: species-native scoring, effect-size synthesis, evidence classes, single-cell reconstruction, pseudobulk localization and figure freezing.'),(5,'Results','Freeze U27B3C2 text; permit only copyediting and cross-reference repair.'),(6,'Discussion','Rewrite around recurrent infection core, steroid synthesis-response decoupling, immunometabolism, complement and cellular attribution.'),(7,'Limitations','Expand pregnancy FDR, dam identifier, n=2 versus n=2, exact p=0.333, cross-species integration and transcript-not-flux limits.'),(8,'Conclusions','Rewrite around the integrated evidence hierarchy in Figure 8.'),(9,'Data availability','Replace with four frozen datasets and final package locations.'),(10,'Code availability','Replace legacy 04_scripts path with 10_scripts and repository status.'),(11,'Figures','Freeze Figures 1-8 and U27B3B legends.'),(12,'Supplementary tables','Rebuild and renumber from frozen U26-U27 source tables.'),(13,'References','Resolve citation keys and remaining gaps through Zotero.')]
 pd.DataFrame(recon,columns=['sequence','component','required_action']).to_csv(outm/'UTI_HostOmics_U27B3D1_v6_reconstruction_map.tsv',sep='\t',index=False)
 rr=tf[tf.section=='Results']; fr=tf[tf.section=='Figures']
 results_ready=bool(len(rr)==1 and rr.iloc[0].contains_GSE168600 and rr.iloc[0].contains_78_submodules and rr.iloc[0].contains_10_axes)
 figures_ready=bool(len(fr)==1 and ff.caption_present_in_figures_section.all())
 replacement=int(tf[tf.recommended_treatment.isin(['REPLACE','MAJOR_REVISION','REPLACE_OR_UPDATE','REPLACE_OR_EXPAND','REPLACE_AND_RENUMBER','REPLACE_WITH_CONFIRMED_FUNDING'])].shape[0])
 occurrences=int(of.occurrence_count.sum()); decision='READY_FOR_U27B3D2_MANUSCRIPT_WIDE_V6_RECONSTRUCTION' if results_ready and figures_ready and replacement>0 else 'TARGETED_U27B3D1_AUDIT_OR_FROZEN_SECTION_REPAIR_REQUIRED'
 pd.DataFrame([{'phase':'U27B3D1','decision':decision,'manuscript_path':str(manuscript),'manuscript_sha256':sha256(manuscript),'paragraphs':pc,'embedded_media_files':media,'sections_identified':len(b),'sections_requiring_replacement_or_major_revision':replacement,'obsolete_term_or_path_occurrences':occurrences,'results_section_ready_to_freeze':results_ready,'figures_1_to_8_ready_to_freeze':figures_ready,'frozen_datasets_detected_in_results':all(d.lower() in results.lower() for d in FROZEN_DATASETS),'supplementary_tables_detected':len(sn),'manuscript_modified':False,'scientific_values_recalculated':False,'figure_assets_modified':False,'source_locks_changed':False,'next_phase':'U27B3D2 create a new v6.0 derivative using frozen Results and Figures 1-8 while reconstructing the remaining scientific sections' if decision.startswith('READY_FOR_U27B3D2') else 'Repair audit ambiguity'}]).to_csv(outt/'UTI_HostOmics_U27B3D1_phase_decision.tsv',sep='\t',index=False)
 report=outr/'UTI_HostOmics_U27B3D1_manuscript_wide_audit_report.md'
 with report.open('w',encoding='utf-8') as h:
  h.write(f'# Phase U27B3D1 - Manuscript-wide content and structure audit\n\n- Version: `{VERSION}`\n- Decision: **{decision}**\n- Manuscript: `{manuscript}`\n- SHA256: `{sha256(manuscript)}`\n- Sections identified: **{len(b)}**.\n- Sections requiring replacement or major revision: **{replacement}**.\n- Obsolete dataset/phase/path occurrences: **{occurrences}**.\n- Results frozen-ready: **{results_ready}**.\n- Figures 1-8 frozen-ready: **{figures_ready}**.\n- Supplementary tables detected: **{len(sn)}**.\n\n## Section decisions\n\n')
  for _,r in tf.iterrows(): h.write(f"- **{r.section}**: `{r.recommended_treatment}`"+(f"; obsolete hits: {r.obsolete_hits}" if r.obsolete_hits else '')+'.\n')
  h.write('\n## Frozen components\n\n- U27B3C2 Results section: retain as the scientific backbone.\n- U27B3A Figures 1-8: retain without redesign.\n- U27B3B definitive legends: retain without scientific expansion.\n\n## Reconstruction boundary\n\nU27B3D2 must create a new v6.0 derivative and must not overwrite v5.2. Results, figures and legends remain fixed except for copyediting and cross-reference normalization. Abstract, Introduction, Methods, Discussion, limitations, conclusions, availability statements and supplementary tables require reconstruction.\n')
 manifest={'version':VERSION,'decision':decision,'manuscript_path':str(manuscript),'manuscript_sha256':sha256(manuscript),'sections_identified':len(b),'sections_requiring_replacement_or_major_revision':replacement,'obsolete_occurrences':occurrences,'results_ready':results_ready,'figures_ready':figures_ready,'supplementary_tables_detected':len(sn),'manuscript_modified':False,'scientific_values_recalculated':False,'figure_assets_modified':False,'source_locks_changed':False}
 (outr/'UTI_HostOmics_U27B3D1_run_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 log(f'Sections identified: {len(b)}'); log(f'Sections requiring replacement/major revision: {replacement}'); log(f'Obsolete occurrences: {occurrences}'); log(f'Results frozen-ready: {results_ready}'); log(f'Figures frozen-ready: {figures_ready}'); log(f'Decision: {decision}'); log(f'Report: {report}')
 return 0
if __name__=='__main__':
 try: raise SystemExit(main())
 except Exception as e:
  print(f'[U27B3D1] ERROR: {e}',file=sys.stderr); raise
