"""Author-year citations and reference entries in the Appendix 17 formats (二.8).

Input is CSL-JSON (Zotero, Better BibTeX, or `pandoc refs.bib -t csljson`). Output is
Pandoc AST, so the DOCX writer keeps hyperlinks and code in pinpoints. Nothing is
inferred: a missing key or year stops conversion, and missing fields are reported,
never filled in.
"""
from __future__ import annotations
import json, re, shutil, subprocess
from pathlib import Path
from .common import BimeError, CJK

KANA = re.compile(r'[぀-ヿ]')
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
          'October', 'November', 'December']


def load_bibliography(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        raise BimeError('Bibliography file does not exist: ' + str(path))
    if path.suffix.lower() == '.json':
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    elif path.suffix.lower() in ('.bib', '.bibtex', '.yaml', '.yml'):
        exe = shutil.which('pandoc')
        if not exe:
            raise BimeError('Pandoc is required to read .bib/.yaml bibliographies.')
        fmt = {'.bib': 'biblatex', '.bibtex': 'bibtex', '.yaml': 'markdown', '.yml': 'markdown'}[path.suffix.lower()]
        args = [exe, '--from', fmt, '--to', 'csljson', str(path)] if fmt != 'markdown' else [exe, '--from', 'markdown', '--to', 'csljson', '--standalone', str(path)]
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        if p.returncode:
            raise BimeError('Pandoc could not read the bibliography: ' + p.stderr.decode('utf-8', 'replace'))
        data = json.loads(p.stdout.decode('utf-8'))
    else:
        raise BimeError('Bibliography must be CSL-JSON (.json), BibTeX/BibLaTeX (.bib) or CSL YAML.')
    if isinstance(data, dict) and 'references' in data:
        data = data['references']
    if not isinstance(data, list):
        raise BimeError('Bibliography must be a list of CSL-JSON items.')
    items = {}
    for item in data:
        key = item.get('id') if isinstance(item, dict) else None
        if not key:
            raise BimeError('Every bibliography item needs an id (the citation key).')
        if key in items:
            raise BimeError('Duplicate bibliography id: ' + key)
        items[key] = item
    return items


# ---------- item facts ----------

def language(item) -> str:
    lang = str(item.get('language', '')).lower()
    if lang.startswith(('zh', 'chi')):
        return 'zh'
    if lang.startswith(('ja', 'jpn')):
        return 'ja'
    if lang:
        return 'en'
    sample = str(item.get('title', '')) + ''.join(n.get('family', '') + n.get('literal', '') for n in names(item))
    if KANA.search(sample):
        return 'ja'
    return 'zh' if CJK.search(sample) else 'en'


ET_AL = {'et al.', 'et al', 'others', '等', '等人'}


def is_et_al(n):
    return bool(n.get('literal')) and n['literal'].strip().lower() in ET_AL


def names(item, role='author'):
    value = item.get(role) or []
    return [n for n in value if isinstance(n, dict)]


def creators(item):
    """Authors, or the issuing organisation for pages that have none (regs 二.8(12) USDA example)."""
    people = names(item)
    if people:
        return people
    if item.get('publisher') and item.get('type') in ('webpage', 'post-weblog', 'post', 'software', 'report', 'dataset'):
        return [{'literal': item['publisher']}]
    return []


def year(item):
    issued = item.get('issued') or {}
    parts = issued.get('date-parts') if isinstance(issued, dict) else None
    if parts and parts[0] and parts[0][0]:
        return str(parts[0][0])
    literal = issued.get('literal') if isinstance(issued, dict) else None
    hit = re.search(r'\d{4}', str(literal or ''))
    return hit.group(0) if hit else None


def family(n):
    if n.get('literal'):
        return n['literal']
    particle = n.get('non-dropping-particle', '')
    return (particle + ' ' if particle else '') + n.get('family', '')


def short_author(item, lang):
    people = creators(item)
    if not people:
        return None
    fam = [family(n) for n in people]
    if lang in ('zh', 'ja'):
        # 二.8(4): (林與張，1960)、(陳等人，1989)
        if len(fam) == 1:
            return fam[0]
        if len(fam) == 2:
            return fam[0] + '與' + fam[1]
        return fam[0] + '等人'
    if len(fam) == 1:
        return fam[0]
    if len(fam) == 2:
        return fam[0] + ' and ' + fam[1]
    return fam[0] + ' et al.'


def initials(given: str) -> str:
    given = re.sub(r'\([^)]*\)', ' ', given or '').strip()
    out = []
    for token in given.split():
        if '-' in token:
            out.append('-'.join(p[0] + '.' for p in token.split('-') if p))
        elif re.fullmatch(r'(?:[A-Z]\.)+', token):
            out.extend(ch + '.' for ch in token.replace('.', ''))
        else:
            out.append(token[0] + '.')
    return ' '.join(out)


def person(n, inverted, lang):
    if n.get('literal'):
        return n['literal']
    if lang in ('zh', 'ja'):
        return n.get('family', '') + n.get('given', '')
    ini = initials(n.get('given', ''))
    fam = family(n)
    suffix = (', ' + n['suffix']) if n.get('suffix') else ''
    if not ini:
        return fam + suffix
    return (fam + ', ' + ini + suffix) if inverted else (ini + ' ' + fam + suffix)


def name_list(people, lang, invert_first=True):
    # A trailing {"literal": "et al."} records an author list the source truncated; it is kept, not completed.
    truncated = bool(people) and is_et_al(people[-1])
    people = [n for n in people if not is_et_al(n)]
    if lang in ('zh', 'ja'):
        return '、'.join(person(n, False, lang) for n in people) + ('等' if truncated else '')
    parts = [person(n, invert_first and i == 0, lang) for i, n in enumerate(people)]
    if truncated:
        return ', '.join(parts) + ', et al.'
    if len(parts) == 1:
        return parts[0]
    # 二.8(5)–(13): "Miller, F. R., and R. A. Creelman." / "A, B, C, and D."
    return ', '.join(parts[:-1]) + ', and ' + parts[-1]


def editor_list(people, lang):
    if lang in ('zh', 'ja'):
        return '、'.join(person(n, False, lang) for n in people)
    parts = [person(n, False, lang) for n in people]
    if len(parts) <= 2:
        return ' and '.join(parts)
    return ', '.join(parts[:-1]) + ', and ' + parts[-1]


def pages(item):
    value = item.get('page') or item.get('number') if item.get('type') in ('article-journal', 'article-magazine', 'article-newspaper') else item.get('page')
    return re.sub(r'\s*[–—]\s*', '-', str(value)) if value else None


def ordinal_edition(value):
    if value is None:
        return None
    text = str(value)
    if text.isdigit():
        n = int(text)
        suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f'{n}{suffix} ed.'
    return text if text.endswith('.') else text


def date_text(value, lang):
    parts = (value or {}).get('date-parts') if isinstance(value, dict) else None
    if not parts or not parts[0]:
        return None
    ymd = parts[0] + [None, None]
    y, m, d = ymd[0], ymd[1], ymd[2]
    if lang in ('zh', 'ja'):
        return '-'.join(f'{x:02d}' if i else str(x) for i, x in enumerate([y, m, d]) if x)
    if m and d:
        return f'{d} {MONTHS[m - 1]} {y}'
    if m:
        return f'{MONTHS[m - 1]} {y}'
    return str(y)


def arxiv_id(item):
    for field in ('number', 'archive_location', 'DOI', 'URL'):
        value = str(item.get(field, ''))
        hit = re.search(r'(?:arXiv[.:/]|abs/)(\d{4}\.\d{4,5}(?:v\d+)?)', value, re.I)
        if hit:
            return hit.group(1)
    return None


def link(item):
    if item.get('URL'):
        return item['URL']
    if item.get('DOI'):
        return 'https://doi.org/' + item['DOI']
    return None


# ---------- inline assembly (Pandoc AST) ----------

def S(text):
    return {'t': 'Str', 'c': text}


def inlines_from_text(text):
    out = []
    for i, piece in enumerate(re.split(r'( +)', text)):
        if not piece:
            continue
        out.append({'t': 'Space'} if piece.startswith(' ') else S(piece))
    return out


def url_inline(url):
    return {'t': 'Link', 'c': [['', [], []], [S(url)], [url, '']]}


class Segments:
    """Joins sentence pieces with the separator the language uses, avoiding doubled stops."""
    def __init__(self, lang):
        self.lang = lang
        self.parts = []

    def add(self, *pieces):
        pieces = [p for p in pieces if p]
        if pieces:
            self.parts.append(pieces)

    def inlines(self):
        out = []
        stop = '。' if self.lang in ('zh', 'ja') else '.'
        for i, pieces in enumerate(self.parts):
            if i and self.lang not in ('zh', 'ja'):
                out.append({'t': 'Space'})
            text_seen = ''
            for p in pieces:
                if isinstance(p, dict):
                    out.append(p)
                    text_seen = 'x'
                else:
                    out.extend(inlines_from_text(p))
                    text_seen = p
            last = text_seen.rstrip()
            if isinstance(pieces[-1], dict) and self.lang not in ('zh', 'ja'):
                out.append(S('.'))
            elif not last.endswith(('.', '?', '!', '。', '？', '！')):
                out.append(S(stop))
        return out


def entry_inlines(item, lang, suffix_letter=''):
    """Render one entry following the 二.8(5)–(13) examples; returns (inlines, missing_fields)."""
    typ = item.get('type', 'article-journal')
    missing = []
    zh = lang in ('zh', 'ja')
    people = creators(item)
    y = (year(item) or '') + suffix_letter
    title = item.get('title')
    if not people:
        missing.append('author')
    if not title:
        missing.append('title')
    container = item.get('container-title-short') or item.get('journalAbbreviation') or item.get('container-title')
    vol, issue, pg = item.get('volume'), item.get('issue'), pages(item)
    place, pub = item.get('publisher-place'), item.get('publisher')
    eds = names(item, 'editor')
    seg = Segments(lang)
    seg.add(name_list(people, lang) if people else '[TODO: 作者]')
    seg.add(y)
    if typ in ('article-journal', 'article-magazine', 'article-newspaper') and not arxiv_id(item):
        seg.add(title)
        if not container:
            missing.append('container-title')
        elif not (item.get('container-title-short') or item.get('journalAbbreviation')) and not zh:
            missing.append('container-title-short (verified ISO 4 abbreviation)')
        tail = str(container or '')
        if vol:
            tail += ' ' + str(vol) + (f'({issue})' if issue else '')
        else:
            missing.append('volume')
        if pg:
            tail += ': ' + pg
        else:
            missing.append('page')
        seg.add(tail)
        if not vol and not pg and link(item):
            seg.add('Available at: ', url_inline(link(item)))
    elif typ == 'book':
        seg.add(title)
        ed = ordinal_edition(item.get('edition'))
        if zh:
            seg.add('，'.join(x for x in (ed, pg) if x))
            seg.add('：'.join(x for x in (place, pub) if x))
        else:
            seg.add(', '.join(x for x in (ed, pg) if x))
            seg.add(': '.join(x for x in (place, pub) if x))
        if not pub:
            missing.append('publisher')
    elif typ in ('chapter', 'paper-conference', 'entry-encyclopedia') and container:
        seg.add(title)
        series = item.get('collection-title')
        quoted = ('〝' + str(container) + '〞' + ('（' + series + '）' if series else '')) if zh else ('“' + str(container) + '”' + (f' ({series})' if series else ''))
        if zh:
            seg.add('出自' + quoted + ('，' + pg if pg else ''))
            if eds:
                seg.add(editor_list(eds, lang) + '主編')
            seg.add('：'.join(x for x in (place, pub) if x))
        elif typ == 'chapter':
            # 二.8(7): In "Book", ed. W. H. Pierce, 87-109. Chicago: Graphic Publishing Co.
            inner = 'In ' + quoted
            if eds:
                inner += ', ' + ('ed. ' if len(eds) == 1 else 'eds. ') + editor_list(eds, lang)
            if pg:
                inner += ', ' + pg
            seg.add(inner)
            seg.add(': '.join(x for x in (place, pub) if x))
        else:
            # 二.8(8): In "Proc. …", 219-232. H. D. Londen and W. Wilkinson, eds. Washington, DC: Am. Seed Trade Assoc.
            seg.add('In ' + quoted + (', ' + pg if pg else ''))
            if eds:
                seg.add(editor_list(eds, lang) + (', ed.' if len(eds) == 1 else ', eds.'))
            seg.add(': '.join(x for x in (place, pub) if x))
        if not pg:
            missing.append('page')
            if not pub and link(item):
                seg.add('網址：' if zh else 'Available at: ', url_inline(link(item)))
    elif typ in ('paper-conference', 'speech'):
        # 二.8(9): ASAE Paper No. 85-3554. St. Joseph, MI: ASAE.
        seg.add(title)
        label = item.get('genre') or 'Paper'
        if item.get('number'):
            seg.add(f'{label} No. {item["number"]}')
        else:
            missing.append('number')
        seg.add((': ' if not zh else '：').join(x for x in (place, pub) if x))
    elif typ == 'thesis':
        seg.add(title)
        seg.add(item.get('genre') or ('碩士論文' if zh else '[TODO: 學位論文類別]'))
        if not item.get('genre'):
            missing.append('genre')
        seg.add((': ' if not zh else '：').join(x for x in (place, pub) if x))
    elif typ == 'software':
        # 二.8(11): SAS. 1990. SAS User's Guide: Statistics. Ver. 6a. Cary, N.C.: SAS Institute, Inc.
        seg.add(title)
        if item.get('version'):
            seg.add(('版本 ' if zh else 'Ver. ') + str(item['version']))
        seg.add((': ' if not zh else '：').join(x for x in (place, pub if names(item) else None) if x))
        url = link(item)
        if url:
            seg.add('網址：' if zh else 'Available at: ', url_inline(url))
        acc = date_text(item.get('accessed'), lang)
        if acc:
            seg.add(('上網日期：' if zh else 'Accessed ') + acc)
    elif typ in ('webpage', 'post-weblog', 'post'):
        # 二.8(12) with the author decision: company as publisher, no invented place.
        seg.add(title)
        if item.get('container-title') and item.get('container-title') != pub:
            seg.add(str(item['container-title']))
        if names(item) or place:
            seg.add((': ' if not zh else '：').join(x for x in (place, pub) if x))
        url = link(item)
        if url:
            seg.add('網址：' if zh else 'Available at: ', url_inline(url))
        else:
            missing.append('URL')
        acc = date_text(item.get('accessed'), lang)
        if acc:
            seg.add(('上網日期：' if zh else 'Accessed ') + acc)
        else:
            missing.append('accessed')
    elif typ == 'patent':
        seg.add(title)
        number = item.get('number')
        if number and item.get('authority') and 'patent' not in str(number).lower():
            number = f"{item['authority']} Patent No. {number}"
        seg.add(str(number) if number else None)
        if not number:
            missing.append('number')
    elif arxiv_id(item) or typ in ('article', 'manuscript') and 'arxiv' in json.dumps(item).lower():
        # Author decision: arXiv preprints are left as they are.
        seg.add(title)
        aid = arxiv_id(item)
        seg.add('arXiv:' + aid if aid else None)
        url = link(item)
        if url:
            seg.add('Available at: ', url_inline(url))
    else:
        seg.add(title)
        seg.add(str(container) if container else None)
        if item.get('genre') and item.get('number'):
            seg.add(f'{item["genre"]} No. {item["number"]}')
        seg.add((': ' if not zh else '：').join(x for x in (place, pub) if x))
        url = link(item)
        if url:
            seg.add('網址：' if zh else 'Available at: ', url_inline(url))
        missing.append('type (no Appendix 17 example for "' + typ + '")')
    return seg.inlines(), missing


# ---------- document processing ----------

def sort_key(item, lang, strokes):
    group = {'zh': 0, 'ja': 1, 'en': 2}[lang]
    y = year(item) or ''
    if lang in ('zh', 'ja'):
        return (group, strokes if strokes is not None else 10**6, y, item.get('title', ''))
    fams = tuple(fold(family(n)) for n in creators(item) if not is_et_al(n))
    return (group, fams, y, fold(str(item.get('title', ''))))


def fold(value):
    # Alphabetical order ignores diacritics and punctuation: Järvelin sorts as Jarvelin.
    import unicodedata
    plain = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return re.sub(r'[^0-9a-z]', '', plain.casefold())


def stroke_key(item):
    for field in ('bime-strokes', 'strokes'):
        if isinstance(item.get(field), (int, float)):
            return item[field]
    hit = re.search(r'(?:bime-)?strokes\s*[:=]\s*(\d+)', str(item.get('note', '')))
    return int(hit.group(1)) if hit else None


def collect_cites(node, out):
    if isinstance(node, dict):
        if node.get('t') == 'Cite':
            out.append(node)
        for v in node.values():
            collect_cites(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_cites(v, out)


def process(ast, bibliography_path, *, placement='auto', notes=None):
    """Replace Cite nodes in place and return reference Blocks plus a report."""
    notes = notes if notes is not None else []
    cites = []
    collect_cites(ast['blocks'], cites)
    if not cites:
        return None, {'cited': [], 'missing_fields': {}, 'uncited': []}
    if not bibliography_path:
        keys = sorted({c['citationId'] for node in cites for c in node['c'][0]})
        raise BimeError('Unresolved citation keys need a bibliography (--bibliography refs.json|refs.bib). No style is guessed. Keys: ' + ', '.join(keys[:20]))
    items = load_bibliography(bibliography_path)
    used = []
    unknown = []
    for node in cites:
        for c in node['c'][0]:
            key = c['citationId']
            if key not in items:
                unknown.append(key)
            elif key not in used:
                used.append(key)
    if unknown:
        raise BimeError('Citation keys not found in the bibliography (nothing is invented): ' + ', '.join(sorted(set(unknown))))
    no_year = [k for k in used if not year(items[k])]
    if no_year:
        raise BimeError('Bibliography items without a year cannot be cited author-year: ' + ', '.join(no_year))
    langs = {k: language(items[k]) for k in used}
    shorts = {}
    for k in used:
        s = short_author(items[k], langs[k])
        if not s:
            raise BimeError('Bibliography item has no author, editor-free organisation, or publisher to cite: ' + k)
        shorts[k] = s
    # Same short author and year: 2020a, 2020b by title (implementation default; the source is silent).
    groups = {}
    for k in used:
        groups.setdefault((shorts[k], year(items[k])), []).append(k)
    letters = {}
    for members in groups.values():
        if len(members) > 1:
            for i, k in enumerate(sorted(members, key=lambda k: str(items[k].get('title', '')).casefold())):
                letters[k] = 'abcdefghijklmnopqrstuvwxyz'[i]
    for node in cites:
        citations = node['c'][0]
        node['t'] = 'Span'
        node['c'] = [['', ['bime-citation'], []], render_group(citations, items, langs, shorts, letters)]
    ordered = sorted(used, key=lambda k: sort_key(items[k], langs[k], stroke_key(items[k])))
    report = {'cited': ordered, 'missing_fields': {}, 'uncited': [k for k in items if k not in used], 'stroke_keys_missing': []}
    blocks = []
    for k in ordered:
        inl, missing = entry_inlines(items[k], langs[k], letters.get(k, ''))
        if missing:
            report['missing_fields'][k] = missing
        if langs[k] in ('zh', 'ja') and stroke_key(items[k]) is None:
            report['stroke_keys_missing'].append(k)
        blocks.append({'t': 'Para', 'c': inl})
    if report['stroke_keys_missing']:
        notes.append({'type': 'reference_order', 'rule': 'REF_ORDER', 'message': 'Chinese/Japanese entries lack a verified surname stroke count (CSL field "bime-strokes"); they keep input order after any keyed entries.', 'keys': report['stroke_keys_missing']})
    if report['missing_fields']:
        notes.append({'type': 'reference_fields', 'rule': 'REF_TYPES', 'message': 'Entries rendered without fields their Appendix 17 example shows; nothing was filled in.', 'items': report['missing_fields']})
    if report['uncited']:
        notes.append({'type': 'uncited_references', 'rule': 'REF_CITED', 'message': 'Bibliography items never cited were left out (二.8(1)).', 'keys': report['uncited'][:50]})
    div = {'t': 'Div', 'c': [['', ['references'], [['custom-style', 'Bibliography']]], blocks]}
    return div, report


def render_group(citations, items, langs, shorts, letters):
    out = []
    mode_in_text = len(citations) == 1 and citations[0].get('citationMode', {}).get('t') == 'AuthorInText'
    if mode_in_text:
        c = citations[0]
        k = c['citationId']
        y = year(items[k]) + letters.get(k, '')
        out.append(S(shorts[k]))
        if langs[k] == 'en':
            out.append({'t': 'Space'})
        out.append(S('(' + y))
        out.extend(c.get('citationSuffix') or [])
        out.append(S(')'))
        return merge_str(out)
    out.append(S('('))
    all_cjk = all(langs[c['citationId']] in ('zh', 'ja') for c in citations)
    for i, c in enumerate(citations):
        k = c['citationId']
        y = year(items[k]) + letters.get(k, '')
        if i:
            out.append(S('；' if all_cjk else ';'))
            if not all_cjk:
                out.append({'t': 'Space'})
        prefix = c.get('citationPrefix') or []
        if prefix:
            out.extend(prefix)
            out.append({'t': 'Space'})
        if c.get('citationMode', {}).get('t') == 'SuppressAuthor':
            out.append(S(y))
        else:
            sep = '，' if langs[k] in ('zh', 'ja') else ', '
            out.extend(inlines_from_text(shorts[k] + sep + y))
        out.extend(c.get('citationSuffix') or [])
    out.append(S(')'))
    return merge_str(out)


def merge_str(inlines):
    out = []
    for x in inlines:
        if out and x.get('t') == 'Str' and out[-1].get('t') == 'Str':
            out[-1] = S(out[-1]['c'] + x['c'])
        else:
            out.append(x)
    return out
