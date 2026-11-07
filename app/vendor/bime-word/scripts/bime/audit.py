"""Read-only, evidence-oriented OOXML audit. No document mutation or rendering claims.

Severities follow the source's strength: an explicit regulation breach is an error,
a principle or example deviation a warning. Decisions taken from the friend template
or CLAUDE.md say so in the finding, and are never reported as department rules.
"""
from __future__ import annotations
import json,math,re,posixpath
from pathlib import Path
from .common import *
from .convert import parse_chapter

CAT=json.loads((ROOT/'references/rules.json').read_text(encoding='utf-8'))
RULES={x['id']:x for x in CAT['rules']}
FONT_ALIASES={'dfkai-sb','標楷體','标楷体','mingliu','細明體','细明体','biaukai','標楷體-繁','kaiti tc'}
KEYWORDS=re.compile(r'^\s*(關鍵[詞字]|关键词|Key\s*words?)\s*[:：]',re.I)
LOCATIONS_KEPT=8

class Findings:
    def __init__(self):
        self.items=[];self.index={};self.checks={r:{'tested':0,'status':'manual'} for r in RULES}
    def tested(self,r,n=1): self.checks[r]['tested']+=n
    def add(self,r,severity,message,location='document',actual=None,expected=None,excerpt=None):
        # Identical findings (same rule, severity, message, expectation) are reported once with a count.
        key=(r,severity,message,json.dumps(expected,ensure_ascii=False,sort_keys=True,default=str))
        if key in self.index:
            item=self.index[key];item['count']+=1
            if location not in item['locations'] and len(item['locations'])<LOCATIONS_KEPT:item['locations'].append(location)
            return
        rule=RULES[r]
        item={'rule_id':r,'severity':severity,'location':location,'locations':[location],'count':1,'message':message,'actual':actual,'expected':expected,'excerpt':excerpt,
              'source':{'authority':rule.get('authority','regulation'),'section':rule['source_section'],'paragraph_1based':rule['source_paragraph_1based'],'quote':rule['quote'],'strength':rule['strength']}}
        if rule.get('decision'):item['decision']=rule['decision']
        self.items.append(item);self.index[key]=item
    def finalize(self,applicable):
        for rid,c in self.checks.items():
            xs=[i['severity'] for i in self.items if i['rule_id']==rid]
            if rid not in applicable:c['status']='not_applicable_to_selected_scope'
            elif 'error' in xs:c['status']='fail'
            elif 'conflict' in xs:c['status']='source_conflict'
            elif 'warning' in xs:c['status']='warning'
            elif 'unknown' in xs:c['status']='partially_unknown' if c['tested'] else 'unknown'
            elif 'manual' in xs or RULES[rid]['checkability'] in ('manual','mixed','heuristic'):
                c['status']='machine_checked_with_manual_review' if c['tested'] else 'manual'
            else:c['status']='machine_pass' if c['tested'] else 'not_checked'
        return self.checks

def loc(rec):
    return f"word/document.xml / body[{rec['body_index']}] / paragraph[{rec['paragraph_index']}]"

def _section_data(pkg,records):
    sections=[];start=1
    for i,b in enumerate(pkg.body,1):
        s=b if b.tag==q('w:sectPr') else b.find('w:pPr/w:sectPr',NS) if b.tag==q('w:p') else None
        if s is not None:
            rs=[r for r in records if start<=r['body_index']<=i]
            sections.append({'index':len(sections)+1,'start':start,'end':i,'element':s,'regions':sorted({r['region'] for r in rs}),'records':rs});start=i+1
    return sections

def _true(node):
    return node is not None and node.get(q('w:val'),'1') not in ('0','false','off')

def twips_cm(v): return round(int(v)*2.54/1440,2)

def para_height_pt(res,p,grid_pitch):
    """Estimated rendered height of one paragraph (points); Word's metrics differ slightly by font."""
    size=0.0
    for r in p.xpath('.//w:r',namespaces=NS):
        sz=res.prop(p,'sz',run=r)
        if sz and sz.isdigit(): size=max(size,int(sz)/2)
    if not size:
        mark=p.find('w:pPr/w:rPr/w:sz',NS)
        sz=mark.get(q('w:val')) if mark is not None else res.prop(p,'sz')
        size=int(sz)/2 if sz and sz.isdigit() else 10.0
    line=res.prop(p,'spacing','line',kind='pPr');rule=res.prop(p,'spacing','lineRule',kind='pPr') or 'auto'
    natural=size*1.15
    snap=res.prop(p,'snapToGrid',kind='pPr')
    if grid_pitch and snap not in ('0','false','off'):
        natural=math.ceil(natural/grid_pitch-1e-9)*grid_pitch
    if line is None or not line.lstrip('-').isdigit():height=natural
    elif rule=='exact':height=int(line)/20
    elif rule=='atLeast':height=max(int(line)/20,natural)
    else:height=natural*int(line)/240
    before=res.prop(p,'spacing','before',kind='pPr');after=res.prop(p,'spacing','after',kind='pPr')
    extra=sum(int(x)/20 for x in (before,after) if x and x.isdigit())
    return height+extra

def zh_value(s):
    digits={c:i for i,c in enumerate('零一二三四五六七八九')};digits['兩']=2
    total=0;cur=0
    for ch in s:
        if ch in digits:cur=digits[ch]
        elif ch in '十百千':
            unit={'十':10,'百':100,'千':1000}[ch];total+=(cur or 1)*unit;cur=0
        else:return None
    return total+cur

NUMERAL=re.compile(r'(?<![第每])([一二兩三四五六七八九十百千]{2,}|十)(?=(?:[個位名次種項篇件組份條台臺天週年月日倍%％]|小時|分鐘|秒|公[尺斤分克升里頃]|平方|立方))')
NUMERAL_IDIOMS=('十分','百分之百','千萬','十足','百年','千年','一百年')

def audit(source:Path,cfg,scope='fragment'):
    pkg=Package(source);original_hash=sha(source);f=Findings();res=Resolver(pkg)
    records=paragraph_records(pkg,scope)
    for r in records:
        override=cfg['role_overrides'].get(str(r['paragraph_index']))
        if override:r['region']=override
    if scope=='thesis':_detect_special_pages(records)
    applicable=set(RULES); metrics={'paragraphs':len(records),'body_runs_checked':0,'automatic_color_runs':0,'abstracts':{},'sections':[]}
    regions={r['region'] for r in records}
    has_abs=bool(regions&{'abstract_zh','abstract_en'})
    if not has_abs: applicable-= {'ABSTRACT_LENGTH','ABSTRACT_CONTENT','ABSTRACT_LIST','KEYWORDS'}
    if scope!='thesis': applicable-= {'STRUCTURE','SPECIAL_PAGES','PAGE_ORIGIN','CHAPTER_NAMES','BACKMATTER_UNNUMBERED','TOC_CONTENT','COVER_CONTENT','SIGNATURE_CONTENT','AUTHOR_THESIS_PARTS'}
    if 'references' not in regions: applicable-= {'REF_CITED','REF_ORDER','REF_TYPES','JOURNAL_ABBREVIATION'}
    tables=pkg.body.findall(q('w:tbl')); images=pkg.doc.xpath('.//w:drawing | .//w:pict',namespaces=NS)
    if not images: applicable-={'PHOTO_ORIGIN','IMAGE_SCALE'}
    if not tables and not images: applicable-={'CAPTION_POSITION','CAPTION_COMPLETE','CAPTION_NUMBER'}
    applicable-={'HOUSE_TYPOGRAPHY','HOUSE_CAPTION','CITATION_KEYS'}
    # WRITING_LANGUAGE: one language decides the line spacing of all prose (三.1, friend template).
    prose_regions={'body','acknowledgements','abstract_zh','abstract_en','symbols','appendix'}
    if cfg['language'] in ('zh','en'):lang=cfg['language'];how='profile'
    else:
        lang=document_language([r['text'] for r in records if r['region']=='body' and r['kind']=='body']);how='detected'
    metrics['language']={'value':lang,'source':how}
    expected_line='360' if lang=='zh' else '480'
    f.add('LINE_SPACING','manual',f'Whole-document writing language is {lang} ({how}); every prose paragraph, including acknowledgements and abstracts, is checked against {"1.5" if lang=="zh" else "double"} spacing (decision taken from the friend template).')
    for rec in records:
        if rec['kind']!='body' or rec['region'] not in prose_regions or not rec['text']:continue
        if rec['element'].xpath('ancestor::w:tbl',namespaces=NS):continue
        p=rec['element'];location=loc(rec);t=rec['text']
        if rec['in_sdt']:
            f.add('FONT_SIZE','manual','Content control paragraph: role and rendering require review.',location,excerpt=t[:140])
        actual_line=res.prop(p,'spacing','line',kind='pPr'); line_rule=res.prop(p,'spacing','lineRule',kind='pPr') or 'auto'
        if actual_line is None:actual_line='240'  # OOXML default: single spacing
        f.tested('LINE_SPACING')
        if actual_line!=expected_line or line_rule!='auto':
            region='front matter prose' if rec['region'] in FRONT else 'body text'
            f.add('LINE_SPACING','warning',f'Line spacing of {region} differs from the {"1.5" if lang=="zh" else "double"} spacing for a {lang} thesis; fixed 18 pt is not 1.5-line spacing.',location,actual={'line':actual_line,'rule':line_rule,'multiple':round(int(actual_line)/240,2) if line_rule=='auto' and actual_line.lstrip('-').isdigit() else None},expected={'line':expected_line,'rule':'auto'},excerpt=t[:140])
        for j,run in enumerate(p.xpath('.//w:r[not(ancestor::w:del)]',namespaces=NS),1):
            rt=text(run)
            if not rt.strip():continue
            if run.xpath('./w:footnoteReference | ./w:endnoteReference',namespaces=NS):continue
            metrics['body_runs_checked']+=1;rloc=location+f'/run[{j}]'
            for rid in ('FONT_SIZE','TEXT_COLOR'):f.tested(rid)
            size=res.prop(p,'sz',run=run)
            if size is None:f.add('FONT_SIZE','unknown','Effective font size could not be resolved.',rloc,excerpt=rt[:90])
            elif size!='24':f.add('FONT_SIZE','warning','Body font differs from the source’s 12pt principle.',rloc,actual=float(size)/2,expected=12,excerpt=rt[:90])
            color=res.color(p,run)
            if color=='AUTO':metrics['automatic_color_runs']+=1
            elif color is None:f.add('TEXT_COLOR','unknown','Theme color with tint/shade cannot be certified black from this run.',rloc,excerpt=rt[:90])
            elif color!='000000':f.add('TEXT_COLOR','error','Body text is not black.',rloc,actual=color,expected='000000',excerpt=rt[:90])
            for script,rid,used in [('cjk','FONT_ZH',bool(CJK.search(rt))),('latin','FONT_EN',bool(LATIN.search(rt)))]:
                if not used:continue
                f.tested(rid);font=res.font(p,run,script)
                good=font and (font.casefold() in FONT_ALIASES if script=='cjk' else font.casefold()=='times new roman')
                if not font:f.add(rid,'unknown','Effective typeface could not be resolved.',rloc,excerpt=rt[:90])
                elif not good:f.add(rid,'warning','Typeface differs from the source’s stated principle; installed-font substitution is a separate check.',rloc,actual=font,expected='細明體 / 標楷體為主' if script=='cjk' else 'Times New Roman',excerpt=rt[:90])
    if metrics['automatic_color_runs']:
        f.add('TEXT_COLOR','manual',f'{metrics["automatic_color_runs"]} run(s) use Word\'s automatic color, which prints black on white paper; they are counted as black.')
    _audit_pages(pkg,res,records,cfg,scope,f,metrics)
    if scope=='thesis':_audit_structure(pkg,records,regions,images,tables,cfg,f)
    _audit_headings(records,f)
    _audit_captions(pkg,records,scope,f)
    _audit_abstracts(records,f,metrics)
    _audit_text_conventions(records,f)
    # Citation/bibliography matching is exact only with an explicit, verified manifest.
    if cfg['reference_manifest']:
        manifest_path=Path(cfg['reference_manifest'])
        manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        _audit_references(records,manifest,f)
    else:
        f.add('CITATION_FORM','manual','Review author-year syntax, and two versus three-or-more authors. Citation keys and author counts cannot be proven from typography alone.')
        if 'references' in regions:
            f.add('REF_CITED','manual','No verified reference manifest supplied. Exact two-way citation matching is not claimed.')
    if 'references' in regions:
        _audit_reference_order(records,f)
        f.add('REF_TYPES','manual','Apply the nine source-specific reference examples; do not substitute APA/IEEE or infer missing bibliographic facts.')
        f.add('JOURNAL_ABBREVIATION','manual','Check recognized journal abbreviations against supplied verified information; full ISO4/ASAE tables are not in this attachment.')
    for rid,msg in [('SI_UNITS','Check SI primacy, optional parenthetical non-SI units, and dimensions semantically.'),('TERMINOLOGY','Common symbols need no translation; judge terminology in context.'),('PUNCTUATION','Review punctuation in prose; tables, equations, and headings have different roles.')]:
        f.add(rid,'manual',msg)
    if pkg.doc.xpath('.//w:txbxContent | .//wp:anchor | .//w:altChunk',namespaces=NS):
        f.add('MARGINS','manual','Text boxes, floating objects, or embedded altChunk content need separate rendering/content review.')
    if pkg.doc.xpath('.//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo',namespaces=NS):
        f.add('STRUCTURE','manual','Tracked changes exist; visible inserted text was read but final accepted-document conformance is not certified.')
        applicable.add('STRUCTURE')
    todo=[r for r in records if '[TODO' in r['text']]
    if todo:
        f.add('SPECIAL_PAGES' if scope=='thesis' else 'STRUCTURE','warning',f'{len(todo)} paragraph(s) still contain [TODO] placeholders.',loc(todo[0]),excerpt=todo[0]['text'][:100])
        if scope!='thesis':applicable.add('STRUCTURE')
    if sha(source)!=original_hash:raise BimeError('Source file changed during audit; discard this report and retry.')
    summary={s:sum(i['severity']==s for i in f.items) for s in ('error','warning','conflict','unknown','manual')}
    status='violations_found' if summary['error'] else 'deviations_or_review_required' if summary['warning'] else 'machine_checks_passed_review_required'
    return {'schema_version':2,'operation':'audit','source':str(source),'source_sha256':original_hash,'source_rule_sha256':CAT['sources']['regulation']['sha256'],'authority_order':CAT['authority_order'],'scope':scope,'overall':status,'summary':summary,'layout_verified':False,'policy':cfg,'metrics':metrics,'coverage':f.finalize(applicable),'findings':f.items,'limitations':['No full Word layout engine was run; XML indices are not page numbers.','Header/footer heights are estimated from font size and spacing, not measured.','Actual font installation/substitution and visual clipping require render-and-inspect.','Conditional table styles, complex scripts, shapes, and all possible fields are not exhaustively resolved.','Only regulation rules are institutional requirements; friend-template and CLAUDE.md decisions fill gaps and are labelled by authority.']}

def _detect_special_pages(records):
    """Cover and title page have no heading: recognise the regulation-sample lines in unlabelled front text."""
    prefix=[]
    for r in records:
        if r['level']==1 or r['region'] not in ('body','cover','title'):break
        prefix.append(r)
    starts=[i for i,r in enumerate(prefix) if r['region']=='body' and '國立臺灣大學' in r['text'] and ('學院' in r['text'] or '學系' in r['text'])]
    for n,i in enumerate(starts[:2]):
        stop=starts[n+1] if n+1<len(starts) else len(prefix)
        for r in prefix[i:stop]:
            if r['region']=='body':
                r['region']='cover' if n==0 else 'title'
                if r['kind']=='body':r['kind']='special'

def _active_footers(pkg,s,inherited,evenodd,kind='footer'):
    rels=pkg.getxml('word/_rels/document.xml.rels')
    relmap={} if rels is None else {r.get('Id'):r.get('Target') for r in rels if r.get('TargetMode')!='External'}
    tag='w:footerReference' if kind=='footer' else 'w:headerReference'
    for ref in s.findall(q(tag)):
        inherited[ref.get(q('w:type'),'default')]=ref.get(q('r:id'))
    active=['default']+(['even'] if evenodd else [])+(['first'] if _true(s.find(q('w:titlePg'))) else [])
    out=[]
    for typ in active:
        rid=inherited.get(typ);target=relmap.get(rid)
        out.append((typ,pkg.getxml(posixpath.normpath(posixpath.join('word',target))) if target else None))
    return out

def _audit_pages(pkg,res,records,cfg,scope,f,metrics):
    sections=_section_data(pkg,records)
    settings=pkg.getxml('word/settings.xml');evenodd=_true(settings.find(q('w:evenAndOddHeaders'))) if settings is not None else False
    footers={};headers={};first_body=True;front_started=False
    for sec in sections:
        s=sec['element'];idx=sec['index'];location=f'word/document.xml / section[{idx}]';sr=cfg['section_roles'].get(str(idx))
        reg=set(sec['regions']);is_body=sr=='body' or sr is None and bool(reg-FRONT)
        is_front=sr=='front' or sr is None and bool(reg & (FRONT-{'cover','title','signature'}))
        is_pre=sr=='pre' or not(is_body or is_front)
        size=s.find(q('w:pgSz'));mar=s.find(q('w:pgMar'))
        actual_size=None if size is None else {k:size.get(q('w:'+k)) for k in ('w','h')}
        metrics['sections'].append({'index':idx,'regions':sec['regions'],'body_range':[sec['start'],sec['end']],'size_twips':actual_size})
        f.tested('PAGE_SIZE')
        if size is None:f.add('PAGE_SIZE','unknown','Page size is not explicit.',location)
        else:
            try: good=abs(int(size.get(q('w:w')))-11906)<=3 and abs(int(size.get(q('w:h')))-16838)<=3
            except (TypeError,ValueError):good=False
            if not good:f.add('PAGE_SIZE','warning','Page is not portrait A4 under the default profile; landscape requires explicit review.',location,actual=actual_size,expected={'w':11906,'h':16838})
        # MARGINS apply to every section, front matter included (decision taken from the friend template).
        for k,want in {'top':1701,'bottom':1134,'left':1701,'right':1701}.items():
            f.tested('MARGINS');val=mar.get(q('w:'+k)) if mar is not None else None
            if val is None:f.add('MARGINS','unknown',f'{k} margin is not explicit.',location)
            elif abs(int(val)-want)>3:f.add('MARGINS','error',f'{k} margin differs from the source.',location,actual={'twips':int(val),'cm':twips_cm(val)},expected={'twips':want,'cm':2 if k=='bottom' else 3})
        gutter=mar.get(q('w:gutter'),'0') if mar is not None else '0'
        if gutter!='0':f.add('MARGINS','manual','Nonzero gutter changes physical whitespace; check rendered margins.',location,actual=gutter)
        grid=s.find(q('w:docGrid'));pitch=None
        if grid is not None and grid.get(q('w:type')) in ('lines','linesAndChars','snapToChars'):
            lp=grid.get(q('w:linePitch'));pitch=int(lp)/20 if lp and lp.isdigit() else None
        foot=_active_footers(pkg,s,footers,evenodd,'footer');head=_active_footers(pkg,s,headers,evenodd,'header')
        # A header or footer taller than its margin pushes the text area inward (二.5 本文留白).
        if mar is not None:
            for kind,parts,dist_key,margin_key,want_cm in (('footer',foot,'footer','bottom',2),('header',head,'header','top',3)):
                dist=mar.get(q('w:'+dist_key));margin=mar.get(q('w:'+margin_key))
                if not (dist and margin and dist.isdigit() and margin.isdigit()):continue
                for typ,part in parts:
                    if part is None:continue
                    height=sum(para_height_pt(res,p,pitch) for p in part.xpath('./w:p | ./w:sdt/w:sdtContent/w:p',namespaces=NS))
                    reach_cm=round((int(dist)/20+height)*2.54/72,2);margin_cm=twips_cm(margin)
                    f.tested('MARGINS')
                    if reach_cm>margin_cm:
                        excess=reach_cm-margin_cm
                        f.add('MARGINS','error' if excess>0.2 else 'warning',f'The {kind} ({"distance" if kind=="footer" else "distance"} {twips_cm(dist)} cm + about {round(height*2.54/72,2)} cm of content) reaches past the {margin_cm} cm {margin_key} margin, so Word enlarges the {margin_key} whitespace to about {reach_cm} cm.',location+f'/{kind}[{typ}]',actual={'estimated_effective_cm':reach_cm},expected={f'{margin_key}_cm':want_cm})
        if is_pre:
            for typ,footer in foot:
                if footer is not None and re.search(r'\bPAGE\b',' '.join(footer.xpath('.//w:instrText/text() | .//w:fldSimple/@w:instr',namespaces=NS))):
                    if not (cfg['pagination_origin']=='signature' and 'signature' in reg):
                        f.add('PAGE_FORMAT','warning','A cover/title/signature section shows a page number; numbering starts at 誌謝 (i).',location+f'/footer[{typ}]')
            continue
        if is_body and is_front:f.add('PAGE_FORMAT','manual','Front matter and body share a section; inspect field switches and the exact numbering boundary.',location)
        pg=s.find(q('w:pgNumType'));fmt=pg.get(q('w:fmt'),'decimal') if pg is not None else 'decimal';start=pg.get(q('w:start')) if pg is not None else None
        wanted='decimal' if is_body else 'lowerRoman'
        for typ,footer in foot:
            f.tested('PAGE_POSITION')
            floc=location+f'/footer[{typ}]'
            if footer is None:
                f.add('PAGE_POSITION','error','An active footer has no page-number field.',floc);continue
            page_ps=[];switches=[]
            for p in footer.xpath('.//w:p',namespaces=NS):
                instructions=' '.join(p.xpath('.//w:instrText/text() | .//w:fldSimple/@w:instr',namespaces=NS))
                if re.search(r'\bPAGE\b',instructions):
                    page_ps.append(p)
                    sw=re.search(r'\bPAGE\b[^\\]*\\\*\s+(roman|ROMAN|Arabic|arabic)\b',instructions)
                    if sw:switches.append(sw.group(1))
            if not page_ps:
                f.add('PAGE_POSITION','manual','No PAGE field found; static numerals or another representation need visual review.',floc);continue
            for p in page_ps:
                align=res.prop(p,'jc',kind='pPr');tabs=p.xpath('.//w:tab',namespaces=NS)
                def num(v):
                    try:return int(v)
                    except (TypeError,ValueError):return 0
                left=num(res.prop(p,'ind','left',kind='pPr'));right=num(res.prop(p,'ind','right',kind='pPr'))
                first=num(res.prop(p,'ind','firstLine',kind='pPr'))-num(res.prop(p,'ind','hanging',kind='pPr'))
                chars=res.prop(p,'ind','firstLineChars',kind='pPr')
                if chars and chars.lstrip('-').isdigit() and int(chars):first=int(chars)*res_size(res,p)*20//100
                if p.xpath('ancestor::w:tc',namespaces=NS) or tabs:
                    f.add('PAGE_POSITION','manual','Footer table/tabs prevent certifying page-center position from paragraph alignment alone.',floc)
                elif align not in ('center',):f.add('PAGE_POSITION','error','PAGE field paragraph is not centered.',floc,actual=align,expected='center')
                else:
                    offset=(left+first-right)/2
                    if abs(offset)>57:f.add('PAGE_POSITION','warning',f'Indents shift the centred page number by about {round(offset*2.54/1440,2)} cm.',floc,actual={'left':left,'first_line':first,'right':right},expected='no indent')
            effective=fmt
            if switches: effective={'roman':'lowerRoman','ROMAN':'upperRoman','Arabic':'decimal','arabic':'decimal'}[switches[0]]
            f.tested('PAGE_FORMAT')
            if effective!=wanted:f.add('PAGE_FORMAT','error','Numbering format differs from the applicable region.',floc,actual=effective,expected=wanted)
        if is_front and not front_started:
            front_started=True
            if scope=='thesis':
                f.tested('PAGE_ORIGIN')
                first_region=next((r['region'] for r in sec['records'] if r['region'] in FRONT and r['text']),None)
                wanted_origin='signature' if cfg['pagination_origin']=='signature' else 'acknowledgements'
                restarted=start=='1' or idx==1
                if first_region!=wanted_origin and not (wanted_origin=='signature' and first_region=='acknowledgements'):
                    f.add('PAGE_ORIGIN','warning',f'Roman numbering starts at {first_region}; the adopted origin is {wanted_origin} = i.',location,actual=first_region,expected=wanted_origin)
                elif not restarted:
                    f.add('PAGE_ORIGIN','warning','Roman numbering does not restart at 1 where front matter begins, so the unnumbered cover pages are counted.',location,actual=start,expected='1')
        if is_body and first_body:
            f.tested('PAGE_FORMAT')
            if scope=='thesis' and start!='1':f.add('PAGE_FORMAT','manual','First body section does not explicitly restart at 1; rendered page sequence needs review.',location,actual=start,expected='1')
            first_body=False
    if scope=='thesis':
        f.add('PAGE_ORIGIN','manual','Adopted: 誌謝 is page i (regulation 二.4 text and the friend template). The regulation’s TOC sample shows 審定書 i, 誌謝 ii; set pagination_origin to "signature" only if the department asks for that.')

def res_size(res,p):
    sz=res.prop(p,'sz')
    return int(sz)/2 if sz and sz.isdigit() else 10

def chapter_name(display):
    s=re.sub(r'^(第\s*[0-9零一二三四五六七八九十百]+\s*章|chapter\s+\d+|\d+)[\s.．:：]*','',display.strip(),flags=re.I)
    return re.sub(r'\s+',' ',s).strip()

def _audit_structure(pkg,records,regions,images,tables,cfg,f):
    expected_roles=['cover','title','signature','acknowledgements','abstract_zh','abstract_en','toc','references']
    if cfg['title_page']=='omit':expected_roles.remove('title')
    sequence=[]
    for r in records:
        role=r['region']
        if role in FRONT|{'references','appendix'} and role not in sequence:sequence.append(role)
    f.tested('STRUCTURE',len(expected_roles))
    for role in expected_roles:
        if role not in regions:f.add('STRUCTURE','warning',f'Could not identify required component {role}; unlabelled special pages may need a role override.',expected=role)
    order=['cover','title','signature','acknowledgements','abstract_zh','abstract_en','toc','figures','tables','symbols','references','appendix']
    found=[r for r in sequence if r in order]
    want=sorted(found,key=order.index)
    if found!=want:f.add('STRUCTURE','error','Detected component order disagrees with the regulation order.',actual=found,expected=want)
    has_fig=bool(images) or any(caption(r['display']) and caption(r['display']).group(1).lower() in ('圖','figure') for r in records if r['kind']=='caption')
    f.tested('AUTHOR_THESIS_PARTS')
    for role,need,label in (('figures',has_fig,'圖目錄'),('tables',bool(tables),'表目錄')):
        if need and role not in regions:f.add('AUTHOR_THESIS_PARTS','warning',f'The thesis has {"figures" if role=="figures" else "tables"} but no {label} page (regulation TOC sample, friend template, CLAUDE.md).',expected=label)
    if 'symbols' not in regions:f.add('AUTHOR_THESIS_PARTS','manual','No 符號說明 page found; include one if the thesis defines symbols (regulation TOC sample, CLAUDE.md).')
    # Chapter functions (regulation 一). Other names, such as the earlier DSR ones, are flagged for confirmation.
    chapters=[r for r in records if r['level']==1 and r['region']=='body']
    names=[chapter_name(r['display']) for r in chapters]
    f.tested('CHAPTER_NAMES')
    zh=[a for a,_ in CHAPTER_NAMES];en=[b for _,b in CHAPTER_NAMES]
    normal=[n.lower() for n in names]
    if names and normal!=zh and normal!=en:
        f.add('CHAPTER_NAMES','warning','Chapter names differ from regulation 一 (前言、文獻探討、材料與方法、結果與討論、結論). The regulation’s own TOC sample varies them, so this is a deviation to confirm, not a hard error.',actual=names,expected=zh)
    # Back matter carries no chapter number (TOC sample: 參考文獻, 附錄一, 附錄二).
    apps=[]
    for r in records:
        if r['level']!=1 or r['region'] not in ('references','appendix') or role_title(r['text']) not in ('references','appendix'):continue
        f.tested('BACKMATTER_UNNUMBERED')
        if re.match(r'^(第\s*[0-9零一二三四五六七八九十百]+\s*章|chapter\s+\d+|\d+[\s.])',r['display'],re.I):
            f.add('BACKMATTER_UNNUMBERED','warning','References and appendices are not numbered as chapters in the regulation TOC sample.',loc(r),actual=r['display'].replace('\t',' ')[:60],expected=r['text'])
        if role_title(r['text'])=='appendix':apps.append(r)
    if len(apps)>1 and len({re.sub(r'\s+','',a['text']) for a in apps})<len(apps):
        f.add('BACKMATTER_UNNUMBERED','warning','Several appendices share one title; the TOC sample numbers them 附錄一, 附錄二.',loc(apps[1]),actual=[a['text'] for a in apps])
    # TOC content (二.1 目錄範例).
    toc_entries=[r for r in records if r['region']=='toc' and re.match(r'^toc\s*\d$',r['style_name'].strip(),re.I)]
    fields=' '.join(pkg.doc.xpath('.//w:instrText/text() | .//w:fldSimple/@w:instr',namespaces=NS))
    if 'toc' in regions:
        f.tested('TOC_CONTENT')
        if not re.search(r'\bTOC\b',fields) and not toc_entries:
            f.add('TOC_CONTENT','warning','The 目錄 page has no TOC field or entries.')
        for r in toc_entries:
            if role_title(re.sub(r'[\s.…·\d]+$','',re.sub(r'[ivxlcdm]+$','',r['text'].strip())))=='toc':
                f.add('TOC_CONTENT','warning','The TOC lists the 目錄 page itself; the regulation sample does not.',loc(r),excerpt=r['text'][:60])
        if not any(r['region']=='toc' and r['text'].strip() in ('頁數','頁次','Page') for r in records):
            f.add('TOC_CONTENT','manual','The regulation TOC sample puts 頁數 above the page-number column.')
    # Special pages against the samples.
    cover=[r['text'] for r in records if r['region']=='cover']
    if cover:
        f.tested('COVER_CONTENT')
        joined='\n'.join(cover)
        for label,pattern in (('系名',r'國立臺灣大學生物資源暨農學院生物機電工程學系'),('學位',r'(碩|博)士論文'),('英文系名',r'Department of Biomechatronics Engineering'),('英文學院',r'College of Bioresources and Agriculture'),('英文校名',r'National Taiwan University'),('英文學位',r'Master Thesis|Doctoral Dissertation'),('指導教授',r'指導教授'),('Advisor',r'Advisor'),('日期',r'中華民國\s*\d+\s*年\s*\d+\s*月')):
            if not re.search(pattern,joined):f.add('COVER_CONTENT','warning',f'Cover lacks the {label} line of the regulation sample.',expected=label)
    sig=[r['text'] for r in records if r['region']=='signature']
    if sig:
        f.tested('SIGNATURE_CONTENT');joined='\n'.join(sig)
        for label,pattern in (('標題',r'口試委員會審定書'),('證明文字',r'本論文係'),('口試委員',r'口試委員'),('系主任',r'系主任')):
            if not re.search(pattern,joined):f.add('SIGNATURE_CONTENT','warning',f'Signature page lacks the {label} of the regulation sample.',expected=label)
    f.add('SPECIAL_PAGES','manual','Compare cover/signature/TOC to the regulation samples visually. No source shows a separate title-page layout; the adopted default repeats the cover.')

def _audit_headings(records,f):
    seen_numbers={};current_chapter=None
    for rec in records:
        if not rec['level'] or rec['region'] in FRONT or rec['region'] in ('references','appendix'):continue
        s=rec['display']
        if not rec['text'] and rec['label']:
            f.add('HEADING_NUMBER','warning','A numbered heading paragraph has no text, so Word prints a stray number (and adds it to the TOC).',loc(rec),actual=rec['label'].strip())
            continue
        n=parse_chapter(s) if rec['level']==1 else None
        if n is not None:current_chapter=n
        if rec['level']>1:
            f.tested('HEADING_NUMBER');m=re.match(r'^(\d+(?:[.-]\d+)+)\s+',s)
            if not m:f.add('HEADING_NUMBER','warning','Subheading has no recognized 1.1 / 1-1 numbering.',loc(rec),actual=s)
            else:
                num=tuple(int(x) for x in re.split('[.-]',m.group(1)))
                if num in seen_numbers:f.add('HEADING_NUMBER','error','Duplicate visible subheading number.',loc(rec),actual=m.group(1),excerpt=s)
                seen_numbers[num]=rec
                if current_chapter is not None and num[0]!=current_chapter:f.add('HEADING_NUMBER','error','Subheading number disagrees with the enclosing chapter.',loc(rec),actual=num[0],expected=current_chapter)

def _audit_captions(pkg,records,scope,f):
    by_element={r['element']:r for r in records}
    region_of=lambda node:next((by_element[p]['region'] for p in ([node] if node.tag==q('w:p') else node.xpath('.//w:p',namespaces=NS)) if p in by_element),'body')
    blocks=[b for b in pkg.body if b.tag==q('w:tbl') or b.tag==q('w:p') and (text(b).strip() or by_element.get(b,{}).get('label') or b.xpath('.//w:drawing | .//w:pict',namespaces=NS))]
    shown=lambda b:by_element[b]['display'] if b in by_element else text(b)
    capnodes=[]
    for i,b in enumerate(blocks):
        is_table=b.tag==q('w:tbl');is_image=b.tag==q('w:p') and bool(b.xpath('.//w:drawing | .//w:pict',namespaces=NS))
        if not(is_table or is_image):continue
        if region_of(b) in FRONT:continue
        location=f'word/document.xml/body[{list(pkg.body).index(b)+1}]';f.tested('CAPTION_POSITION')
        if is_image and text(b).strip():
            f.add('CAPTION_POSITION','manual','Image and text share a paragraph; visual caption position needs review.',location);continue
        j=i-1 if is_table else i+1;near=blocks[j] if 0<=j<len(blocks) else None
        near_text=shown(near).strip() if near is not None and near.tag==q('w:p') else ''
        m=caption(near_text)
        wanted=('表','table') if is_table else ('圖','figure')
        if m and m.group(1).lower() in wanted:capnodes.append((near,m));continue
        if caption_like(near_text) and caption_like(near_text).group(1).lower() in wanted:
            f.add('CAPTION_NUMBER','error','Caption number must use the 圖1-1 / 表1-1 form (二.3), not a dot.',location,actual=near_text[:40]);continue
        f.add('CAPTION_POSITION','error','Missing recognized table caption immediately above table.' if is_table else 'Missing recognized figure caption immediately below image.',location,actual=near_text[:100] or None,expected='表 chapter-sequence title' if is_table else '圖 chapter-sequence title')
    last={};seen_cap=set();chapter=None;chapter_at={}
    for r in records:
        if r['level']==1 and r['region']=='body':chapter=parse_chapter(r['display'])
        chapter_at[r['element']]=(chapter,r['region'])
    for p,m in capnodes:
        kind='table' if m.group(1).lower() in ('表','table') else 'figure';ch=int(m.group(2));number=int(m.group(3));key=(kind,ch);locp=f'word/document.xml/body[{list(pkg.body).index(p)+1}]'
        f.tested('CAPTION_NUMBER')
        cur,region=chapter_at.get(p,(None,'body'))
        if cur is not None and region=='body' and ch!=cur:f.add('CAPTION_NUMBER','error','Caption chapter number differs from the enclosing chapter (圖表按章).',locp,actual=ch,expected=cur)
        if (key,number) in seen_cap:f.add('CAPTION_NUMBER','error','Duplicate caption number.',locp,actual=m.group(0)[:30])
        if key in last and number!=last[key]+1:f.add('CAPTION_NUMBER','error','Caption sequence is not consecutive within this chapter/type.',locp,actual=number,expected=last[key]+1)
        elif key not in last and scope=='thesis' and number!=1:f.add('CAPTION_NUMBER','warning','First detected caption in a chapter does not start at 1.',locp,actual=number)
        if not m.group(4).strip():f.add('CAPTION_COMPLETE','warning','Caption number exists but title is empty.',locp)
        seen_cap.add((key,number));last[key]=number
    images=pkg.doc.xpath('.//w:drawing | .//w:pict',namespaces=NS)
    if images:f.add('IMAGE_SCALE','manual','Inspect image pixels for a scale/unit label when size is relevant; XML alt text is not evidence of an embedded scale.')
    if images:f.add('PHOTO_ORIGIN','manual','Original photographic source and academic value require supplied provenance and human judgment.')
    if images or pkg.body.findall(q('w:tbl')):f.add('CAPTION_COMPLETE','manual','Judge whether each figure/table is independently understandable, including axes, units, and necessary explanation.')

def _audit_abstracts(records,f,metrics):
    for lang in ('zh','en'):
        rs=[r for r in records if r['region']=='abstract_'+lang and r['kind']!='heading' and r['kind']!='special' and r['text']]
        if not rs:
            if any(r['region']=='abstract_'+lang for r in records):
                f.add('KEYWORDS','manual',f'The {lang} abstract page has no text yet; length and 3–5 keywords are checked once it is written.')
            continue
        key_lines=[r for r in rs if KEYWORDS.match(r['text'])];body=[r for r in rs if r not in key_lines]
        value='\n'.join(r['text'] for r in body)
        counts={'cjk_characters':len(CJK.findall(value)),'english_words':len(re.findall(r"\b[A-Za-z]+(?:[-'][A-Za-z]+)*\b",value)),'non_whitespace_characters':len(re.sub(r'\s','',value)),'pages':'not_determined_from_docx_xml'}
        metrics['abstracts'][lang]=counts
        # CLAUDE.md decision: each abstract 500–1000, Chinese by characters, English by words.
        n=counts['cjk_characters'] if lang=='zh' else counts['english_words']
        f.tested('ABSTRACT_LENGTH')
        if not 500<=n<=1000:f.add('ABSTRACT_LENGTH','warning',f'{"Chinese" if lang=="zh" else "English"} abstract has {n} {"characters" if lang=="zh" else "words"}; the adopted reading of 約500至1000字 is 500–1000 per abstract.',actual=n,expected='500–1000')
        f.add('ABSTRACT_LENGTH','manual','The three-page limit can only be judged on the rendered document.')
        f.tested('KEYWORDS')
        if not key_lines:f.add('KEYWORDS','error',f'Missing recognized {lang} keywords line.',expected='3–5 keywords at the end, separated by semicolons/commas/、')
        for kr in key_lines:
            raw=re.split('[:：]',kr['text'],maxsplit=1)[1].strip();parts=[p.strip(' .。') for p in re.split('[,，;；、]',raw) if p.strip(' .。')]
            if not re.search('[,，;；、]',raw) and raw:f.add('KEYWORDS','unknown','No unambiguous keyword separator; do not guess multiword keyword boundaries.',loc(kr),actual=raw)
            elif not 3<=len(parts)<=5:f.add('KEYWORDS','error','Keyword count is outside 3–5.',loc(kr),actual=len(parts),expected='3–5')
            if rs[-1] is not kr:f.add('KEYWORDS','warning','Keywords line is not at the end of the abstract.',loc(kr))
        for r in body:
            f.tested('ABSTRACT_LIST')
            if r['label'] or r['element'].find('w:pPr/w:numPr',NS) is not None or re.match(r'^\s*(?:\d+[.、)]|[一二三四五六七八九]+、|[•●])\s*',r['text']):
                f.add('ABSTRACT_LIST','warning','Possible prohibited abstract list; review paragraph meaning before declaring a violation.',loc(r),excerpt=r['text'][:120])
        f.add('ABSTRACT_CONTENT','manual','Read both complete abstracts for purpose, methods, results, conclusions, clarity, and cross-language consistency.')

def _audit_text_conventions(records,f):
    prose=[r for r in records if r['kind']=='body' and r['region'] in ('body','acknowledgements','abstract_zh','abstract_en','appendix') and r['text']]
    # NUMERAL — CLAUDE.md decision: numbers above ten in Arabic numerals; ten and below may stay Chinese.
    for r in prose:
        f.tested('NUMERAL')
        for m in NUMERAL.finditer(r['text']):
            if any(r['text'][max(0,m.start()-1):m.end()+2].find(x)>=0 for x in NUMERAL_IDIOMS):continue
            v=zh_value(m.group(1));after=r['text'][m.end():m.end()+1];before=r['text'][max(0,m.start()-4):m.start()]
            # Month and day names (十一月、二十日) are calendar words, not counts.
            if (after=='月' and v and v<=12) or (after=='日' and '月' in before):continue
            if v and v>10:f.add('NUMERAL','warning',f'Chinese numeral 「{m.group(1)}」 ({v}) is above ten; the adopted reading of 二.6(1) uses Arabic numerals.',loc(r),actual=m.group(1),expected=str(v),excerpt=r['text'][max(0,m.start()-10):m.end()+10])
    f.add('NUMERAL','manual','Heuristic only: numerals inside quotations, names, idioms and dates need reading in context.')
    # CITATION_FORM — typographic checks of 二.8(4) forms.
    patterns=[(r'\bet\s+al(?!\.)','Use “et al.” with a full stop.'),
              (r'\([^()]*[A-Z][A-Za-z\-]+\s*&\s*[A-Z][^()]*\d{4}[a-z]?\)','Two English authors are joined with “and”, not “&”.'),
              (r'\([^()]*[A-Z][A-Za-z\-]+(?:\s+et al\.)?，\s*\d{4}','English author-year citations take a half-width comma: (Smith, 1985).'),
              (r'\([^()]*[一-鿿]+(?:等人)?,\s*\d{4}','Chinese author-year citations take a full-width comma: (陳等人，1989).'),
              (r'\([^()]*[一-鿿](?<!人)等[，,]\s*\d{4}','Three or more Chinese authors are written 等人: (陳等人，1989).')]
    for r in prose:
        for pattern,message in patterns:
            hit=re.search(pattern,r['text'])
            f.tested('CITATION_FORM')
            if hit:f.add('CITATION_FORM','warning',message,loc(r),excerpt=r['text'][max(0,hit.start()-10):hit.end()+10])

def _audit_reference_order(records,f):
    """二.8(2): Chinese, then Japanese, then English; English by surname. Stroke order needs verified data."""
    entries=[r for r in records if r['region']=='references' and not r['level'] and r['kind'] in ('body','special') and r['text'] and not KEYWORDS.match(r['text']) and not re.match(r'^\s*\[(TODO|CITE|FIGURE)\b',r['text'])]
    groups=[]
    for r in entries:
        t=r['text'].strip()
        g=1 if re.match(r'^[぀-ヿ]',t) or re.search(r'[぀-ヿ]',t[:20]) else 0 if CJK.match(t) else 2
        groups.append((g,r))
    f.tested('REF_ORDER',len(groups))
    for (g1,r1),(g2,r2) in zip(groups,groups[1:]):
        if g2<g1:
            f.add('REF_ORDER','error','Reference list is not ordered Chinese → Japanese → English (二.8(2)).',loc(r2),excerpt=r2['text'][:60]);break
    en=[r for g,r in groups if g==2]
    keys=[re.sub(r'[^a-z]','',unicodedata_fold(re.split(r'[,.]',r['text'].strip(),maxsplit=1)[0])) for r in en]
    for (k1,r1),(k2,r2) in zip(zip(keys,en),list(zip(keys,en))[1:]):
        if k2<k1:
            f.add('REF_ORDER','warning','English references are not in surname order.',loc(r2),actual=[k1,k2],excerpt=r2['text'][:60]);break
    if any(g==0 for g,_ in groups):f.add('REF_ORDER','manual','Chinese entries must follow surname stroke counts; verify with a stroke table, never Unicode order.')

def unicodedata_fold(s):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD',s) if not unicodedata.combining(c)).casefold()

def _audit_references(records,manifest,f):
    entries=manifest.get('entries',[])
    if not isinstance(entries,list):raise BimeError('Reference manifest entries must be a list.')
    body='\n'.join(r['text'] for r in records if r['region'] not in FRONT|{'references'})
    refs='\n'.join(r['text'] for r in records if r['region']=='references' and not r['level'])
    order=[];declared=[]
    for item in entries:
        rid=item.get('id','unnamed');citation_forms=item.get('citation_forms');ref=item.get('reference_text')
        if not ref or not citation_forms:raise BimeError(f'Reference manifest {rid}: reference_text and verified citation_forms are required.')
        offset=refs.find(ref);found=[s for s in citation_forms if s in body]
        f.tested('REF_CITED',2)
        if offset>=0 and not found:f.add('REF_CITED','error','Manifest-listed reference occurs in the bibliography but no supplied citation form occurs in the body.',actual=rid)
        if found and offset<0:f.add('REF_CITED','error','A supplied citation form occurs in the body but its exact reference entry is missing.',actual=rid)
        if offset<0:continue
        declared.append(ref)
        language=item.get('language');key=item.get('sort_key');year=item.get('year')
        if language not in ('zh','ja','en') or key is None or year is None:
            f.add('REF_ORDER','manual','Reference manifest lacks verified language/surname sort key/year.',actual=rid);continue
        if language in ('zh','ja') and not isinstance(key,(int,float)):
            f.add('REF_ORDER','manual','Chinese/Japanese sort_key must be a verified numeric surname stroke key.',actual=rid);continue
        f.tested('REF_ORDER');order.append((offset,({'zh':0,'ja':1,'en':2}[language],key if language in ('zh','ja') else str(key).casefold(),int(year)),rid))
    actual=[x[2] for x in sorted(order,key=lambda x:x[0])];expected=[x[2] for x in sorted(order,key=lambda x:x[1])]
    if actual!=expected:f.add('REF_ORDER','error','Verified manifest entries are not in the source-prescribed order.',actual=actual,expected=expected)
    f.add('REF_CITED','manual','Manifest matching covers only supplied literal citation/reference forms. Unlisted entries, alternate forms, and author/year ambiguity still need review.')

AUTHORITY_LABEL={'regulation':'系辦附件十七','friend_template':'朋友範本','author_claude_md':'CLAUDE.md','implementation_default':'實作預設'}

def report_markdown(report):
    lines=['# bime_word 檢查報告','',f"檔案：`{report['source']}`",f"SHA-256：`{report['source_sha256']}`",f"範圍：`{report['scope']}`；結果：`{report['overall']}`",'',
           '權威順序：系辦附件十七 > 朋友範本 > CLAUDE.md > 實作預設。只有系辦條文是學校規定；其餘來源用來補系辦沒寫清楚的地方，每條發現都標明依據。','',
           '這是 OOXML 與文字檢查，不是已完成 Word 視覺驗收。位置是 XML/段落定位，不冒充頁碼。','', '## 統計','', ' | '.join(f'{k}: {v}' for k,v in report['summary'].items()),'', '## 發現','']
    order={'error':0,'conflict':1,'warning':2,'unknown':3,'manual':4}
    for x in sorted(report['findings'],key=lambda x:order[x['severity']]):
        count=f"（共 {x['count']} 處）" if x.get('count',1)>1 else ''
        lines += [f"### [{x['severity']}] {x['rule_id']} — {x['location']}{count}",x['message']]
        if x.get('count',1)>1:lines.append('位置：'+'; '.join(x['locations'])+(' …' if x['count']>len(x['locations']) else ''))
        if x['actual'] is not None:lines.append('實際：`'+json.dumps(x['actual'],ensure_ascii=False)+'`')
        if x['expected'] is not None:lines.append('預期：`'+json.dumps(x['expected'],ensure_ascii=False)+'`')
        if x['excerpt']:lines.append('文字：'+x['excerpt'].replace('\t',' '))
        src=x['source'];label=AUTHORITY_LABEL.get(src.get('authority'),src.get('authority'))
        lines.append(f"依據：{label}；{src['section']}"+(f"；原始 DOCX 段落 P{src['paragraph_1based']}" if src.get('paragraph_1based') else '')+f"；{src['strength']}。")
        if x.get('decision'):lines.append(f"採用的解讀（{AUTHORITY_LABEL.get(x['decision']['resolved_by'])}）：{x['decision']['resolution']}")
        lines.append('')
    lines += ['## 檢查覆蓋','', '| 規則 | 權威 | 狀態 | 機器檢查次數 |','|---|---|---|---|']
    for rid,c in report['coverage'].items():lines.append(f"| {rid} | {AUTHORITY_LABEL.get(RULES[rid].get('authority'),'')} | {c['status']} | {c['tested']} |")
    return '\n'.join(lines)+'\n'
