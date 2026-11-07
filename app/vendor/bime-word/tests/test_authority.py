"""Behaviour added in 1.1.0: the regulation > friend template > CLAUDE.md precedence."""
from __future__ import annotations
import json,sys,copy
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

META='''---
bime:
  degree: master
  title_zh: 測試題目
  title_en: A Synthetic Test Title
  author_zh: 測試者
  author_en: Test Writer
  student_id: R00000000
  advisor_zh: 測試教授 博士
  advisor_en: Test Advisor, Ph.D.
  year_roc: 115
  month: 9
---

'''
THESIS=META+'''# 誌謝

感謝。

# 中文摘要

摘要內容。

關鍵詞：甲、乙、丙

# Abstract

Abstract text.

Keywords: one, two, three

# 前言

正文。

# 文獻探討

內容。

# 材料與方法

內容。

# 結果與討論

內容。

# 結論

內容。

# 參考文獻

Omega, A. 2000. A synthetic entry.
'''
# Synthetic items only, shaped like the regulation's 二.8 examples; they are not real publications.
REFS=[
 {'id':'alpha2001','type':'article-journal','author':[{'family':'Alpha','given':'Ann Beth'},{'family':'Beta','given':'C.'},{'family':'Gamma','given':'D. E.'}],'issued':{'date-parts':[[2001]]},'title':'A synthetic journal article','container-title':'Journal of Synthetic Tests','container-title-short':'J. Synth. Tests','volume':'3','issue':'2','page':'10–20'},
 {'id':'delta1999','type':'book','author':[{'family':'Delta','given':'F.'},{'family':'Epsilon','given':'G.'}],'issued':{'date-parts':[[1999]]},'title':'A Synthetic Book','edition':'2','publisher-place':'Taipei','publisher':'Test Press'},
 {'id':'lin2010','type':'article-journal','language':'zh-TW','author':[{'family':'林','given':'甲'},{'family':'張','given':'乙'}],'issued':{'date-parts':[[2010]]},'title':'合成測試文章','container-title':'測試學報','volume':'1','issue':'1','page':'1-9','bime-strokes':8},
 {'id':'chen2012','type':'article-journal','language':'zh-TW','author':[{'family':'陳','given':'丙'},{'family':'王','given':'丁'},{'family':'李','given':'戊'}],'issued':{'date-parts':[[2012]]},'title':'另一篇合成文章','container-title':'測試學報','volume':'2','issue':'1','page':'5-8','bime-strokes':16},
 {'id':'org2020','type':'webpage','author':[{'literal':'Test Org'}],'issued':{'date-parts':[[2020]]},'title':'A synthetic web page','publisher':'Test Org','URL':'https://example.org/page','accessed':{'date-parts':[[2026,9,28]]}},
 {'id':'repo2026','type':'software','author':[{'family':'Writer','given':'Test'}],'issued':{'date-parts':[[2026]]},'title':'SYNTHETIC-REPO','URL':'https://example.org/repo'},
 {'id':'never','type':'book','author':[{'family':'Omega'}],'issued':{'date-parts':[[2000]]},'title':'Never cited'},
]

@pytest.fixture
def cfg():return load_config()

def md(tmp,content,name='doc'):
    p=tmp/(name+'.md');p.write_text(content,encoding='utf-8');return p

def conv(tmp,cfg,content,name='doc',scope='fragment',**kw):
    out=tmp/(name+'.docx');convert(md(tmp,content,name),out,cfg,scope,**kw);return out

def has(report,rid,severity=None):return any(f['rule_id']==rid and (severity is None or f['severity']==severity) for f in report['findings'])
def texts(path,scope='thesis'):return [r for r in paragraph_records(Package(path),scope)]

def test_rules_carry_authority_and_rejections():
    cat=json.loads((ROOT/'references/rules.json').read_text(encoding='utf-8'))
    assert cat['authority_order'][:3]==['regulation','friend_template','author_claude_md']
    assert all(r['authority'] in cat['authority_order'] for r in cat['rules'])
    assert cat['sources']['friend_template']['sha256'].startswith('6ab7ee5a')
    assert any('頁尾距離' in x['item'] for x in cat['rejected'])
    assert any(x['source']=='author_claude_md' and 'DSR' in x['item'] for x in cat['rejected'])
    assert {r['id']:r for r in cat['rules']}['PAGE_ORIGIN']['decision']['resolved_by']=='friend_template'

def test_cover_title_and_signature_pages(tmp_path,cfg):
    out=conv(tmp_path,cfg,THESIS,scope='thesis')
    rs=texts(out);cover=[r for r in rs if r['region']=='cover'];sig=[r for r in rs if r['region']=='signature']
    assert cover[0]['text']=='國立臺灣大學生物資源暨農學院生物機電工程學系'
    assert any(r['text']=='中華民國115年9月September 2026' for r in cover)
    assert any(r['region']=='title' for r in rs)
    assert any('本論文係測試者君（R00000000）' in r['text'] for r in sig)
    assert not any(r['text']=='封面' for r in rs)
    p=Package(out);res=Resolver(p)
    size=lambda r:res.prop(r['element'],'sz',run=r['element'].find('.//'+q('w:r')))
    assert size(cover[0])=='36' and size(next(r for r in cover if r['text'].startswith('Department')))=='28'
    sects=p.doc.xpath('.//w:sectPr',namespaces=NS)
    fmts=[(s.find('w:pgNumType',NS).get(q('w:fmt')) if s.find('w:pgNumType',NS) is not None else None) for s in sects]
    assert fmts[:3]==[None,None,None] and fmts[3]=='lowerRoman' and fmts[-1]=='decimal'
    assert sects[3].find('w:pgNumType',NS).get(q('w:start'))=='1'
    r=audit(out,cfg,'thesis')
    assert r['summary']['error']==0
    assert not has(r,'CHAPTER_NAMES','warning') and not has(r,'STRUCTURE','warning') and not has(r,'COVER_CONTENT','warning')

def test_missing_metadata_writes_placeholders(tmp_path,cfg):
    out=conv(tmp_path,cfg,THESIS.split('---\n\n',1)[1],scope='thesis')
    assert any('[TODO: 論文中文題目]' in r['text'] for r in texts(out))
    assert has(audit(out,cfg,'thesis'),'SPECIAL_PAGES','warning')

def test_toc_title_stays_out_of_toc(tmp_path,cfg):
    out=conv(tmp_path,cfg,THESIS,scope='thesis');rs=texts(out)
    title=next(r for r in rs if r['text']=='目錄')
    assert title['style']=='BIMETOCTitle' and title['level'] is None
    assert any(r['text']=='頁數' for r in rs)

def test_english_chapter_labels(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# Introduction\n\nEnglish text.\n\n# Chapter 2 Related Work\n\nMore text.\n')
    heads=[r['text'] for r in texts(out,'fragment') if r['level']==1]
    assert heads==['Chapter 1 Introduction','Chapter 2 Related Work']

def test_document_language_sets_uniform_spacing(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n這是一段中文正文，說明研究背景與方法。\n\nThis English sentence sits in a Chinese thesis.\n')
    p=Package(out);res=Resolver(p)
    lines={res.prop(r['element'],'spacing','line',kind='pPr') for r in paragraph_records(p) if r['kind']=='body' and r['text']}
    assert lines=={'360'}

def test_captions_normalised(tmp_path,cfg):
    Image.new('RGB',(20,10)).save(tmp_path/'a.png')
    out=conv(tmp_path,cfg,'# 前言\n\n![圖 1-1　示意](a.png)\n\n**表 1-1　數據**\n\n| A | B |\n|---|---|\n| 1 | 2 |\n')
    caps=[r for r in texts(out,'fragment') if r['kind']=='caption' and r['text']]
    assert [c['text'] for c in caps]==['圖1-1\t示意','表1-1\t數據']
    assert [c['style'] for c in caps]==['ImageCaption','TableCaption']
    assert not Package(out).doc.xpath('.//w:p[w:pPr/w:pStyle/@w:val="TableCaption"]//w:rPr/w:b',namespaces=NS)
    assert not has(audit(out,cfg),'CAPTION_POSITION','error')

def refs_file(tmp):
    p=tmp/'refs.json';p.write_text(json.dumps(REFS,ensure_ascii=False),encoding='utf-8');return p

def test_citations_and_reference_list(tmp_path,cfg):
    body='# 前言\n\n見 [@alpha2001] 與 @delta1999，以及 [@lin2010; @chen2012]。Alpha et al. [-@alpha2001] 另見 [@org2020; @repo2026, commit `abc1234`]。\n\n# 參考文獻\n\n{{REFERENCES}}\n'
    out=tmp_path/'c.docx';result=convert(md(tmp_path,body,'c'),out,cfg,bibliography=refs_file(tmp_path))
    rs=texts(out,'fragment');para=next(r['text'] for r in rs if r['text'].startswith('見'))
    assert '(Alpha et al., 2001)' in para and 'Delta and Epsilon (1999)' in para
    assert '(林與張，2010；陳等人，2012)' in para and 'Alpha et al. (2001)' in para
    assert '(Test Org, 2020; Writer, 2026, commit abc1234)' in para
    refs=[r['text'] for r in rs if r['region']=='references' and not r['level']]
    assert refs[0].startswith('林甲、張乙。2010。') and refs[1].startswith('陳丙、王丁、李戊。2012。')
    assert refs[2]=='Alpha, A. B., C. Beta, and D. E. Gamma. 2001. A synthetic journal article. J. Synth. Tests 3(2): 10-20.'
    assert refs[3]=='Delta, F., and G. Epsilon. 1999. A Synthetic Book. 2nd ed. Taipei: Test Press.'
    assert refs[4]=='Test Org. 2020. A synthetic web page. Test Org. Available at: https://example.org/page. Accessed 28 September 2026.'
    assert refs[5]=='Writer, T. 2026. SYNTHETIC-REPO. Available at: https://example.org/repo.'
    assert 'never' in result['references']['uncited'] and len(refs)==6

def test_references_placeholder_without_citations(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n沒有引用。\n\n# 參考文獻\n\n{{REFERENCES}}\n')
    assert not any('{{REFERENCES}}' in r['text'] for r in texts(out,'fragment'))

def test_unknown_citation_key_stops(tmp_path,cfg):
    with pytest.raises(BimeError,match='not found'):
        convert(md(tmp_path,'文字 [@missing]。\n'),tmp_path/'x.docx',cfg,bibliography=refs_file(tmp_path))

def test_bibtex_bibliography(tmp_path,cfg):
    # Braces keep capitals: pandoc stores BibTeX titles in sentence case otherwise.
    bib=tmp_path/'r.bib';bib.write_text('@book{zeta2005, author={Zeta, H.}, title={{Synthetic Bib Book}}, year={2005}, publisher={Test Press}, address={Taipei}}\n',encoding='utf-8')
    out=tmp_path/'b.docx';convert(md(tmp_path,'文字 [@zeta2005]。\n\n{{REFERENCES}}\n','b'),out,cfg,bibliography=bib)
    assert any(r['text']=='Zeta, H. 2005. Synthetic Bib Book. Taipei: Test Press.' for r in texts(out,'fragment'))

def test_references_section_with_manual_content_refused(tmp_path,cfg):
    with pytest.raises(BimeError,match='REFERENCES'):
        convert(md(tmp_path,'文字 [@alpha2001]。\n\n# 參考文獻\n\n手寫條目。\n'),tmp_path/'m.docx',cfg,'thesis',bibliography=refs_file(tmp_path))

def test_automatic_color_counts_as_black(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n中文內容。\n')
    p=Package(out)
    for c in p.doc.xpath('.//w:color',namespaces=NS):c.getparent().remove(c)
    styles=p.getxml('word/styles.xml')
    for c in styles.xpath('.//w:color',namespaces=NS):c.getparent().remove(c)
    p.setxml('word/styles.xml',styles);bad=tmp_path/'auto.docx';p.save(bad)
    r=audit(bad,cfg);assert not has(r,'TEXT_COLOR','unknown') and not has(r,'TEXT_COLOR','error');assert r['metrics']['automatic_color_runs']>0

def test_findings_are_merged(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n第一段。\n\n第二段。\n\n第三段。\n')
    p=Package(out)
    for sz in p.doc.xpath('.//w:p[w:pPr/w:pStyle/@w:val!="Heading1"]//w:r/w:rPr/w:sz',namespaces=NS):sz.set(q('w:val'),'22')
    bad=tmp_path/'small.docx';p.save(bad)
    items=[f for f in audit(bad,cfg)['findings'] if f['rule_id']=='FONT_SIZE']
    assert len(items)==1 and items[0]['count']==3

def test_tall_footer_enlarges_bottom_margin(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n中文內容。\n')
    p=Package(out);p.body.find('w:sectPr/w:pgMar',NS).set(q('w:footer'),'992')
    footer=p.getxml('word/bimeFooter.xml');footer.append(copy.deepcopy(footer.find(q('w:p'))));p.setxml('word/bimeFooter.xml',footer)
    bad=tmp_path/'tall.docx';p.save(bad)
    hit=[f for f in audit(bad,cfg)['findings'] if f['rule_id']=='MARGINS' and f['severity']=='error']
    assert hit and hit[0]['actual']['estimated_effective_cm']>2.5
    assert not [f for f in audit(out,cfg)['findings'] if f['rule_id']=='MARGINS' and f['severity'] in ('error','warning')]

def test_front_matter_spacing_checked(tmp_path,cfg):
    out=conv(tmp_path,cfg,THESIS,scope='thesis')
    p=Package(out)
    rec=next(r for r in paragraph_records(p,'thesis') if r['region']=='acknowledgements' and r['kind']=='body' and r['text'])
    rec['element'].find('w:pPr/w:spacing',NS).set(q('w:line'),'278')
    bad=tmp_path/'front.docx';p.save(bad)
    assert has(audit(bad,cfg,'thesis'),'LINE_SPACING','warning')

def numbered_template(tmp,cfg):
    """A document numbered the way the friend template is: headings and captions by list levels."""
    Image.new('RGB',(20,10)).save(tmp/'a.png')
    out=conv(tmp,cfg,'# 前言\n\n文字。\n\n## 1.1 背景\n\n文字。\n\n![圖1-1 示意](a.png)\n\n# 文獻探討\n\n文字。\n\n# 參考文獻\n\n條目。\n',name='numbered')
    p=Package(out)
    for t in p.doc.xpath('.//w:t',namespaces=NS):
        for prefix in ('第一章　','第二章　','1.1 ','圖1-1'):
            if t.text and t.text.startswith(prefix):t.text=t.text[len(prefix):]
    for tab in p.doc.xpath('.//w:p[w:pPr/w:pStyle/@w:val="ImageCaption"]//w:tab',namespaces=NS):tab.getparent().remove(tab)
    W_=W
    numbering=E.fromstring(f'''<w:numbering xmlns:w="{W_}"><w:abstractNum w:abstractNumId="0">
      <w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="taiwaneseCountingThousand"/><w:pStyle w:val="Heading1"/><w:lvlText w:val="第%1章"/></w:lvl>
      <w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:pStyle w:val="Heading2"/><w:isLgl/><w:lvlText w:val="%1.%2"/></w:lvl>
      <w:lvl w:ilvl="3"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlRestart w:val="1"/><w:pStyle w:val="ImageCaption"/><w:isLgl/><w:lvlText w:val="圖%1-%4"/></w:lvl>
      </w:abstractNum><w:num w:numId="7"><w:abstractNumId w:val="0"/></w:num></w:numbering>''')
    p.setxml('word/numbering.xml',numbering)
    types=p.getxml('[Content_Types].xml')
    if not any(n.get('PartName')=='/word/numbering.xml' for n in types):
        n=E.SubElement(types,'{'+CT+'}Override');n.set('PartName','/word/numbering.xml');n.set('ContentType','application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml');p.setxml('[Content_Types].xml',types)
    rels=p.getxml('word/_rels/document.xml.rels')
    if not any(r.get('Type','').endswith('/numbering') for r in rels):
        n=E.SubElement(rels,'{'+REL+'}Relationship');n.set('Id','rIdNum7');n.set('Type',R+'/numbering');n.set('Target','numbering.xml');p.setxml('word/_rels/document.xml.rels',rels)
    styles=p.getxml('word/styles.xml')
    for sid,ilvl in (('Heading1','0'),('Heading2','1'),('ImageCaption','3')):
        st=styles.find(f'w:style[@w:styleId="{sid}"]',NS);pp=child(st,'w:pPr');num=child(pp,'w:numPr')
        child(num,'w:ilvl').set(q('w:val'),ilvl);child(num,'w:numId').set(q('w:val'),'7')
    p.setxml('word/styles.xml',styles)
    dest=tmp/'template.docx';p.save(dest);return dest

def test_list_numbering_is_rendered(tmp_path,cfg):
    doc=numbered_template(tmp_path,cfg)
    shown=[r['display'] for r in paragraph_records(Package(doc),'thesis') if r['level'] or (r['kind']=='caption' and r['display'])]
    assert shown[:4]==['第一章\t前言','1.1\t背景','圖1-1\t示意','第二章\t文獻探討']
    r=audit(doc,cfg,'thesis')
    assert not has(r,'CAPTION_POSITION','error') and not has(r,'HEADING_NUMBER','warning')
    assert has(r,'BACKMATTER_UNNUMBERED','warning')

def test_stray_numbered_heading(tmp_path,cfg):
    doc=numbered_template(tmp_path,cfg);p=Package(doc)
    empty=E.fromstring(f'<w:p xmlns:w="{W}"><w:pPr><w:pStyle w:val="Heading2"/></w:pPr></w:p>')
    first=next(r for r in paragraph_records(p) if r['text']=='背景')['element'];first.addnext(empty)
    bad=tmp_path/'stray.docx';p.save(bad)
    assert has(audit(bad,cfg),'HEADING_NUMBER','warning')

def test_insert_follows_recipient_numbering(tmp_path,cfg):
    doc=numbered_template(tmp_path,cfg);out=tmp_path/'ins.docx'
    insert(doc,md(tmp_path,'## 1.2 新增\n\n新增文字。\n','add'),out,cfg,mode='under',anchor='前言')
    heads=[(r['display'],r['style']) for r in paragraph_records(Package(out)) if r['level']==2]
    assert ('1.2\t新增','Heading2') in heads
    with pytest.raises(BimeError,match='would show'):
        insert(doc,md(tmp_path,'## 1.5 錯號\n\n文字。\n','bad'),tmp_path/'no.docx',cfg,mode='under',anchor='前言')
    assert not (tmp_path/'no.docx').exists()

def test_dsr_chapter_names_are_flagged(tmp_path,cfg):
    out=conv(tmp_path,cfg,META+'# 誌謝\n\n感謝。\n\n# 緒論\n\n內容。\n\n# 系統設計與實作\n\n內容。\n',scope='thesis')
    assert has(audit(out,cfg,'thesis'),'CHAPTER_NAMES','warning')

def test_numerals_above_ten(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n共有十二位受試者，分成三組，這十分重要，於十一月二十日完成。\n')
    items=[f for f in audit(out,cfg)['findings'] if f['rule_id']=='NUMERAL' and f['severity']=='warning']
    assert len(items)==1 and items[0]['actual']=='十二'

def test_citation_punctuation(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n如文獻所述 (Smith，2020)，以及 (陳等人, 1989) 與 (Wang & Lin, 1992)。\n')
    msgs={f['message'] for f in audit(out,cfg)['findings'] if f['rule_id']=='CITATION_FORM' and f['severity']=='warning'}
    assert len(msgs)==3

def test_reference_language_order(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n內容。\n\n# 參考文獻\n\nZeta, A. 2001. Title. J. 1: 1-2.\n\n陳甲。2000。題目。學報 1: 1-2。\n\nAlpha, B. 2002. Title. J. 1: 1-2.\n')
    assert has(audit(out,cfg),'REF_ORDER','error')

def test_abstract_length_per_language(tmp_path,cfg):
    long='這是摘要的內容。'*80
    words=' '.join(['word']*600)
    doc=THESIS.replace('摘要內容。',long).replace('Abstract text.',words)
    out=conv(tmp_path,cfg,doc,scope='thesis')
    assert not has(audit(out,cfg,'thesis'),'ABSTRACT_LENGTH','warning')

def test_front_heading_region_ends_at_same_level(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 計畫\n\n## 目錄\n\n清單。\n\n## 研究目的\n\n正文。\n')
    rec=next(r for r in texts(out,'fragment') if r['text']=='正文。')
    assert rec['region']=='body'

def test_title_heading_shift(tmp_path):
    path=tmp_path/'p.json';path.write_text('{"shift_heading_level": -1}');cfg=load_config(path)
    out=conv(tmp_path,cfg,'# 計畫書題目\n\n## 研究目的\n\n正文。\n\n### 背景\n\n文字。\n')
    rs=texts(out,'fragment');heads=[(r['level'],r['text']) for r in rs if r['level']]
    assert heads==[(1,'第一章\u3000研究目的'),(2,'1.1 背景')]
    first=next(r for r in rs if r['text'])
    assert first['text']=='計畫書題目' and first['style']=='BIMEDocTitle'

def test_truncated_authors_series_and_url_fallbacks(tmp_path,cfg):
    items=[{'id':'many2024','type':'article-journal','author':[{'family':'One','given':'A.'},{'family':'Two','given':'B.'},{'family':'Three','given':'C.'},{'literal':'et al.'}],'issued':{'date-parts':[[2024]]},'title':'Truncated list','container-title':'Synthetic J.','container-title-short':'Synth. J.','URL':'https://example.org/tmlr'},
           {'id':'lncs2016','type':'paper-conference','author':[{'family':'Four','given':'D.'}],'issued':{'date-parts':[[2016]]},'title':'Series paper','container-title':'Advances in Synthetic Retrieval','collection-title':'Lecture Notes in Synthetic Science','page':'1-7','publisher-place':'Cham','publisher':'Test Press'},
           {'id':'conf2023','type':'paper-conference','author':[{'family':'Five','given':'E.'}],'issued':{'date-parts':[[2023]]},'title':'Pageless paper','container-title':'The First Synthetic Conference','URL':'https://example.org/forum'}]
    bib=tmp_path/'b.json';bib.write_text(json.dumps(items),encoding='utf-8')
    out=tmp_path/'t.docx';convert(md(tmp_path,'見 [@many2024; @lncs2016; @conf2023]。\n\n{{REFERENCES}}\n','t'),out,cfg,bibliography=bib)
    rs=[r['text'] for r in texts(out,'fragment')]
    assert '見 (One et al., 2024; Four, 2016; Five, 2023)。' in rs
    assert 'Five, E. 2023. Pageless paper. In “The First Synthetic Conference”. Available at: https://example.org/forum.' in rs
    assert 'Four, D. 2016. Series paper. In “Advances in Synthetic Retrieval” (Lecture Notes in Synthetic Science), 1-7. Cham: Test Press.' in rs
    assert 'One, A., B. Two, C. Three, et al. 2024. Truncated list. Synth. J. Available at: https://example.org/tmlr.' in rs

def test_tables_have_grid_borders_and_are_centred(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 前言\n\n**表 1-1　數據**\n\n| A | B |\n|---|---|\n| 1 | 2 |\n')
    p=Package(out);tbl=p.body.find(q('w:tbl'))
    assert tbl.find('w:tblPr/w:jc',NS).get(q('w:val'))=='center'
    sid=tbl.find('w:tblPr/w:tblStyle',NS).get(q('w:val'))
    style=p.getxml('word/styles.xml').find(f'w:style[@w:styleId="{sid}"]',NS)
    sides={E.QName(b).localname for b in style.find('w:tblPr/w:tblBorders',NS)}
    assert sides=={'top','left','bottom','right','insideH','insideV'}

def test_todo_placeholders_are_dropped(tmp_path,cfg):
    bib=tmp_path/'r.json';bib.write_text(json.dumps(REFS),encoding='utf-8')
    src=md(tmp_path,'# 前言\n\n正文一句。[TODO: 待補 [@alpha2001] 的說明。]\n\n[TODO: 整段待辦。]\n\n- 步驟：[TODO: 待訂。]\n\n另見 [@delta1999]。\n\n{{REFERENCES}}\n','t')
    out=tmp_path/'t.docx';result=convert(src,out,cfg,bibliography=bib)
    rs=[r['text'] for r in texts(out,'fragment') if r['text']]
    assert not any('TODO' in t for t in rs) and '正文一句。' in rs
    assert 'alpha2001' in result['references']['uncited']
    kinds={d['type'] for d in result['decisions']}
    assert 'todo_dropped' in kinds and 'todo_dangling' in kinds
    path=tmp_path/'keep.json';path.write_text('{"drop_todo": false}')
    out2=tmp_path/'k.docx';convert(src,out2,load_config(path),bibliography=bib)
    assert any('TODO' in r['text'] for r in texts(out2,'fragment'))

def test_toc_entries_link_to_headings(tmp_path,cfg):
    out=conv(tmp_path,cfg,'# 目錄\n\n{{TOC}}\n\n# 前言\n\n文字。\n\n## 背景\n\n文字。\n\n# 結論\n\n文字。\n')
    p=Package(out)
    links=p.doc.xpath('.//w:hyperlink[starts-with(@w:anchor,"_TocBIME")]',namespaces=NS)
    assert [text(l).replace('\t','') for l in links]==['第一章\u3000前言','1.1 背景','第二章\u3000結論']
    marks={b.get(q('w:name')) for b in p.doc.iter(q('w:bookmarkStart'))}
    assert all(l.get(q('w:anchor')) in marks for l in links)
    instr=' '.join(p.doc.xpath('.//w:instrText/text()',namespaces=NS))
    assert 'TOC \\o "1-3" \\h' in instr and instr.count('PAGEREF _TocBIME')==3
    styles=[l.getparent().find('w:pPr/w:pStyle',NS).get(q('w:val')) for l in links]
    assert styles==['toc1','toc2','toc1']

def test_footer_distance_guard(tmp_path):
    path=tmp_path/'p.json';path.write_text('{"footer_distance_cm": 2.5}')
    with pytest.raises(BimeError,match='footer_distance_cm'):load_config(path)
