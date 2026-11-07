from __future__ import annotations
import copy,hashlib,json,sys,zipfile,subprocess
from pathlib import Path
import pytest
from lxml import etree as E
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from bime.common import *
from bime.convert import convert
from bime.audit import audit
from bime.insert import insert

@pytest.fixture
def cfg():return load_config()

def make(tmp,cfg,content='# 前言\n\n中文內容 English，完整的句子。\n\n## 研究目的\n\n研究目的的文字。\n',name='base'):
    md=tmp/(name+'.md');md.write_text(content,encoding='utf-8');out=tmp/(name+'.docx');convert(md,out,cfg);return out

def patch(path,tmp,fn,name='bad'):
    p=Package(path);fn(p);out=tmp/(name+'.docx');p.save(out);return out

def body_rec(p):return next(r for r in paragraph_records(p) if r['kind']=='body' and r['text'])
def has(report,rid,severity=None):return any(f['rule_id']==rid and (severity is None or f['severity']==severity) for f in report['findings'])
def fragment(tmp,content='新增內容保持原來的章節。\n',name='add'):
    p=tmp/(name+'.md');p.write_text(content,encoding='utf-8');return p

def test_source_hash():
    r=json.loads((ROOT/'references/rules.json').read_text());assert sha(ROOT/'references/source/bime-format-original.docx')==r['sources']['regulation']['sha256']

def test_simple_conversion(tmp_path,cfg):
    out=make(tmp_path,cfg);r=audit(out,cfg);assert r['summary']['error']==0;assert r['summary']['warning']==0
    assert r['metrics']['body_runs_checked']>0
    assert not r['layout_verified']

def test_chapter_subheading_numbering(tmp_path,cfg):
    p=Package(make(tmp_path,cfg));ss=[r['text'] for r in paragraph_records(p) if r['level']];assert ss==['第一章\u3000前言','1.1 研究目的']

def test_hyphen_is_valid(tmp_path,cfg):
    cfg['heading_separator']='-';out=make(tmp_path,cfg);assert not has(audit(out,cfg),'HEADING_NUMBER','error')
    assert '1-1 研究目的' in [r['text'] for r in paragraph_records(Package(out))]

def test_english_double_spacing(tmp_path,cfg):
    out=make(tmp_path,cfg,'# Introduction\n\nA complete English paragraph.\n');p=Package(out);r=body_rec(p);assert Resolver(p).prop(r['element'],'spacing','line',kind='pPr')=='480'

def test_headings_not_forced_12(tmp_path,cfg):
    out=make(tmp_path,cfg);p=Package(out);r=next(r for r in paragraph_records(p) if r['level']==1);run=r['element'].find('.//'+q('w:r'));assert Resolver(p).prop(r['element'],'sz',run=run)=='36';assert not has(audit(out,cfg),'FONT_SIZE','warning')

def test_table_caption(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 前言\n\n表 1-1 測量數據\n\n| 單位 | 數值 |\n|---|---|\n| m | 2 |\n');assert not has(audit(out,cfg),'CAPTION_POSITION','error')

def test_missing_caption_detected(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 前言\n\n| A | B |\n|---|---|\n| 1 | 2 |\n');assert has(audit(out,cfg),'CAPTION_POSITION','error')

def test_math_and_footnote(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 前言\n\n文字[^x]。\n\n$$E=mc^2$$\n\n[^x]: 註腳內容。\n');p=Package(out);assert p.doc.xpath('.//m:oMath',namespaces=NS);refs=p.doc.xpath('.//w:footnoteReference/@w:id',namespaces=NS); assert len(refs)==1; assert refs[0] in p.getxml('word/footnotes.xml').xpath('./w:footnote/@w:id',namespaces=NS)

def test_unicode_paths(tmp_path,cfg):
    d=tmp_path/'有空 白目錄';d.mkdir();out=make(d,cfg,name='研究 報告');assert out.is_file()

def test_remote_images_blocked(tmp_path,cfg):
    with pytest.raises(BimeError,match='Remote'):make(tmp_path,cfg,'![圖 1-1 remote](https://example.org/a.png)')

def test_path_escape_blocked(tmp_path,cfg):
    d=tmp_path/'child';d.mkdir();Image.new('RGB',(10,10)).save(tmp_path/'secret.png')
    with pytest.raises(BimeError,match='outside'):make(d,cfg,'![圖 1-1 x](../secret.png)')

def test_unresolved_citation_blocked(tmp_path,cfg):
    with pytest.raises(BimeError,match='citation'):make(tmp_path,cfg,'A claim [@madeup].')

def test_raw_html_not_silently_lost(tmp_path,cfg):
    with pytest.raises(BimeError,match='raw'):make(tmp_path,cfg,'<script>Important text</script>')

def test_code_not_executed(tmp_path,cfg):
    out=make(tmp_path,cfg,'```python\nraise RuntimeError("do not run")\n```');assert 'raise RuntimeError' in text(Package(out).body)

def test_margin_violation(tmp_path,cfg):
    source=make(tmp_path,cfg)
    out=patch(source,tmp_path,lambda p:p.body.find('w:sectPr/w:pgMar',NS).set(q('w:left'),'500'))
    assert has(audit(out,cfg),'MARGINS','error')

def test_size_override(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):child(child(body_rec(p)['element'].find('.//'+q('w:r')),'w:rPr'),'w:sz').set(q('w:val'),'20')
    out=patch(source,tmp_path,change);assert has(audit(out,cfg),'FONT_SIZE','warning')

def test_color_override(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):child(child(body_rec(p)['element'].find('.//'+q('w:r')),'w:rPr'),'w:color').set(q('w:val'),'FF0000')
    out=patch(source,tmp_path,change);assert has(audit(out,cfg),'TEXT_COLOR','error')

def test_exact_spacing_not_multiple(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):
        n=body_rec(p)['element'].find('w:pPr/w:spacing',NS);n.set(q('w:lineRule'),'exact');n.set(q('w:line'),'360')
    out=patch(source,tmp_path,change);assert has(audit(out,cfg),'LINE_SPACING','warning')

def test_inherited_font_detected(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):
        rec=body_rec(p)
        for run in rec['element'].findall('.//'+q('w:r')):
            n=run.find('w:rPr/w:rFonts',NS)
            if n is not None:n.getparent().remove(n)
        st=p.getxml('word/styles.xml');style=st.find('w:style[@w:styleId="'+rec['style']+'"]',NS);font=child(child(style,'w:rPr'),'w:rFonts');font.set(q('w:eastAsia'),'Arial');font.set(q('w:ascii'),'Arial');font.set(q('w:hAnsi'),'Arial');p.setxml('word/styles.xml',st)
    out=patch(source,tmp_path,change);r=audit(out,cfg);assert has(r,'FONT_ZH','warning');assert has(r,'FONT_EN','warning')

def test_theme_override_is_resolved(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):
        r=body_rec(p)['element'].find('.//'+q('w:r'));n=r.find('w:rPr/w:rFonts',NS);n.set(q('w:asciiTheme'),'minorHAnsi');n.set(q('w:hAnsiTheme'),'minorHAnsi')
    out=patch(source,tmp_path,change);assert has(audit(out,cfg),'FONT_EN')

def test_audit_read_only(tmp_path,cfg):
    source=make(tmp_path,cfg);before=source.read_bytes();audit(source,cfg);assert source.read_bytes()==before

def test_fragment_does_not_require_cover(tmp_path,cfg):
    out=make(tmp_path,cfg);r=audit(out,cfg);assert r['coverage']['STRUCTURE']['status']=='not_applicable_to_selected_scope'

def test_thesis_page_origin_is_decided_not_conflicting(tmp_path,cfg):
    # The regulation text and the TOC sample disagree; the friend template breaks the tie (誌謝 = i).
    out=make(tmp_path,cfg);r=audit(out,cfg,'thesis');assert has(r,'PAGE_ORIGIN','manual');assert not has(r,'PAGE_ORIGIN','conflict');assert has(r,'STRUCTURE','warning')

def test_keyword_count(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 中文摘要\n\n摘要文字。\n\n關鍵詞：甲；乙\n');assert has(audit(out,cfg),'KEYWORDS','error')

def test_keyword_multiword(tmp_path,cfg):
    out=make(tmp_path,cfg,'# Abstract\n\nThis is an abstract.\n\nKeywords: machine learning; image restoration; academic writing\n');assert not has(audit(out,cfg),'KEYWORDS','error')

def test_abstract_list_warning(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 中文摘要\n\n1. 條列摘要。\n2. 另一點。\n\n關鍵詞：甲；乙；丙\n');assert has(audit(out,cfg),'ABSTRACT_LIST','warning')

def test_plain_insert_preserves_original_nodes_and_parts(tmp_path,cfg):
    source=make(tmp_path,cfg);before=source.read_bytes();md=fragment(tmp_path);out=tmp_path/'inserted.docx';r=insert(source,md,out,cfg)
    assert r['original_body_subtrees_unchanged'];assert source.read_bytes()==before;assert '新增內容' in text(Package(out).body)
    a=Package(source);b=Package(out)
    for n in ('docProps/core.xml','docProps/custom.xml','word/theme/theme1.xml'):assert a.parts[n]==b.parts[n]
    assert E.tostring(a.body.find(q('w:sectPr')),method='c14n')==E.tostring(b.body.find(q('w:sectPr')),method='c14n')

def test_insert_preserves_unknown_zip_part(tmp_path,cfg):
    base=make(tmp_path,cfg);source=patch(base,tmp_path,lambda p:p.parts.update({'customXml/private.bin':b'keep this exactly'}),'extra');out=tmp_path/'result.docx';insert(source,fragment(tmp_path),out,cfg);assert Package(out).parts['customXml/private.bin']==b'keep this exactly'

def test_insert_preserves_existing_styles(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';insert(source,fragment(tmp_path),out,cfg);a=Package(source).getxml('word/styles.xml');b=Package(out).getxml('word/styles.xml')
    for s in a.findall(q('w:style')):
        ss=b.find('w:style[@w:styleId="'+s.get(q('w:styleId'))+'"]',NS);assert E.tostring(s,method='c14n')==E.tostring(ss,method='c14n')

def test_insert_under_heading(tmp_path,cfg):
    source=make(tmp_path,cfg,'# 前言\n\n第一章內容。\n\n# 文獻探討\n\n第二章內容。\n');out=tmp_path/'result.docx';insert(source,fragment(tmp_path),out,cfg,mode='under',anchor='第一章 前言');t=text(Package(out).body);assert t.index('第一章內容')<t.index('新增內容')<t.index('第二章\u3000文獻探討')

def test_anchor_missing_no_output(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx'
    with pytest.raises(BimeError,match='anchor not found'):insert(source,fragment(tmp_path),out,cfg,mode='after',anchor='不存在')
    assert not out.exists()

def test_ambiguous_anchor(tmp_path,cfg):
    source=make(tmp_path,cfg,'重複句子。\n\n重複句子。\n');out=tmp_path/'result.docx'
    with pytest.raises(BimeError,match='ambiguous'):insert(source,fragment(tmp_path),out,cfg,mode='after',anchor='重複句子。')

def test_optimistic_hash_guard(tmp_path,cfg):
    source=make(tmp_path,cfg)
    with pytest.raises(BimeError,match='hash'):insert(source,fragment(tmp_path),tmp_path/'result.docx',cfg,expected_sha='wrong')

def test_inplace_forbidden(tmp_path,cfg):
    source=make(tmp_path,cfg)
    with pytest.raises(BimeError,match='source must remain'):insert(source,fragment(tmp_path),source,cfg)

def test_existing_output_guard(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';out.write_bytes(b'do not overwrite')
    with pytest.raises(BimeError,match='Output exists'):insert(source,fragment(tmp_path),out,cfg)
    assert out.read_bytes()==b'do not overwrite'

def test_dry_run_no_commit(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';r=insert(source,fragment(tmp_path),out,cfg,dry_run=True);assert r['dry_run'];assert not out.exists()

def test_duplicate_heading_blocks_insert(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';md=fragment(tmp_path,'## 1.1 重複小節\n\n文字。')
    with pytest.raises(BimeError,match='new hard violations'):insert(source,md,out,cfg)
    assert not out.exists()

def test_allow_draft_is_explicit(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';r=insert(source,fragment(tmp_path,'## 1.1 重複小節\n\n文字。'),out,cfg,allow_draft=True);assert r['new_hard_violations'];assert out.exists()

def test_unnumbered_insert_heading_rejected(tmp_path,cfg):
    source=make(tmp_path,cfg)
    with pytest.raises(BimeError,match='explicit subsection'):insert(source,fragment(tmp_path,'## 新小節\n\n文字。'),tmp_path/'result.docx',cfg)

def test_footnotes_merge(tmp_path,cfg):
    source=make(tmp_path,cfg,'# 前言\n\n舊註腳[^a]。\n\n[^a]: 原始註腳保留。\n');md=fragment(tmp_path,'新增註腳[^b]。\n\n[^b]: 新的註腳。\n');out=tmp_path/'result.docx';insert(source,md,out,cfg)
    p=Package(out);notes=p.getxml('word/footnotes.xml');ids=notes.xpath('./w:footnote/@w:id',namespaces=NS);assert len(ids)==len(set(ids));assert '原始註腳保留。' in text(notes);assert '新的註腳。' in text(notes)
    refs=p.doc.xpath('.//w:footnoteReference/@w:id',namespaces=NS);assert len(set(refs))==2;assert all(i in ids for i in refs)

def test_numbered_lists_merge(tmp_path,cfg):
    source=make(tmp_path,cfg,'# 前言\n\n1. 原清單一。\n2. 原清單二。\n');out=tmp_path/'result.docx';insert(source,fragment(tmp_path,'1. 新清單一。\n2. 新清單二。\n'),out,cfg)
    p=Package(out);num=p.getxml('word/numbering.xml');ids=num.xpath('./w:num/@w:numId',namespaces=NS);assert len(ids)==len(set(ids));refs=p.doc.xpath('.//w:numId/@w:val',namespaces=NS);assert set(refs)<=set(ids)

def test_images_and_hyperlink_merge(tmp_path,cfg):
    Image.new('RGB',(80,40),'white').save(tmp_path/'old.png');Image.new('RGB',(40,80),'gray').save(tmp_path/'new.png')
    source=make(tmp_path,cfg,'# 前言\n\n![圖 1-1 原圖](old.png)\n');out=tmp_path/'result.docx';md=fragment(tmp_path,'![圖 1-2 新圖](new.png)\n\n[說明連結](https://example.org)。\n');insert(source,md,out,cfg)
    a=Package(source);b=Package(out)
    for n in a.parts:
        if n.startswith('word/media/'):assert a.parts[n]==b.parts[n]
    rels=b.getxml('word/_rels/document.xml.rels');ids={n.get('Id') for n in rels};assert set(b.doc.xpath('.//@r:embed | .//@r:id',namespaces=NS))<=ids
    assert len(b.doc.xpath('.//w:drawing',namespaces=NS))==2

def test_revisions_refuse_modification(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):p.body.insert(0,el('w:ins',id='7',author='reviewer'))
    source=patch(source,tmp_path,change)
    with pytest.raises(BimeError,match='tracked changes'):insert(source,fragment(tmp_path),tmp_path/'result.docx',cfg)

def test_locked_document_refused(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):
        s=p.getxml('word/settings.xml');n=child(s,'w:documentProtection');n.set(q('w:edit'),'readOnly');n.set(q('w:enforcement'),'1');p.setxml('word/settings.xml',s)
    source=patch(source,tmp_path,change)
    with pytest.raises(BimeError,match='protection'):insert(source,fragment(tmp_path),tmp_path/'result.docx',cfg)

def test_even_footer_is_checked(tmp_path,cfg):
    source=make(tmp_path,cfg)
    def change(p):
        s=p.getxml('word/settings.xml');child(s,'w:evenAndOddHeaders');p.setxml('word/settings.xml',s)
    source=patch(source,tmp_path,change);assert has(audit(source,cfg),'PAGE_POSITION','error')

def test_config_accepts_role_overrides(tmp_path):
    cfg=tmp_path/'config.json';cfg.write_text('{"role_overrides":{"2":"cover"}}');assert load_config(cfg)['role_overrides']['2']=='cover'

def test_report_sidecar_names(tmp_path,cfg):
    md=fragment(tmp_path,'# 前言\n\n文字。');out=tmp_path/'result.docx'
    p=subprocess.run([sys.executable,str(ROOT/'scripts/bime_word.py'),'convert',str(md),'-o',str(out)],capture_output=True,text=True);assert p.returncode==0,p.stderr
    assert (tmp_path/'result.audit.json').exists();assert (tmp_path/'result.audit.md').exists();assert (tmp_path/'result.bime.json').exists()

def test_zip_traversal_rejected(tmp_path):
    z=tmp_path/'unsafe.docx'
    with zipfile.ZipFile(z,'w') as f:f.writestr('../x','bad');f.writestr('word/document.xml','bad')
    with pytest.raises(BimeError,match='Unsafe ZIP'):Package(z)

def test_thesis_front_pagination(tmp_path,cfg):
    md=fragment(tmp_path,'# 誌謝\n\n感謝。\n\n# 中文摘要\n\n摘要。\n\n關鍵詞：甲；乙；丙\n\n# Abstract\n\nAn abstract.\n\nKeywords: one; two; three\n\n# 前言\n\n正文。\n')
    out=tmp_path/'thesis.docx';convert(md,out,cfg,'thesis');r=audit(out,cfg,'thesis');assert not has(r,'PAGE_FORMAT','error');assert not has(r,'PAGE_POSITION','error')
    formats=Package(out).doc.xpath('.//w:sectPr/w:pgNumType/@w:fmt',namespaces=NS);assert formats==['lowerRoman','lowerRoman','lowerRoman','lowerRoman','decimal']

def test_fragment_cover_opt_in(tmp_path,cfg):
    md=fragment(tmp_path,'---\nbime:\n  title_en: An English Title\n  author_zh: 王小明\n  author_en: Hsiao-Ming Wang\n  advisor_zh: 李大華 博士\n  advisor_en: Ta-Hua Lee, Ph.D.\n  year_roc: 115\n  month: 10\n---\n\n# 計畫題目\n\n## 研究目的\n\n正文。\n')
    c=dict(cfg,cover=True,shift_heading_level=-1);out=tmp_path/'cover.docx';convert(md,out,c)
    p=Package(out);texts=[text(x) for x in p.body.iter(q('w:p'))]
    assert texts[:2]==['國立臺灣大學生物資源暨農學院生物機電工程學系','碩士論文'];assert '計畫題目' in texts and 'An English Title' in texts
    assert texts.count('計畫題目')==1;assert '中華民國115年10月October 2026' in texts
    sects=p.doc.xpath('.//w:sectPr',namespaces=NS);assert len(sects)==2
    assert not sects[0].xpath('w:footerReference',namespaces=NS);assert sects[1].xpath('w:pgNumType/@w:start',namespaces=NS)==['1']
    plain=tmp_path/'plain.docx';convert(md,plain,dict(cfg,shift_heading_level=-1));assert len(Package(plain).doc.xpath('.//w:sectPr',namespaces=NS))==1

def test_bookmark_ids_remapped(tmp_path,cfg):
    source=make(tmp_path,cfg);out=tmp_path/'result.docx';insert(source,fragment(tmp_path,'## 1.2 新小節\n\n文字。'),out,cfg)
    p=Package(out);ids=p.doc.xpath('.//w:bookmarkStart/@w:id',namespaces=NS);names=p.doc.xpath('.//w:bookmarkStart/@w:name',namespaces=NS)
    assert len(ids)==len(set(ids));assert len(names)==len(set(names))

def test_reference_manifest_uncited_detected(tmp_path,cfg):
    ref='Adams, A. 2020. Synthetic test entry. Not a real publication.'
    out=make(tmp_path,cfg,'# 前言\n\n沒有文獻引用。\n\n# 參考文獻\n\n'+ref+'\n')
    manifest=tmp_path/'refs.json';manifest.write_text(json.dumps({'entries':[{'id':'test','reference_text':ref,'citation_forms':['(Adams, 2020)'],'language':'en','sort_key':'Adams','year':2020}]}))
    cfg['reference_manifest']=str(manifest);assert has(audit(out,cfg),'REF_CITED','error')

def test_reference_manifest_cited_matches(tmp_path,cfg):
    ref='Adams, A. 2020. Synthetic test entry. Not a real publication.'
    out=make(tmp_path,cfg,'# 前言\n\n已引用 (Adams, 2020)。\n\n# 參考文獻\n\n'+ref+'\n')
    manifest=tmp_path/'refs.json';manifest.write_text(json.dumps({'entries':[{'id':'test','reference_text':ref,'citation_forms':['(Adams, 2020)'],'language':'en','sort_key':'Adams','year':2020}]}))
    cfg['reference_manifest']=str(manifest);assert not has(audit(out,cfg),'REF_CITED','error')

def test_list_of_figures_and_tables_fields(tmp_path,cfg):
    out=make(tmp_path,cfg,'# 前言\n\n{{LOF}}\n\n{{LOT}}\n')
    p=Package(out);fields=' '.join(p.doc.xpath('.//w:instrText/text()',namespaces=NS))
    assert 'Image Caption,1' in fields and 'Table Caption,1' in fields

def test_outputs_keep_schema_child_order(tmp_path,cfg):
    from bime.ooxml_order import order_errors
    img=tmp_path/'a.png';Image.new('RGB',(20,10)).save(img)
    out=make(tmp_path,cfg,'# 前言\n\n文字[^x]。\n\n![圖1-1 示意](a.png)\n\n表1-1 數據\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n[^x]: 註腳。\n')
    p=Package(out)
    for name,data in p.parts.items():
        if name.endswith('.xml'):assert order_errors(xml(data),name)==[],name
    revised=tmp_path/'revised.docx';insert(out,fragment(tmp_path,'## 1.1 新增\n\n新增文字。\n'),revised,cfg,mode='at_end')
    q2=Package(revised)
    for name,data in q2.parts.items():
        if name.endswith('.xml'):assert order_errors(xml(data),name)==[],name

def test_config_bad_role_type_refused(tmp_path):
    path=tmp_path/'bad.json';path.write_text('{"role_overrides":false}')
    with pytest.raises(BimeError,match='role_overrides'):load_config(path)
