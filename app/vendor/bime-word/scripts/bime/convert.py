"""Markdown conversion through Pandoc, then OOXML formatting.

Every formatting value comes from the precedence the user set:
Appendix 17 (regulation) > the friend's Word template > the author's CLAUDE.md >
implementation default. references/authority.md lists each value and its source.
"""
from __future__ import annotations
import copy, json, re, shutil, subprocess, tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.style import WD_STYLE_TYPE
from .common import *
from . import cite

MD_FORMAT='markdown+pipe_tables+footnotes+tex_math_dollars+fenced_divs+bracketed_spans+citations+yaml_metadata_block-smart'
TEXT_WIDTH_TWIPS=8494          # friend template: TOC right tab stop (A4 minus 3 cm margins is 8504)
DEPARTMENT_ZH='國立臺灣大學生物資源暨農學院生物機電工程學系'   # regulation cover sample
DEPARTMENT_EN=['Department of Biomechatronics Engineering','College of Bioresources and Agriculture','National Taiwan University']
META_KEYS={'degree','title_zh','title_en','author_zh','author_en','student_id','advisor_zh','advisor_en','year_roc','month','date','defense_date','title_page'}

def run_pandoc(args, *, data=None, cwd=None):
    exe=shutil.which('pandoc')
    if not exe: raise BimeError('Pandoc is required for convert/insert. See README.md installation instructions.')
    p=subprocess.run([exe,*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=cwd,timeout=180)
    if p.returncode: raise BimeError('Pandoc failed: '+p.stderr.decode('utf-8',errors='replace'))
    return p.stdout,p.stderr.decode('utf-8',errors='replace').strip()

def inline_text(xs):
    out=[]
    for x in xs:
        if not isinstance(x,dict): continue
        t=x.get('t'); c=x.get('c')
        if t=='Str': out.append(c)
        elif t in ('Space','SoftBreak','LineBreak'): out.append(' ')
        elif t=='Code': out.append(c[1])
        elif t=='Math': out.append(c[1])
        elif t in ('Emph','Strong','Strikeout','Superscript','Subscript','SmallCaps','Underline'): out.append(inline_text(c))
        elif t in ('Link','Image','Span','Cite'): out.append(inline_text(c[1]))
        elif t=='Quoted': out.append(inline_text(c[1]))
    return ''.join(out)

def zhnum(n): return zh_count(n)

def parse_chapter(s):
    hit=re.match(r'^第\s*([0-9零一二三四五六七八九十百]+)\s*章',s)
    if hit:
        n=hit.group(1)
        if n.isdigit(): return int(n)
        chars={v:i for i,v in enumerate('零一二三四五六七八九')}
        if '十' in n:
            a,b=n.split('十',1); return (chars.get(a,1) if a else 1)*10+chars.get(b,0)
        return chars.get(n)
    hit=re.match(r'^chapter\s+(\d+)\b',s,re.I)
    if hit: return int(hit.group(1))
    hit=re.match(r'^(\d+)(?:[.．]?\s+)',s)
    return int(hit.group(1)) if hit else None

def meta_value(node):
    t=node.get('t'); c=node.get('c')
    if t=='MetaInlines': return inline_text(c).strip()
    if t=='MetaString': return str(c)
    if t=='MetaBool': return bool(c)
    if t=='MetaList': return [meta_value(x) for x in c]
    if t=='MetaMap': return {k:meta_value(v) for k,v in c.items()}
    if t=='MetaBlocks': return '\n'.join(inline_text(b.get('c',[])) for b in c if b.get('t') in ('Para','Plain'))
    return None

def blocks_walk(blocks):
    for b in blocks:
        yield b
        t=b.get('t'); c=b.get('c')
        if t in ('BlockQuote',): yield from blocks_walk(c)
        elif t=='Div': yield from blocks_walk(c[1])
        elif t in ('BulletList',):
            for item in c: yield from blocks_walk(item)
        elif t=='OrderedList':
            for item in c[1]: yield from blocks_walk(item)

LABEL=re.compile(r'^\s*(圖|表|Figure|Table)\s*(\d+)\s*[-－–]\s*(\d+)\s*[.:：、]?\s*',re.I)

def normalize_caption(inlines, lang):
    """二.3 / friend template: '圖1-1' (no space), a tab, then the title; captions are not bold."""
    if len(inlines)==1 and inlines[0].get('t')=='Strong': inlines=inlines[0]['c']
    lead=[];acc=''
    for x in inlines:
        if x.get('t') not in ('Str','Space'): break
        lead.append(x);acc+=x['c'] if x['t']=='Str' else ' '
    m=LABEL.match(acc)
    if not m: return None
    word=m.group(1); word={'figure':'Figure','table':'Table'}.get(word.lower(),word)
    label=(f'{word}{m.group(2)}-{m.group(3)}' if word in ('圖','表') else f'{word} {m.group(2)}-{m.group(3)}')
    consumed=m.end();rest=[];used=0
    for x in lead:
        piece=x['c'] if x['t']=='Str' else ' '
        if used+len(piece)<=consumed: used+=len(piece);continue
        cut=consumed-used;used+=len(piece)
        if cut>0 and x['t']=='Str': rest.append({'t':'Str','c':piece[cut:]})
        elif cut<=0: rest.append(x)
    rest+=inlines[len(lead):]
    return [{'t':'Str','c':label+'\t'}]+rest

def is_figure_block(b):
    if b.get('t')=='Figure': return True
    return b.get('t')=='Para' and any(x.get('t')=='Image' for x in b['c'])

def head(level,text_value):
    return {'t':'Header','c':[level,['',[],[]],[{'t':'Str','c':text_value}]]}

def placeholder(token):
    return {'t':'Para','c':[{'t':'Str','c':token}]}

def drop_todos(markdown):
    """Remove [TODO: …] placeholders (brackets balanced, so citations inside go too); return text and report."""
    out=[];removed=[];i=0;n=len(markdown)
    while i<n:
        if markdown.startswith('[TODO:',i):
            depth=0;j=i
            while j<n:
                if markdown[j]=='[':depth+=1
                elif markdown[j]==']':
                    depth-=1
                    if depth==0:break
                j+=1
            if j>=n:break
            removed.append({'line':markdown.count('\n',0,i)+1,'text':markdown[i:j+1][:120]})
            # Drop the space that separated the placeholder from the sentence before it.
            if out and out[-1].endswith(' ') and (j+1>=n or markdown[j+1]=='\n'):out[-1]=out[-1].rstrip(' ')
            i=j+1;continue
        k=markdown.find('[TODO:',i)
        k=n if k<0 else k
        out.append(markdown[i:k]);i=k
    text=''.join(out)
    lines_with=set(r['line'] for r in removed);dangling=[]
    for no,line in enumerate(text.split('\n'),1):
        bare=re.sub(r'[*_\s]','',re.sub(r'^\s*(?:[-*+]|\d+\.)\s+','',line))
        if no in lines_with and line.strip() and re.fullmatch(r'.{0,24}[：:。]',bare):
            dangling.append({'line':no,'text':line.strip()[:60]})
    return text,removed,dangling

def prepare_ast(source: Path,cfg,scope, *, for_insert=False, bibliography=None):
    shift=['--shift-heading-level-by=-1'] if cfg['shift_heading_level']==-1 else []
    markdown=source.read_text(encoding='utf-8-sig');notes=[]
    if cfg['drop_todo']:
        markdown,removed,dangling=drop_todos(markdown)
        if removed:notes.append({'type':'todo_dropped','message':f'{len(removed)} [TODO: …] placeholder(s) were left out of the Word file; the Markdown keeps them.','items':removed})
        if dangling:notes.append({'type':'todo_dangling','message':'These lines are left with only a label after their TODO was removed; fill them or delete the label in the Markdown.','items':dangling})
    raw,warn=run_pandoc(['--from',MD_FORMAT,'--to','json',*shift],data=markdown.encode('utf-8'),cwd=source.parent)
    ast=json.loads(raw)
    if shift: notes.append({'type':'headings','message':'The first # heading became the document title and ## headings are chapters (shift_heading_level = -1).'})
    if warn: notes.append({'type':'pandoc_warning','message':warn})
    meta={}
    title_node=(ast.get('meta') or {}).get('title')
    title_inlines=title_node['c'] if isinstance(title_node,dict) and title_node.get('t')=='MetaInlines' else None
    if ast.get('meta'):
        values={k:meta_value(v) for k,v in ast['meta'].items()}
        meta=values.get('bime') or {}
        if not isinstance(meta,dict): raise BimeError('The bime metadata block must be a mapping.')
        if values.get('title') and not meta.get('title_zh'):
            meta=dict(meta,title_zh=values['title'])
        unknown=sorted(set(meta)-META_KEYS)
        if unknown: notes.append({'type':'metadata','message':'Unknown bime metadata keys were ignored.','keys':unknown})
        if not bibliography and values.get('bibliography'):
            bib=values['bibliography'];bib=bib[0] if isinstance(bib,list) else bib
            bibliography=(source.parent/str(bib)).resolve()
        others=sorted(set(values)-{'bime','bibliography','title'})
        if others: notes.append({'type':'metadata','message':'YAML keys other than bime/bibliography are not rendered.','keys':others})
        ast['meta']={}
    base=source.parent.resolve()
    def walk(node):
        if isinstance(node,dict):
            t=node.get('t'); c=node.get('c')
            if t in ('RawInline','RawBlock'):
                if not (c[0]=='html' and re.fullmatch(r'\s*<!--[\s\S]*?-->\s*',c[1])):
                    raise BimeError(f'Unsupported raw {c[0]} content. Convert it to Markdown/OMML rather than silently dropping it.')
            if t=='Image':
                target=c[2][0]; parsed=urlparse(target)
                if parsed.scheme or parsed.netloc: raise BimeError('Remote/file-URL image loading is disabled. Store the image beside the Markdown file.')
                resolved=(base/unquote(target.split('#')[0])).resolve()
                try: resolved.relative_to(base)
                except ValueError: raise BimeError('Image is outside the Markdown asset directory: '+target)
                if not resolved.is_file(): raise BimeError('Missing image: '+target)
                c[2][0]=str(resolved)
            for val in node.values(): walk(val)
        elif isinstance(node,list):
            for val in node: walk(val)
    walk(ast['blocks'])
    # WRITING_LANGUAGE / LINE_SPACING decision: one language for the whole document.
    if cfg['language'] in ('zh','en'): lang,how=cfg['language'],'profile'
    else:
        lang=document_language([inline_text(b['c']) for b in blocks_walk(ast['blocks']) if b.get('t') in ('Para','Plain')]);how='detected from the body text'
    notes.append({'type':'writing_language','rule':'WRITING_LANGUAGE','message':f'Document language {lang} ({how}); line spacing {"1.5" if lang=="zh" else "2.0"} applies to the whole document.','language':lang})
    blocks=ast['blocks']
    if title_inlines and scope!='thesis' and not for_insert and not cfg['cover']:
        # With shift_heading_level -1 the first # heading is the document title; keep it visible.
        blocks.insert(0,{'t':'Div','c':[['',[],[['custom-style','BIME Doc Title']]],[{'t':'Para','c':title_inlines}]]})
    # Captions: table captions above tables, figure captions below figures (二.3), normalised label.
    changed=0
    for i,b in enumerate(blocks):
        if b.get('t')=='Para':
            nxt=blocks[i+1] if i+1<len(blocks) else {}
            prv=blocks[i-1] if i else {}
            whole_bold=len(b['c'])==1 and b['c'][0].get('t')=='Strong'
            if nxt.get('t')=='Table' or is_figure_block(prv) or whole_bold:
                new=normalize_caption(b['c'],lang)
                if new: b['c']=new;changed+=1
        elif b.get('t')=='Table':
            cap=b['c'][1][1]
            for blk in cap:
                if blk.get('t') in ('Plain','Para'):
                    new=normalize_caption(blk['c'],lang)
                    if new: blk['c']=new;changed+=1
        elif b.get('t')=='Figure':
            for blk in b['c'][1][1]:
                if blk.get('t') in ('Plain','Para'):
                    new=normalize_caption(blk['c'],lang)
                    if new: blk['c']=new;changed+=1
    if changed: notes.append({'type':'captions','rule':'HOUSE_CAPTION','message':f'{changed} caption label(s) normalised to 圖1-1/表1-1 + tab (regulation 二.3, friend template); bold removed from captions.'})
    # Headings: chapter labels by language, sections 1.1 (二.3), appendices 附錄一… (目錄範例).
    counters=[0]*6; body=False
    appendix_heads=[b for b in blocks if b.get('t')=='Header' and b['c'][0]==1 and role_title(inline_text(b['c'][2]))=='appendix' and re.sub(r'\s+','',inline_text(b['c'][2])).lower() in ('附錄','appendix')]
    for n,b in enumerate(appendix_heads,1):
        if len(appendix_heads)>1:
            b['c'][2]=[{'t':'Str','c':('附錄'+zh_count(n)) if inline_text(b['c'][2]).strip().startswith('附') else 'Appendix'},*([] if inline_text(b['c'][2]).strip().startswith('附') else [{'t':'Space'},{'t':'Str','c':chr(64+n)}])]
    for block in blocks:
        if block.get('t')!='Header': continue
        level,attrs,inlines=block['c']; s=inline_text(inlines).strip(); role=role_title(s)
        if role:
            if level!=1: notes.append({'type':'role_heading','message':f'{s}: semantic role is clearest as an H1 heading.'})
            if role in FRONT: body=False
            continue
        if level==1:
            body=True; n=parse_chapter(s)
            counters[0]=n if n is not None else counters[0]+1
            counters[1:]=[0]*5
            if n is None and cfg['auto_number_headings']:
                if for_insert: raise BimeError('Insertion requires explicit chapter numbers in Markdown; inspect the target before choosing them.')
                prefix=[{'t':'Str','c':'第'+zh_count(counters[0])+'章　'}] if lang=='zh' else [{'t':'Str','c':'Chapter'},{'t':'Space'},{'t':'Str','c':str(counters[0])},{'t':'Space'}]
                inlines[:0]=prefix
        elif body or scope=='fragment':
            num=re.match(r'^(\d+(?:[.-]\d+)+)\s+',s)
            if num:
                values=[int(x) for x in re.split(r'[.-]',num.group(1))]
                counters[:len(values)]=values
                for k in range(len(values),6): counters[k]=0
            elif cfg['auto_number_headings']:
                if for_insert: raise BimeError('Insertion requires explicit subsection numbers (for example ## 1.2 方法).')
                if not counters[0]: counters[0]=1
                if level>2 and counters[level-2]==0: raise BimeError('Heading hierarchy jumps a level; add the missing parent heading.')
                counters[level-1]+=1
                for k in range(level,6): counters[k]=0
                inlines[:0]=[{'t':'Str','c':cfg['heading_separator'].join(map(str,counters[:level]))},{'t':'Space'}]
    # Front-matter lists (目錄範例, friend template, CLAUDE.md thesis parts).
    if scope=='thesis' and not for_insert:
        add_lists(blocks,lang,notes)
    # Citations (二.8(4)) and the reference list (二.8(1)-(13)).
    div,report=cite.process(ast,bibliography,notes=notes)
    if div is not None:
        place_references(blocks,div,scope,lang,notes,for_insert)
    else:
        for i,b in enumerate(blocks):
            if b.get('t')=='Para' and inline_text(b['c']).strip()=='{{REFERENCES}}':
                blocks[i]={'t':'Div','c':[['',['references'],[]],[]]}
                notes.append({'type':'references','rule':'REF_CITED','message':'{{REFERENCES}} found but the text cites no keys; the placeholder was removed.'})
    return ast,notes,meta,lang,report

def h1_roles(blocks):
    out=[]
    for i,b in enumerate(blocks):
        if b.get('t')=='Header' and b['c'][0]==1:
            out.append((i,role_title(inline_text(b['c'][2]))))
    return out

def section_empty(blocks,i):
    j=i+1
    while j<len(blocks) and not (blocks[j].get('t')=='Header' and blocks[j]['c'][0]==1):
        if blocks[j].get('t') not in ('Null',): return False
        j+=1
    return True

def add_lists(blocks,lang,notes):
    names={'toc':('目錄','Table of Contents','{{TOC}}'),'figures':('圖目錄','List of Figures','{{LOF}}'),'tables':('表目錄','List of Tables','{{LOT}}')}
    has_fig=any(is_figure_block(b) or (b.get('t')=='Para' and re.match(r'^(圖|Figure)\s*\d+-\d+',inline_text(b['c']),re.I)) for b in blocks_walk(blocks))
    has_tab=any(b.get('t')=='Table' for b in blocks_walk(blocks))
    wanted=['toc']+(['figures'] if has_fig else [])+(['tables'] if has_tab else [])
    added=[]
    for role in wanted:
        zh,en,token=names[role]
        roles=h1_roles(blocks)
        found=[i for i,r in roles if r==role]
        if found:
            i=found[0]
            nxt=blocks[i+1] if i+1<len(blocks) else None
            if not (nxt and nxt.get('t')=='Para' and inline_text(nxt['c']).strip()==token) and section_empty(blocks,i):
                blocks.insert(i+1,placeholder(token));added.append(token)
            continue
        order=['toc','figures','tables','symbols']
        later=[i for i,r in roles if (r in order and order.index(r)>order.index(role)) or r is None]
        at=later[0] if later else len(blocks)
        blocks[at:at]=[head(1,zh if lang=='zh' else en),placeholder(token)];added.append(zh if lang=='zh' else en)
    if added: notes.append({'type':'front_lists','rule':'TOC_CONTENT','message':'Added missing list pages or fields: '+', '.join(added)+'. Update fields in Word.'})

def place_references(blocks,div,scope,lang,notes,for_insert):
    for i,b in enumerate(blocks):
        if b.get('t')=='Para' and inline_text(b['c']).strip()=='{{REFERENCES}}':
            blocks[i]=div;return
    if for_insert:
        notes.append({'type':'references','rule':'REF_CITED','message':'Inserted text cites works; add their entries to the target reference list (not merged automatically).','entries':len(div['c'][1])});return
    roles=h1_roles(blocks);refs=[i for i,r in roles if r=='references']
    if refs:
        if not section_empty(blocks,refs[0]):
            raise BimeError('The references section already has content. Replace it with a {{REFERENCES}} paragraph so the list is generated from the cited keys.')
        blocks.insert(refs[0]+1,div);return
    if scope=='thesis':
        apps=[i for i,r in roles if r=='appendix'];at=apps[0] if apps else len(blocks)
        blocks[at:at]=[head(1,'參考文獻' if lang=='zh' else 'References'),div]
        notes.append({'type':'references','rule':'REF_CITED','message':'Added a references section before the appendices.'})
    else:
        blocks.append(div)
        notes.append({'type':'references','rule':'REF_CITED','message':'Reference list appended at the end of the fragment; place {{REFERENCES}} to choose its position.'})

# ---------------- OOXML formatting ----------------

def font_props(rp,cfg,size=12,color=True):
    f=child(rp,'w:rFonts')
    for k in list(f.attrib):
        if k.endswith('Theme'): del f.attrib[k]
    for name in ('ascii','hAnsi','cs'): f.set(q('w:'+name),cfg['font_en'])
    f.set(q('w:eastAsia'),cfg['font_zh'])
    child(rp,'w:sz').set(q('w:val'),str(round(size*2)))
    child(rp,'w:szCs').set(q('w:val'),str(round(size*2)))
    if color:
        c=child(rp,'w:color'); c.attrib.clear(); c.set(q('w:val'),'000000')

def set_indent(pp,first_chars=None,left=None,hanging=None):
    ind=child(pp,'w:ind')
    for k in list(ind.attrib): del ind.attrib[k]
    if left is not None: ind.set(q('w:left'),str(left));ind.set(q('w:leftChars'),'0')
    if hanging is not None:
        # hanging and firstLine exclude each other; hangingChars=0 cancels an inherited character indent.
        ind.set(q('w:hangingChars'),'0');ind.set(q('w:hanging'),str(hanging));return
    if first_chars is not None:
        ind.set(q('w:firstLineChars'),str(int(first_chars*100)));ind.set(q('w:firstLine'),str(int(first_chars*240)))
    else:
        ind.set(q('w:firstLineChars'),'0');ind.set(q('w:firstLine'),'0')

def xml_style(d,name,sid=None):
    st=d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH) if name not in d.styles else d.styles[name]
    return st

def make_reference(path,cfg,lang):
    d=Document(); s=d.sections[0]
    s.page_width=Cm(21);s.page_height=Cm(29.7)
    s.top_margin=Cm(3);s.bottom_margin=Cm(2);s.left_margin=Cm(3);s.right_margin=Cm(3)
    s.header_distance=Cm(cfg['header_distance_cm']);s.footer_distance=Cm(cfg['footer_distance_cm'])
    for name in ('Body Text','First Paragraph','Compact','Image Caption','Table Caption','Captioned Figure','Source Code','Bibliography','BIME TOC Title','BIME Doc Title','BIME Cover','BIME Title Page','BIME Signature'):
        if name not in d.styles: d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
    for name in ('toc 1','toc 2','toc 3'):
        # Built-in names, so Word uses them when it fills the TOC field.
        if name not in d.styles: d.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH,builtin=True)
    multiple=1.5 if lang=='zh' else 2.0
    for style in d.styles:
        if style.type not in (WD_STYLE_TYPE.PARAGRAPH,WD_STYLE_TYPE.CHARACTER): continue
        font_props(style.element.get_or_add_rPr(),cfg,12)
        if style.type==WD_STYLE_TYPE.PARAGRAPH:
            style.paragraph_format.line_spacing=multiple
            style.paragraph_format.space_after=Pt(cfg['paragraph_after_pt'])
    # Friend template: heading 1 18 pt bold centred, before 12 pt after 6 pt; heading 2/3 14 pt bold.
    for i,size in enumerate(cfg['heading_sizes_pt'],1):
        st=d.styles[f'Heading {i}'];font_props(st.element.get_or_add_rPr(),cfg,size)
        st.font.bold=True;st.font.italic=False;st.paragraph_format.keep_with_next=True;st.paragraph_format.keep_together=True
        st.paragraph_format.space_before=Pt(12);st.paragraph_format.space_after=Pt(6)
        set_indent(st.element.get_or_add_pPr())
        if i==1: st.paragraph_format.alignment=1
    for name in ('BIME TOC Title','BIME Doc Title'):
        st=d.styles[name];font_props(st.element.get_or_add_rPr(),cfg,cfg['front_title_size_pt']);st.font.bold=True
        st.paragraph_format.alignment=1;st.paragraph_format.keep_with_next=True;st.paragraph_format.space_before=Pt(12);st.paragraph_format.space_after=Pt(6);set_indent(st.element.get_or_add_pPr())
    for name in ('Body Text','First Paragraph'):
        set_indent(d.styles[name].element.get_or_add_pPr(),cfg['first_line_indent_chars'] or None)
    for name in ('Image Caption','Table Caption','Captioned Figure'):
        st=d.styles[name];st.paragraph_format.alignment=1;st.font.bold=False;st.font.italic=False;set_indent(st.element.get_or_add_pPr())
        if name!='Image Caption': st.paragraph_format.keep_with_next=True
    set_indent(d.styles['Compact'].element.get_or_add_pPr())
    set_indent(d.styles['Bibliography'].element.get_or_add_pPr(),None,left=480,hanging=480)
    for i,name in enumerate(('toc 1','toc 2','toc 3')):
        pp=d.styles[name].element.get_or_add_pPr();tabs=child(pp,'w:tabs')
        tab=el('w:tab',val='right',leader='dot',pos=str(TEXT_WIDTH_TWIPS));tabs.append(tab)
        set_indent(pp,None,left=480*i if i else None)
    for name in ('BIME Cover','BIME Title Page','BIME Signature'):
        set_indent(d.styles[name].element.get_or_add_pPr());d.styles[name].paragraph_format.alignment=1
    # Pandoc gives every table the style named "Table"; without it Word draws no borders.
    # Friend template: Table Grid borders (single, 0.5 pt) and centred tables (「表格」樣式).
    st=d.styles['Table'] if 'Table' in d.styles else d.styles.add_style('Table',WD_STYLE_TYPE.TABLE)
    tblpr=st.element.find(q('w:tblPr'))
    if tblpr is None: tblpr=insert_ordered(st.element,el('w:tblPr'))
    for old in tblpr.findall(q('w:tblBorders')): tblpr.remove(old)
    borders=el('w:tblBorders')
    for side in ('top','left','bottom','right','insideH','insideV'):
        b=el('w:'+side);b.set(q('w:val'),'single');b.set(q('w:sz'),'4');b.set(q('w:space'),'0');b.set(q('w:color'),'auto');borders.append(b)
    insert_ordered(tblpr,borders)
    d.core_properties.title='';d.core_properties.author='';d.core_properties.subject=''
    d.save(path)

def add_field(paragraph,instruction,placeholder='1'):
    ppr=paragraph.find(q('w:pPr'))
    for c in list(paragraph):
        if c is not ppr: paragraph.remove(c)
    r=el('w:r');r.append(el('w:fldChar',fldCharType='begin',dirty='true'));paragraph.append(r)
    r=el('w:r');ins=el('w:instrText');ins.set('{http://www.w3.org/XML/1998/namespace}space','preserve');ins.text=' '+instruction+' ';r.append(ins);paragraph.append(r)
    r=el('w:r');r.append(el('w:fldChar',fldCharType='separate'));paragraph.append(r)
    r=el('w:r');t=el('w:t');t.text=placeholder;r.append(t);paragraph.append(r)
    r=el('w:r');r.append(el('w:fldChar',fldCharType='end'));paragraph.append(r)

def add_footer(pkg,cfg):
    # Page number centred at the bottom (二.4, 二.5); 10 pt as in the friend template; no indent, no trailing paragraph.
    footer=E.Element(q('w:ftr'),nsmap={'w':W,'r':R});p=el('w:p');pp=el('w:pPr');p.append(pp)
    child(pp,'w:snapToGrid').set(q('w:val'),'0')
    sp=child(pp,'w:spacing');sp.set(q('w:line'),'360');sp.set(q('w:lineRule'),'auto');sp.set(q('w:after'),'0');sp.set(q('w:before'),'0')
    set_indent(pp);child(pp,'w:jc').set(q('w:val'),'center')
    add_field(p,'PAGE');footer.append(p)
    for r in p.findall(q('w:r')): font_props(child(r,'w:rPr'),cfg,cfg['page_number_size_pt'])
    name='word/bimeFooter.xml';pkg.setxml(name,footer)
    rels=pkg.getxml('word/_rels/document.xml.rels')
    if rels is None: rels=E.Element('{'+REL+'}Relationships',nsmap={None:REL})
    ids={r.get('Id') for r in rels};i=1
    while f'rIdBime{i}' in ids: i+=1
    rid=f'rIdBime{i}';n=E.SubElement(rels,'{'+REL+'}Relationship');n.set('Id',rid);n.set('Type',R+'/footer');n.set('Target','bimeFooter.xml')
    pkg.setxml('word/_rels/document.xml.rels',rels)
    types=pkg.getxml('[Content_Types].xml');n=E.SubElement(types,'{'+CT+'}Override');n.set('PartName','/'+name);n.set('ContentType','application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml');pkg.setxml('[Content_Types].xml',types)
    return rid

def split_tabs(p):
    for t in p.xpath('.//w:t',namespaces=NS):
        if not t.text or '\t' not in t.text: continue
        run=t.getparent();pieces=t.text.split('\t');t.text=pieces[0]
        if pieces[0]=='' : t.getparent().remove(t)
        at=run
        for piece in pieces[1:]:
            new=copy.deepcopy(run)
            for c in list(new):
                if c.tag!=q('w:rPr'): new.remove(c)
            new.append(el('w:tab'))
            if piece:
                nt=el('w:t');nt.text=piece;nt.set('{http://www.w3.org/XML/1998/namespace}space','preserve');new.append(nt)
            at.addnext(new);at=new

# ---------- special pages (二.1 samples) ----------

def roc_date(meta):
    y=meta.get('year_roc');m=meta.get('month')
    if (not y or not m) and meta.get('date'):
        hit=re.match(r'^(\d{4})-(\d{1,2})',str(meta['date']))
        if hit: y=int(hit.group(1))-1911;m=int(hit.group(2))
    try: y=int(y);m=int(m)
    except (TypeError,ValueError): return None
    if not 1<=m<=12: return None
    return y,m

def sample_paragraph(style,text_value,size,cfg,*,jc='center',line=('360','auto'),before=None,underline=False,runs=None,first_chars=None,left=None,hanging=None):
    p=el('w:p');pp=el('w:pPr');p.append(pp)
    child(pp,'w:pStyle').set(q('w:val'),style)
    child(pp,'w:snapToGrid').set(q('w:val'),'0')
    sp=child(pp,'w:spacing');sp.set(q('w:line'),line[0]);sp.set(q('w:lineRule'),line[1]);sp.set(q('w:after'),'0')
    if before: sp.set(q('w:before'),str(before))
    set_indent(pp,first_chars,left=left,hanging=hanging)
    child(pp,'w:jc').set(q('w:val'),jc)
    mark=child(pp,'w:rPr');font_props(mark,cfg,size)
    for piece in (runs if runs is not None else ([(text_value,underline)] if text_value else [])):
        value,under=piece
        parts=value.split('\n')
        r=el('w:r');rp=child(r,'w:rPr');font_props(rp,cfg,size)
        if under: child(rp,'w:u').set(q('w:val'),'single')
        for k,part in enumerate(parts):
            if k: r.append(el('w:br'))
            t=el('w:t');t.text=part;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');r.append(t)
        p.append(r)
    return p

def todo(meta,key,label,missing):
    value=meta.get(key)
    if isinstance(value,list): value='\n'.join(str(v) for v in value if v)
    if value: return str(value)
    missing.append(key);return f'[TODO: {label}]'

def cover_page(meta,cfg,style,missing):
    """封面範例 P110–P128: line order, sizes, centred, 1.5 lines, snapToGrid off."""
    doctoral=str(meta.get('degree','master')).lower() in ('doctoral','phd','博士')
    date=roc_date(meta)
    if date is None: missing.append('year_roc/month (or date)')
    date_zh=f'中華民國{date[0]}年{date[1]}月' if date else '中華民國[TODO: 年]年[TODO: 月]月'
    date_en=f'{cite.MONTHS[date[1]-1]} {date[0]+1911}' if date else '[TODO: Month Year]'
    lines=[(DEPARTMENT_ZH,18,None),('博士論文' if doctoral else '碩士論文',18,None),
           (DEPARTMENT_EN[0],14,None),(DEPARTMENT_EN[1],14,None),(DEPARTMENT_EN[2],16,None),
           ('Doctoral Dissertation' if doctoral else 'Master Thesis',16,None),('',18,540),
           (todo(meta,'title_zh','論文中文題目',missing),18,None),(todo(meta,'title_en','論文英文題目',missing),18,None),('',18,None),('',18,None),
           (todo(meta,'author_zh','作者中文姓名',missing),18,None),(todo(meta,'author_en','作者英文姓名',missing),18,None),('',18,None),
           ('指導教授：'+todo(meta,'advisor_zh','指導教授姓名 博士',missing),18,None),('Advisor: '+todo(meta,'advisor_en','Advisor name, Ph.D.',missing),18,None),('',18,None),
           (date_zh+'\n'+date_en,18,None)]
    return [sample_paragraph(style,t,size,cfg,before=before) for t,size,before in lines]

def signature_page(meta,cfg,missing):
    """第一頁（口試委員會審定書）範例 P131–P149."""
    doctoral=str(meta.get('degree','master')).lower() in ('doctoral','phd','博士')
    degree='博士' if doctoral else '碩士'
    auto=('100','atLeast');sign=('500','atLeast')
    defense=meta.get('defense_date');hit=re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$',str(defense or ''))
    when=f'民國{int(hit.group(1))-1911}年{int(hit.group(2))}月{int(hit.group(3))}日' if hit else '民國○○年○○月○○日'
    if not hit: missing.append('defense_date')
    author=todo(meta,'author_zh','作者中文姓名',missing);sid=todo(meta,'student_id','學號',missing)
    title=todo(meta,'title_zh','論文中文題目',missing)+'\n'+todo(meta,'title_en','論文英文題目',missing)
    body=f'本論文係{author}君（{sid}）在國立臺灣大學生物機電工程學系完成之{degree}學位論文，於{when}承下列考試委員審查通過及口試及格，特此證明'
    blank=('　'*8+'  ',True);gap=('     ',False)
    out=[sample_paragraph('BIMESignature',f'國立臺灣大學{degree}學位論文',24,cfg,line=('240','auto')),
         sample_paragraph('BIMESignature','口試委員會審定書',26,cfg,line=('240','auto')),
         sample_paragraph('BIMESignature',title,20,cfg,line=('240','atLeast'),before=100),
         sample_paragraph('BIMESignature','',16,cfg,jc='both',line=auto),
         sample_paragraph('BIMESignature',body,16,cfg,jc='both',line=('240','atLeast'),first_chars=2),
         sample_paragraph('BIMESignature','',16,cfg,jc='both',line=auto),
         sample_paragraph('BIMESignature','口試委員：',16,cfg,jc='both',line=('240','atLeast')),
         sample_paragraph('BIMESignature',None,16,cfg,jc='both',line=sign,left=3280,hanging=1600,runs=[('　'*16+'（簽名）',True),('\n（指導教授）',False)])]
    for _ in range(4):
        out.append(sample_paragraph('BIMESignature','',16,cfg,jc='both',line=sign,left=3280,hanging=1600))
        out.append(sample_paragraph('BIMESignature',None,16,cfg,jc='both',line=sign,left=3280,hanging=1600,runs=[blank,gap,blank]))
    out.append(sample_paragraph('BIMESignature','',16,cfg,jc='both',line=sign))
    out.append(sample_paragraph('BIMESignature',None,16,cfg,jc='both',line=sign,runs=[('系主任、所長  ',False),('　'*11+'（簽名）',True)]))
    missing.append('committee signatures (left blank by design)')
    return out

def sect_for(base,role,rid,origin,reset):
    s=copy.deepcopy(base)
    for x in list(s):
        if x.tag in (q('w:footerReference'),q('w:headerReference'),q('w:pgNumType'),q('w:titlePg')): s.remove(x)
    if numbered(role,origin):
        f=el('w:footerReference',type='default');f.set(q('r:id'),rid);insert_ordered(s,f)
        n=child(s,'w:pgNumType');n.set(q('w:fmt'),'lowerRoman' if role in FRONT else 'decimal')
        if reset: n.set(q('w:start'),'1')
    return s

def numbered(role,origin):
    return role not in ('cover','title') and not (role=='signature' and origin=='acknowledgements')

def attach_break(pkg,p,sectpr):
    """Put the section break on the paragraph before p, so no empty paragraph can spill onto a blank page."""
    at=p
    while at.getprevious() is not None and at.getprevious().tag in (q('w:bookmarkStart'),q('w:bookmarkEnd')): at=at.getprevious()
    prev=at.getprevious()
    if prev is not None and prev.tag==q('w:p') and prev.find('w:pPr/w:sectPr',NS) is None:
        pp=child(prev,'w:pPr');insert_ordered(pp,sectpr);return
    bp=el('w:p');bpp=el('w:pPr');bp.append(bpp);insert_ordered(bpp,sectpr);at.addprevious(bp)

def prefill_list(pkg,placeholder,token,instruction,cfg):
    """Write the TOC/LOF/LOT result now: each entry is a hyperlink to a bookmark on its heading or caption,
    so the list is clickable before Word updates it. Page numbers are PAGEREF fields Word fills on update."""
    if token=='{{TOC}}':
        wanted={'Heading1':'toc1','Heading2':'toc2','Heading3':'toc3'}
    else:
        wanted={'ImageCaption' if token=='{{LOF}}' else 'TableCaption':'toc1'}
    targets=[]
    for p in pkg.body.iter(q('w:p')):
        st=p.find('w:pPr/w:pStyle',NS)
        sid=st.get(q('w:val')) if st is not None else None
        if sid in wanted and text(p).strip():targets.append((p,wanted[sid]))
    if not targets:return 0
    ids=[int(b.get(q('w:id'))) for b in pkg.doc.iter(q('w:bookmarkStart')) if (b.get(q('w:id')) or '').isdigit()]
    next_id=max(ids+[0])+1
    names={b.get(q('w:name')) for b in pkg.doc.iter(q('w:bookmarkStart'))}
    def run(*children,size=12):
        r=el('w:r');font_props(child(r,'w:rPr'),cfg,size)
        for c in children:r.append(c)
        return r
    def t_node(value):
        n=el('w:t');n.text=value;n.set('{http://www.w3.org/XML/1998/namespace}space','preserve');return n
    entries=[]
    for n,(p,style) in enumerate(targets,1):
        name=f'_TocBIME{n:05d}'
        while name in names:name+='x'
        names.add(name)
        start=el('w:bookmarkStart',id=str(next_id));start.set(q('w:name'),name);end=el('w:bookmarkEnd',id=str(next_id));next_id+=1
        pp=p.find(q('w:pPr'))
        (pp.addnext(start) if pp is not None else p.insert(0,start));p.append(end)
        e=el('w:p');ep=el('w:pPr');e.append(ep);ep.append(el('w:pStyle',val=style))
        tabs=el('w:tabs');tabs.append(el('w:tab',val='right',leader='dot',pos=str(TEXT_WIDTH_TWIPS)));ep.append(tabs)
        link=el('w:hyperlink',anchor=name,history='1')
        link.append(run(t_node(re.sub(r'[\t\n ]+',' ',text(p)).strip())))
        link.append(run(el('w:tab')))
        instr=el('w:instrText');instr.set('{http://www.w3.org/XML/1998/namespace}space','preserve');instr.text=f' PAGEREF {name} \\h '
        link.append(run(el('w:fldChar',fldCharType='begin')));link.append(run(instr))
        link.append(run(el('w:fldChar',fldCharType='separate')));link.append(run(el('w:fldChar',fldCharType='end')))
        e.append(link);entries.append(e)
    first=entries[0];ins=el('w:instrText');ins.set('{http://www.w3.org/XML/1998/namespace}space','preserve');ins.text=' '+instruction+' '
    for k,node in enumerate([run(el('w:fldChar',fldCharType='begin',dirty='true')),run(ins),run(el('w:fldChar',fldCharType='separate'))]):
        first.insert(1+k,node)
    entries[-1].append(run(el('w:fldChar',fldCharType='end')))
    for e in entries:placeholder.addprevious(e)
    placeholder.getparent().remove(placeholder)
    return len(entries)

def apply_format(pkg,cfg,scope,notes,*,lang='zh',meta=None,for_insert=False):
    meta=meta or {}
    records=paragraph_records(pkg,scope);pending_lists=[]
    line='360' if lang=='zh' else '480'
    for rec in records:
        p=rec['element'];pp=child(p,'w:pPr'); t=rec['text'];level=rec['level']
        in_table=bool(p.xpath('ancestor::w:tbl',namespaces=NS))
        sid=rec['style']
        spacing=child(pp,'w:spacing');spacing.set(q('w:line'),line);spacing.set(q('w:lineRule'),'auto')
        spacing.set(q('w:after'),str(round(cfg['paragraph_after_pt']*20)))
        prose=rec['kind']=='body' and not in_table and pp.find(q('w:numPr')) is None and sid in ('BodyText','FirstParagraph','Normal')
        if prose and not re.match(r'^\s*(關鍵[詞字]|关键词|Key\s*words?)\s*[:：]',t,re.I):
            set_indent(pp,cfg['first_line_indent_chars'] or None)
        elif rec['kind'] in ('caption','heading') or in_table or re.match(r'^\s*(關鍵[詞字]|关键词|Key\s*words?)\s*[:：]',t,re.I):
            set_indent(pp)
        size=cfg['heading_sizes_pt'][min(level,6)-1] if level else 12
        is_toc_title=level==1 and role_title(t)=='toc' and not for_insert
        if is_toc_title or sid=='BIMEDocTitle': size=cfg['front_title_size_pt']
        for run in p.xpath('.//w:r',namespaces=NS): font_props(child(run,'w:rPr'),cfg,size)
        if level:
            child(pp,'w:keepNext').set(q('w:val'),'1')
            if level==1 and cfg['chapter_page_break'] and not for_insert:
                child(pp,'w:pageBreakBefore').set(q('w:val'),'1')
        if rec['kind']=='caption':
            m=caption(t)
            if m:
                is_table=m.group(1).lower() in ('表','table')
                child(pp,'w:pStyle').set(q('w:val'),'TableCaption' if is_table else 'ImageCaption')
                if is_table: child(pp,'w:keepNext').set(q('w:val'),'1')
                child(pp,'w:jc').set(q('w:val'),'center')
                for run in p.xpath('.//w:r',namespaces=NS):
                    b=run.find('w:rPr/w:b',NS)
                    if b is not None: b.getparent().remove(b)
        if p.xpath('.//w:drawing',namespaces=NS):
            child(pp,'w:keepNext').set(q('w:val'),'1');child(pp,'w:jc').set(q('w:val'),'center');set_indent(pp)
        if is_toc_title:
            child(pp,'w:pStyle').set(q('w:val'),'BIMETOCTitle')
            label=el('w:p');lpp=el('w:pPr');label.append(lpp);child(lpp,'w:jc').set(q('w:val'),'right');set_indent(lpp)
            lsp=child(lpp,'w:spacing');lsp.set(q('w:line'),line);lsp.set(q('w:lineRule'),'auto');lsp.set(q('w:after'),'0')
            r=el('w:r');font_props(child(r,'w:rPr'),cfg,12);tt=el('w:t');tt.text='頁數' if lang=='zh' else 'Page';r.append(tt);label.append(r)
            p.addnext(label)
        if t in ('{{TOC}}','{{LOF}}','{{LOT}}'):
            extra=' \\l "1-1"' if cfg['pagination_origin']=='signature' else ''
            field={'{{TOC}}':'TOC \\o "1-3" \\h \\z \\u'+extra,'{{LOF}}':'TOC \\h \\z \\t "Image Caption,1"','{{LOT}}':'TOC \\h \\z \\t "Table Caption,1"'}[t]
            add_field(p,field,'請在 Word 更新欄位' if lang=='zh' else 'Update this field in Word')
            set_indent(pp)
            pending_lists.append((p,t,field))
            notes.append({'type':'field_update','message':f'{t}: entries link to their headings already; update fields in Word to fill in page numbers.'})
        split_tabs(p)
    for tbl in pkg.body.iter(q('w:tbl')):
        tp=tbl.find(q('w:tblPr'))
        if tp is not None:
            child(tp,'w:jc').set(q('w:val'),'center')
    for placeholder,token,instruction in pending_lists:
        prefill_list(pkg,placeholder,token,instruction,cfg)
    for name in ('word/footnotes.xml','word/endnotes.xml'):
        rt=pkg.getxml(name)
        if rt is not None:
            for p in rt.findall('.//'+q('w:p')):
                for run in p.findall('.//'+q('w:r')): font_props(child(run,'w:rPr'),cfg,12)
            pkg.setxml(name,rt)
    base=pkg.body.find(q('w:sectPr'))
    if base is None: base=el('w:sectPr');pkg.body.append(base)
    page=child(base,'w:pgSz');page.set(q('w:w'),'11906');page.set(q('w:h'),'16838')
    mar=child(base,'w:pgMar')
    header=round(cfg['header_distance_cm']/2.54*1440);footer_d=round(cfg['footer_distance_cm']/2.54*1440)
    for k,v in {'top':1701,'right':1701,'bottom':1134,'left':1701,'header':header,'footer':footer_d,'gutter':0}.items(): mar.set(q('w:'+k),str(v))
    for n in base.findall(q('w:docGrid')): base.remove(n)
    if cfg['document_grid']:
        g=child(base,'w:docGrid');g.set(q('w:type'),'lines');g.set(q('w:linePitch'),'360')
    rid=add_footer(pkg,cfg)
    origin=cfg['pagination_origin']
    points=[]
    if scope=='thesis' and not for_insert:
        missing=[]
        pages=[('cover',cover_page(meta,cfg,'BIMECover',missing))]
        if cfg['title_page']=='same_as_cover' and meta.get('title_page',True) is not False:
            pages.append(('title',cover_page(meta,cfg,'BIMETitlePage',[])))
        pages.append(('signature',signature_page(meta,cfg,missing)))
        first=pkg.body[0] if len(pkg.body) else None
        for role,paras in pages:
            for para in paras:
                if first is not None: first.addprevious(para)
                else: pkg.body.insert(len(pkg.body)-1,para)
            points.append((paras[0],role))
        if origin=='signature':
            add_tc(points[-1][0],'口試委員審定書')
        if missing: notes.append({'type':'special_pages','rule':'SPECIAL_PAGES','message':'Cover/signature fields not supplied; [TODO] placeholders were written.','missing':sorted(set(missing))})
        notes.append({'type':'special_pages','rule':'SPECIAL_PAGES','message':'Cover and 口試委員會審定書 follow the regulation samples; the title page copies the cover because no source shows its layout.' if cfg['title_page']=='same_as_cover' else 'Cover and 口試委員會審定書 follow the regulation samples.'})
        seen_body=False
        for rec in records:
            if rec['level']!=1: continue
            role=role_title(rec['text'])
            if role in FRONT: points.append((rec['element'],role))
            elif not seen_body and role not in ('references','appendix'):
                points.append((rec['element'],'body'));seen_body=True
    elif cfg['cover'] and not for_insert:
        # A fragment (e.g. the proposal) may open with the regulation cover; it gets its own
        # unnumbered page and the rest of the document is numbered from 1.
        missing=[];paras=cover_page(meta,cfg,'BIMECover',missing)
        first=next((r['element'] for r in records if r['text']),None)
        for para in paras:
            if first is not None: first.addprevious(para)
            else: pkg.body.insert(len(pkg.body)-1,para)
        points.append((paras[0],'cover'))
        if first is not None: points.append((first,'body'))
        if missing: notes.append({'type':'special_pages','rule':'SPECIAL_PAGES','message':'Cover fields not supplied; [TODO] placeholders were written.','missing':sorted(set(missing))})
        notes.append({'type':'special_pages','rule':'SPECIAL_PAGES','message':'The cover follows the regulation sample (封面範例) and is not numbered; the pages after it are numbered from 1.'})
    if points:
        front_started=False;body_started=False;sections=[]
        for j,(p,role) in enumerate(points):
            reset=False
            if numbered(role,origin):
                if role in FRONT and not front_started: reset=True;front_started=True
                if role=='body' and not body_started: reset=True;body_started=True
            sections.append((p,role,reset))
        for j,(p,role,reset) in enumerate(sections):
            br=p.find('w:pPr/w:pageBreakBefore',NS)
            if br is not None: br.getparent().remove(br)
            if j: attach_break(pkg,p,sect_for(base,sections[j-1][1],rid,origin,sections[j-1][2]))
        pkg.body.replace(base,sect_for(base,sections[-1][1],rid,origin,sections[-1][2]))
    else:
        pkg.body.replace(base,sect_for(base,'body',rid,origin,True))
        first=next((r for r in records if r['text']),None)
        if first:
            n=first['element'].find('w:pPr/w:pageBreakBefore',NS)
            if n is not None: n.getparent().remove(n)
    settings=pkg.getxml('word/settings.xml')
    if settings is None: settings=E.Element(q('w:settings'),nsmap={'w':W})
    child(settings,'w:updateFields').set(q('w:val'),'true')
    zoom=settings.find(q('w:zoom'))
    if zoom is not None and zoom.get(q('w:percent')) is None: zoom.set(q('w:percent'),'100')
    pkg.setxml('word/settings.xml',settings)
    declare_media_defaults(pkg)

def add_tc(p,label):
    # A TC entry lets the TOC list the signature page when it carries page i (目錄範例).
    r=el('w:r');r.append(el('w:fldChar',fldCharType='begin'));p.append(r)
    r=el('w:r');ins=el('w:instrText');ins.set('{http://www.w3.org/XML/1998/namespace}space','preserve');ins.text=f' TC "{label}" \\l 1 ';r.append(ins);p.append(r)
    r=el('w:r');r.append(el('w:fldChar',fldCharType='end'));p.append(r)

MEDIA_TYPES={'png':'image/png','jpeg':'image/jpeg','jpg':'image/jpeg','gif':'image/gif','emf':'image/x-emf','wmf':'image/x-wmf','svg':'image/svg+xml','tif':'image/tiff','tiff':'image/tiff','bmp':'image/bmp'}

def declare_media_defaults(pkg):
    # Pandoc declares media by Override, which is valid; a Default entry also satisfies strict checkers.
    types=pkg.getxml('[Content_Types].xml')
    have={n.get('Extension','').lower() for n in types if n.tag=='{'+CT+'}Default'}
    for name in pkg.parts:
        ext=name.rsplit('.',1)[-1].lower() if '.' in name else ''
        if name.startswith('word/') and ext in MEDIA_TYPES and ext not in have:
            n=E.Element('{'+CT+'}Default');n.set('Extension',ext);n.set('ContentType',MEDIA_TYPES[ext])
            first=next((i for i,c in enumerate(types) if c.tag=='{'+CT+'}Override'),len(types));types.insert(first,n);have.add(ext)
    pkg.setxml('[Content_Types].xml',types)


def convert(source: Path, output: Path, cfg,scope='fragment', *, overwrite=False, for_insert=False, bibliography=None):
    source=Path(source); output=Path(output)
    if not source.is_file(): raise BimeError('Markdown file does not exist: '+str(source))
    if output.resolve()==source.resolve(): raise BimeError('Input and output cannot be the same file.')
    if output.exists() and not overwrite: raise BimeError('Output exists: '+str(output))
    bibliography=bibliography or cfg.get('bibliography')
    ast,notes,meta,lang,refs=prepare_ast(source,cfg,scope,for_insert=for_insert,bibliography=bibliography)
    with tempfile.TemporaryDirectory(prefix='bime-convert-') as td:
        td=Path(td);ref=td/'reference.docx';raw=td/'raw.docx';make_reference(ref,cfg,lang)
        _,warn=run_pandoc(['--from','json','--to','docx','--standalone','--reference-doc',str(ref),'--resource-path',str(source.parent.resolve()),'--no-highlight','--output',str(raw)],data=json.dumps(ast).encode('utf-8'),cwd=source.parent)
        if warn: notes.append({'type':'pandoc_warning','message':warn})
        pkg=Package(raw);apply_format(pkg,cfg,scope,notes,lang=lang,meta=meta,for_insert=for_insert);pkg.save(output,overwrite)
    return {'operation':'convert','source':str(source),'source_sha256':sha(source),'output':str(output),'output_sha256':sha(output),'scope':scope,'language':lang,'references':refs,'decisions':notes,'policy':cfg,'layout_verified':False,'note':'OOXML formatting is applied. Render and inspect before certifying visual layout.'}
