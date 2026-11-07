"""Safe OPC access, formatting resolution, and shared policy utilities."""
from __future__ import annotations
import copy, hashlib, json, os, re, tempfile, zipfile
from pathlib import Path
from typing import Any
from lxml import etree as E
from .ooxml_order import insert_ordered, order_errors

ROOT = Path(__file__).resolve().parents[2]
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
NS = {'w': W, 'r': R, 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
      'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math', 'rel': REL}
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
LATIN = re.compile(r'[A-Za-z]')

class BimeError(Exception):
    """Expected user-facing validation error, never a silent partial write."""

def q(name: str) -> str:
    prefix, local = name.split(':', 1)
    return '{' + NS[prefix] + '}' + local

def el(name: str, **attrs: Any):
    node = E.Element(q(name))
    for key, val in attrs.items(): node.set(q('w:' + key), str(val))
    return node

def xml(data: bytes):
    return E.fromstring(data, E.XMLParser(resolve_entities=False, no_network=True, huge_tree=False))

def dump(root) -> bytes:
    return E.tostring(root, encoding='UTF-8', xml_declaration=True, standalone=True)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def text(node) -> str:
    # Include hyperlinks, fields' cached text, smart tags and tab characters; exclude deleted text.
    parts = node.xpath('.//w:t[not(ancestor::w:del)] | .//w:tab[not(ancestor::w:del)][not(ancestor::w:tabs)]', namespaces=NS)
    return ''.join((n.text or '') if n.tag == q('w:t') else '\t' for n in parts)

def child(parent, name):
    # Word rejects out-of-order children, so new elements go to their schema position.
    got = parent.find(q(name))
    if got is None:
        got = insert_ordered(parent, el(name))
    return got

def load_config(path: Path | None = None) -> dict:
    cfg = json.loads((ROOT / 'assets/defaults.json').read_text(encoding='utf-8'))
    if path:
        supplied = json.loads(path.read_text(encoding='utf-8-sig'))
        def merge(a, b):
            for k, v in b.items():
                if k not in a: raise BimeError(f'Unknown configuration key: {k}')
                if k in ('role_overrides', 'section_roles') and isinstance(v, dict): a[k].update(v)
                elif isinstance(a[k], dict) and isinstance(v, dict): merge(a[k], v)
                else: a[k] = v
        merge(cfg, supplied)
    if cfg['language'] not in ('auto', 'zh', 'en'): raise BimeError('language must be auto, zh, or en')
    if cfg['heading_separator'] not in ('.', '-'): raise BimeError('heading_separator must be . or -')
    if cfg['pagination_origin'] not in ('unresolved', 'acknowledgements', 'signature'):
        raise BimeError('pagination_origin must be unresolved, acknowledgements, or signature')
    if not isinstance(cfg['font_zh'], str) or not cfg['font_zh'].strip(): raise BimeError('font_zh is empty')
    if cfg['body_size_pt'] != 12: raise BimeError('body_size_pt is source-derived and must be 12')
    if not isinstance(cfg['heading_sizes_pt'],list) or len(cfg['heading_sizes_pt'])!=6 or any(not isinstance(x,(int,float)) or not 1<=x<=72 for x in cfg['heading_sizes_pt']):
        raise BimeError('heading_sizes_pt must contain six sizes between 1 and 72 pt.')
    if cfg['shift_heading_level'] not in (0,-1): raise BimeError('shift_heading_level must be 0 or -1')
    for key in ('auto_number_headings','chapter_page_break','pagination_confirmed','document_grid','drop_todo','cover'):
        if not isinstance(cfg[key],bool): raise BimeError(key+' must be a boolean.')
    for key in ('paragraph_after_pt','first_line_indent_chars','header_distance_cm','footer_distance_cm'):
        if not isinstance(cfg[key],(int,float)) or cfg[key]<0: raise BimeError(key+' must be nonnegative.')
    for key in ('front_title_size_pt','page_number_size_pt'):
        if not isinstance(cfg[key],(int,float)) or not 6<=cfg[key]<=72: raise BimeError(key+' must be between 6 and 72 pt.')
    if cfg['footer_distance_cm']>=2: raise BimeError('footer_distance_cm must stay below the 2 cm bottom margin (regulation 二.5).')
    if cfg['title_page'] not in ('same_as_cover','omit'): raise BimeError('title_page must be same_as_cover or omit')
    if cfg['bibliography'] is not None and not isinstance(cfg['bibliography'],str): raise BimeError('bibliography must be a path string or null')
    if not isinstance(cfg['font_en'],str) or not cfg['font_en'].strip():raise BimeError('font_en is empty')
    for key in ('role_overrides','section_roles'):
        if not isinstance(cfg[key],dict) or any(not str(k).isdigit() or not isinstance(v,str) for k,v in cfg[key].items()):raise BimeError(key+' must map positive index strings to role strings.')
    if cfg['reference_manifest'] is not None and not isinstance(cfg['reference_manifest'],str):raise BimeError('reference_manifest must be a path string or null')
    return cfg

class Package:
    """Never extracts ZIP entries onto disk; reject unsafe or oversized packages."""
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.suffix.lower() != '.docx': raise BimeError('Only .docx is supported; convert .doc/.docm explicitly first.')
        try:
            with zipfile.ZipFile(self.path) as z:
                infos = z.infolist()
                if len(infos) > 10000 or sum(i.file_size for i in infos) > 512*1024*1024:
                    raise BimeError('DOCX exceeds safe package limits (10,000 parts / 512 MiB).')
                names = [i.filename for i in infos]
                if len(names) != len(set(names)): raise BimeError('Duplicate ZIP part names.')
                if any(n.startswith('/') or '..' in n.replace('\\','/').split('/') for n in names):
                    raise BimeError('Unsafe ZIP part path.')
                self.parts = {i.filename: z.read(i) for i in infos}
                self.original_parts = dict(self.parts)
        except (zipfile.BadZipFile, RuntimeError) as exc:
            raise BimeError('Invalid, encrypted, or unsupported DOCX package.') from exc
        if 'word/document.xml' not in self.parts: raise BimeError('Missing word/document.xml')
        self.doc = xml(self.parts['word/document.xml'])
        if self.doc.tag != q('w:document'): raise BimeError('Strict/unknown OOXML namespace is not supported; do not silently convert.')
        self.body = self.doc.find(q('w:body'))
        if self.body is None: raise BimeError('Missing document body')

    def getxml(self, name: str):
        return xml(self.parts[name]) if name in self.parts else None

    def setxml(self, name: str, node): self.parts[name] = dump(node)

    def save(self, path: Path, overwrite: bool = False):
        path = Path(path)
        if path.resolve() == self.path.resolve(): raise BimeError('In-place writes are forbidden. Choose a new output path.')
        if path.exists() and not overwrite: raise BimeError(f'Output exists: {path}; use --overwrite for a different output, never the source.')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.setxml('word/document.xml', self.doc)
        self.check_order()
        fd, tmp = tempfile.mkstemp(prefix='.bime-', suffix='.docx', dir=path.parent); os.close(fd)
        try:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
                for name, data in self.parts.items(): z.writestr(name, data)
            with zipfile.ZipFile(tmp) as z:
                if z.testzip(): raise BimeError('ZIP integrity check failed.')
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def check_order(self):
        """Refuse to write a part whose schema-order errors increased compared with its input."""
        problems = []
        for name, data in self.parts.items():
            if not name.endswith('.xml') or data == self.original_parts.get(name):
                continue
            try:
                new = order_errors(xml(data), name)
                old = order_errors(xml(self.original_parts[name]), name) if name in self.original_parts else []
            except E.XMLSyntaxError:
                continue
            if len(new) > len(old):
                problems.extend(new[:3])
        if problems:
            raise BimeError('Internal OOXML order check failed; nothing was written: ' + '; '.join(f'{p}: {m}' for p, _, m in problems[:5]))

    def writable(self):
        if any(n.startswith('_xmlsignatures/') or 'vbaProject' in n for n in self.parts):
            raise BimeError('Digitally signed or macro-bearing packages must not be modified by this tool.')
        if self.doc.xpath('.//w:ins | .//w:del | .//w:moveFrom | .//w:moveTo', namespaces=NS):
            raise BimeError('Unresolved tracked changes: review them in Word before safe insertion; nothing was modified.')
        settings = self.getxml('word/settings.xml')
        if settings is not None:
            prot = settings.find(q('w:documentProtection'))
            if prot is not None and prot.get(q('w:enforcement'), '0') not in ('0', 'false', 'off'):
                raise BimeError('Document protection is active; tool will not bypass it.')

class Resolver:
    """Resolve direct, character/paragraph style inheritance, and docDefaults.

    Theme fonts/colors are resolved when determinable. Conditional table styles,
    complex-script selection and app font fallback remain explicit review items.
    """
    def __init__(self, pkg: Package):
        self.styles = pkg.getxml('word/styles.xml')
        self.index = {} if self.styles is None else {s.get(q('w:styleId')): s for s in self.styles.findall(q('w:style'))}
        self.default_style = next((sid for sid,s in self.index.items() if s.get(q('w:type')) == 'paragraph' and s.get(q('w:default')) == '1'), 'Normal')
        self.theme = pkg.getxml('word/theme/theme1.xml')

    def chain(self, sid: str | None):
        out, seen = [], set()
        while sid and sid not in seen and sid in self.index:
            seen.add(sid); s = self.index[sid]; out.append(s)
            based = s.find(q('w:basedOn')); sid = based.get(q('w:val')) if based is not None else None
        return out

    def pstyle(self, p):
        n = p.find('w:pPr/w:pStyle', NS)
        return n.get(q('w:val')) if n is not None else self.default_style

    def props(self, p, run=None, kind='rPr'):
        out=[]
        if run is not None:
            rp=run.find(q('w:rPr'))
            if rp is not None:
                out.append(rp)
                sid=rp.find(q('w:rStyle'))
                if sid is not None:
                    out.extend(s.find(q('w:rPr')) for s in self.chain(sid.get(q('w:val'))))
        if kind == 'pPr':
            out.append(p.find(q('w:pPr')))
        out.extend(s.find(q('w:'+kind)) for s in self.chain(self.pstyle(p)))
        if self.styles is not None:
            out.append(self.styles.find(f'w:docDefaults/w:{kind}Default/w:{kind}', NS))
        return [n for n in out if n is not None]

    def prop(self,p,name,attr='val',run=None,kind='rPr'):
        for props in self.props(p,run,kind):
            n=props.find(q('w:'+name))
            if n is not None and n.get(q('w:'+attr)) is not None: return n.get(q('w:'+attr))
        return None

    def font(self,p,run,script):
        attrs=('ascii','hAnsi') if script=='latin' else ('eastAsia',)
        for props in self.props(p,run):
            f=props.find(q('w:rFonts'))
            if f is None: continue
            for attr in attrs:
                theme=f.get(q('w:'+attr+'Theme'))
                if theme:
                    if self.theme is None: return None
                    group='majorFont' if theme.startswith('major') else 'minorFont'
                    tag='latin' if script=='latin' else 'ea'
                    node=self.theme.find(f'.//a:fontScheme/a:{group}/a:{tag}',NS)
                    if node is not None and node.get('typeface'): return node.get('typeface')
                    if script!='latin':
                        node=self.theme.find(f'.//a:fontScheme/a:{group}/a:font[@script="Hant"]',NS)
                        if node is not None: return node.get('typeface')
                    return None
                if f.get(q('w:'+attr)): return f.get(q('w:'+attr))
        return None

    def color(self,p,run):
        """Hex color, 'AUTO' for Word's automatic color (explicit or by default), None if unresolvable."""
        for props in self.props(p,run):
            n=props.find(q('w:color'))
            if n is None: continue
            theme=n.get(q('w:themeColor'))
            if theme:
                aliases={'text1':'dk1','text2':'dk2','background1':'lt1','background2':'lt2'}
                name=aliases.get(theme,theme)
                if self.theme is None: return None
                node=self.theme.find(f'.//a:clrScheme/a:{name}',NS)
                if node is None or len(node)==0: return None
                val=node[0].get('val') if E.QName(node[0]).localname=='srgbClr' else node[0].get('lastClr')
                if n.get(q('w:themeTint')) or n.get(q('w:themeShade')): return None
                return val.upper() if val else None
            value=n.get(q('w:val'))
            if not value or value=='auto': return 'AUTO'
            return value.upper()
        return 'AUTO'

    def style_name(self, sid):
        for s in self.chain(sid):
            nm = s.find(q('w:name'))
            if nm is not None and nm.get(q('w:val')):
                return nm.get(q('w:val'))
        return sid or ''

    def num_pr(self, p):
        """(numId, ilvl) from direct formatting or the paragraph style chain; None when unnumbered."""
        direct = p.find('w:pPr/w:numPr', NS)
        chain = [direct] if direct is not None else []
        chain += [s.find('w:pPr/w:numPr', NS) for s in self.chain(self.pstyle(p))]
        num_id = ilvl = None
        for n in chain:
            if n is None:
                continue
            if num_id is None and n.find(q('w:numId')) is not None:
                num_id = n.find(q('w:numId')).get(q('w:val'))
            if ilvl is None and n.find(q('w:ilvl')) is not None:
                ilvl = n.find(q('w:ilvl')).get(q('w:val'))
        if num_id in (None, '0'):
            return None
        return num_id, int(ilvl) if ilvl and ilvl.isdigit() else None

    def heading_level(self,p):
        level=self.prop(p,'outlineLvl',kind='pPr')
        if level is not None and level.isdigit() and int(level)<9: return int(level)+1
        sid=self.pstyle(p)
        for s in self.chain(sid):
            nm=s.find(q('w:name')); name=nm.get(q('w:val'),'') if nm is not None else ''
            hit=re.search(r'(?:Heading|標題|标题)\s*([1-6])$',name,re.I)
            if hit: return int(hit.group(1))
        return None

ROLE_NAMES={
 'cover':['封面','cover'], 'title':['標題頁','title page'],
 'signature':['簽名頁','口試委員會審定書','口試委員審定書','signature page'],
 'acknowledgements':['誌謝','致謝','acknowledgements','acknowledgments','acknowledgement'],
 'abstract_zh':['中文摘要','摘要'], 'abstract_en':['英文摘要','abstract'],
 'toc':['目錄','table of contents','contents'], 'figures':['圖目錄','list of figures'],
 'tables':['表目錄','list of tables'], 'symbols':['符號說明','nomenclature','list of symbols'],
 'references':['參考文獻','references','bibliography'], 'appendix':['附錄','appendix','appendices']}
FRONT={'cover','title','signature','acknowledgements','abstract_zh','abstract_en','toc','figures','tables','symbols'}
# Paragraph styles the converter gives to generated special pages.
STYLE_ROLES={'BIMECover':'cover','BIMETitlePage':'title','BIMESignature':'signature','BIMETOCTitle':'toc'}
# Regulation 一 lists these chapter functions in this order.
CHAPTER_NAMES=[('前言','introduction'),('文獻探討','literature review'),('材料與方法','materials and methods'),('結果與討論','results and discussion'),('結論','conclusions')]

def role_title(t: str) -> str | None:
    s=re.sub(r'\s+','',t).lower()
    for role,names in ROLE_NAMES.items():
        if s in [re.sub(r'\s+','',n).lower() for n in names]: return role
    if re.match(r'^附錄[一二三四五六七八九十0-9A-Za-z]*$',s) or re.match(r'^appendix[a-z0-9]?$',s): return 'appendix'
    return None

def caption(t: str):
    return re.match(r'^\s*(圖|表|Figure|Table)\s*(\d+)\s*[-－–]\s*(\d+)\s*[.:：、]?\s*(.*)$',t,re.I|re.S)

def caption_like(t: str):
    """Caption numbered with a dot or other separator; 二.3 prescribes 圖1-1／表1-1."""
    return re.match(r'^\s*(圖|表|Figure|Table)\s*(\d+)\s*[.．]\s*(\d+)\b',t,re.I)

ZH_DIGITS='零一二三四五六七八九'

def zh_count(n: int) -> str:
    """Taiwanese counting numerals as Word's taiwaneseCountingThousand renders them."""
    if n <= 0: return str(n)
    if n < 10: return ZH_DIGITS[n]
    if n < 20: return '十' + (ZH_DIGITS[n % 10] if n % 10 else '')
    if n < 100: return ZH_DIGITS[n // 10] + '十' + (ZH_DIGITS[n % 10] if n % 10 else '')
    if n < 1000:
        rest = n % 100
        tail = '' if not rest else (('零' if rest < 10 else ('一' if rest < 20 else '')) + zh_count(rest))
        return ZH_DIGITS[n // 100] + '百' + tail
    return str(n)

def roman(n: int) -> str:
    vals=[(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
    out=''
    for v,sym in vals:
        while n>=v: out+=sym; n-=v
    return out

def format_number(n: int, fmt: str) -> str:
    if fmt in ('decimal', None): return str(n)
    if fmt == 'decimalZero': return f'{n:02d}'
    if fmt in ('taiwaneseCountingThousand','taiwaneseCounting','chineseCounting','chineseCountingThousand','ideographDigital'): return zh_count(n)
    if fmt == 'ideographTraditional': return '甲乙丙丁戊己庚辛壬癸'[(n-1)%10]
    if fmt == 'lowerRoman': return roman(n)
    if fmt == 'upperRoman': return roman(n).upper()
    if fmt == 'lowerLetter': return chr(96 + (n-1) % 26 + 1) * ((n-1)//26 + 1)
    if fmt == 'upperLetter': return chr(64 + (n-1) % 26 + 1) * ((n-1)//26 + 1)
    if fmt in ('none','bullet'): return ''
    return str(n)

class Numbering:
    """Word list numbering, rendered so audits see '第一章', '3.1' and '圖4-1' like the reader does."""
    def __init__(self, pkg: Package, res: Resolver):
        self.res = res; self.levels = {}; self.nums = {}; self.style_levels = {}
        root = pkg.getxml('word/numbering.xml')
        if root is None: return
        abstract = {}
        for a in root.findall(q('w:abstractNum')):
            lv = {}
            for l in a.findall(q('w:lvl')):
                i = int(l.get(q('w:ilvl'), '0'))
                def val(tag, default=None):
                    n = l.find(q('w:' + tag)); return n.get(q('w:val'), default) if n is not None else default
                lv[i] = {'start': int(val('start', '1') or 1), 'fmt': val('numFmt', 'decimal'), 'text': val('lvlText', ''),
                         'lgl': l.find(q('w:isLgl')) is not None, 'restart': val('lvlRestart'), 'suff': val('suff', 'tab'), 'pstyle': val('pStyle')}
            abstract[a.get(q('w:abstractNumId'))] = lv
        for n in root.findall(q('w:num')):
            aid = n.find(q('w:abstractNumId'))
            lv = {k: dict(v) for k, v in abstract.get(aid.get(q('w:val')) if aid is not None else None, {}).items()}
            for o in n.findall(q('w:lvlOverride')):
                i = int(o.get(q('w:ilvl'), '0')); so = o.find(q('w:startOverride'))
                if so is not None and i in lv: lv[i]['start'] = int(so.get(q('w:val'), '1'))
            self.nums[n.get(q('w:numId'))] = {'levels': lv, 'abstract': aid.get(q('w:val')) if aid is not None else None}
        for num_id, info in self.nums.items():
            for i, l in info['levels'].items():
                if l['pstyle']: self.style_levels.setdefault(l['pstyle'], i)
        self.counters = {}

    def label(self, p):
        found = self.res.num_pr(p)
        if not found: return ''
        num_id, ilvl = found
        info = self.nums.get(num_id)
        if not info: return ''
        if ilvl is None: ilvl = self.style_levels.get(self.res.pstyle(p), 0)
        levels = info['levels']; lvl = levels.get(ilvl)
        if lvl is None: return ''
        key = info['abstract'] or num_id
        counts = self.counters.setdefault(key, {})
        counts[ilvl] = counts[ilvl] + 1 if ilvl in counts else lvl['start']
        for deeper, spec in levels.items():
            if deeper <= ilvl or deeper not in counts: continue
            restart = spec['restart']
            if restart is None or (restart.isdigit() and int(restart) != 0 and ilvl < int(restart)):
                del counts[deeper]
        def piece(m):
            i = int(m.group(1)) - 1
            spec = levels.get(i, {'start': 1, 'fmt': 'decimal'})
            n = counts.get(i, spec['start'])
            return format_number(n, 'decimal' if lvl['lgl'] and spec['fmt'] not in ('decimalZero',) else spec['fmt'])
        text = re.sub(r'%([1-9])', piece, lvl['text'])
        if not text: return ''
        return text + {'tab': '\t', 'space': ' ', 'nothing': ''}.get(lvl['suff'], '\t')

def document_language(texts) -> str:
    joined='\n'.join(texts)
    cjk=len(CJK.findall(joined)); words=len(re.findall(r'[A-Za-z]+',joined))
    return 'zh' if cjk >= words else 'en'

def paragraph_records(pkg: Package, scope='fragment'):
    res=Resolver(pkg); numbering=Numbering(pkg,res); records=[]; current='body'; has_body=False; role_level=1
    for index,block in enumerate(pkg.body):
        if block.tag not in (q('w:p'),q('w:tbl'),q('w:sdt')): continue
        plist=[block] if block.tag==q('w:p') else block.xpath('.//w:p',namespaces=NS)
        for p in plist:
            t=text(p).strip(); level=res.heading_level(p); label=numbering.label(p)
            display=(label+t).strip() if label else t
            sid=res.pstyle(p); sname=res.style_name(sid)
            # TOC/LOF/LOT entries repeat heading text; they never start a region.
            is_entry=bool(re.match(r'^(toc\s*\d|table of figures)$',sname.strip(),re.I))
            role=role_title(t) if block.tag==q('w:p') and not is_entry else None
            if sid in STYLE_ROLES: current=STYLE_ROLES[sid]
            elif role and (level or (len(t)<50 and scope=='thesis')): current=role; role_level=level or 1
            elif level==1 or (level and current!='body' and level<=role_level): current='body'; has_body=True
            elif current in ('cover','title','signature') and sid not in STYLE_ROLES and block.tag==q('w:p') and t: current='body'
            cap=caption(display)
            cap_adjacent=False
            if cap and block.tag==q('w:p'):
                siblings=list(pkg.body)
                direction=1 if cap.group(1).lower() in ('表','table') else -1
                j=index+direction
                while 0<=j<len(siblings):
                    other=siblings[j]
                    meaningful=other.tag==q('w:tbl') or other.tag==q('w:p') and (text(other).strip() or other.xpath('.//w:drawing | .//w:pict',namespaces=NS))
                    if meaningful:
                        cap_adjacent=other.tag==q('w:tbl') if direction==1 else bool(other.xpath('.//w:drawing | .//w:pict',namespaces=NS))
                        break
                    j+=direction
            kind='heading' if level else ('caption' if cap_adjacent else ('table' if block.tag==q('w:tbl') else 'body'))
            lowered=(sid+' '+sname).lower()
            if not level:
                if 'caption' in lowered: kind='caption'
                elif sid in STYLE_ROLES or sid.startswith('BIME') or any(x in lowered for x in ('title','sourcecode','source code','verbatim','toc','table of figures')): kind='special'
                elif role and len(t)<50 and scope=='thesis' and kind=='body': kind='special'
            records.append({'body_index':index+1,'paragraph_index':len(records)+1,'element':p,'text':t,'label':label,'display':display,'level':level,'region':current,'kind':kind,'style':sid,'style_name':sname,'in_sdt':block.tag==q('w:sdt')})
    return records

def safe_json(path: Path, data: Any):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
