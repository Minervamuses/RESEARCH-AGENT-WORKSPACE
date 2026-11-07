"""Surgical insertion: preserve recipient OPC parts and original body/style subtrees."""
from __future__ import annotations
import copy,hashlib,posixpath,re,tempfile,collections
from pathlib import Path
from .common import *
from .convert import convert, declare_media_defaults
from .audit import audit


def rels_name(part):
    return posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')

class Merger:
    def __init__(self,target:Package,donor:Package):
        self.dst=target;self.src=donor;self.types=target.getxml('[Content_Types].xml');self.source_types=donor.getxml('[Content_Types].xml')
        existing=set(target.parts)
        digest=hashlib.sha256(donor.parts['word/document.xml']).hexdigest()[:8]
        self.prefix='BIME'+digest
        i=0
        while any(self.prefix in n for n in existing) or self.prefix.encode() in target.parts.get('word/styles.xml',b''):
            i+=1;self.prefix='BIME'+digest+str(i)
        self.clone_cache={};self.rels_cache={};self.style_map={};self.num_map={}
        self.changed=set();self.drawing_id=1;self.bookmark_id=1
        for name,data in target.parts.items():
            if not name.endswith('.xml') or not name.startswith('word/'):continue
            try:rt=xml(data)
            except E.XMLSyntaxError:continue
            for n in rt.xpath('.//w:bookmarkStart',namespaces=NS):
                if n.get(q('w:id'),'').isdigit():self.bookmark_id=max(self.bookmark_id,int(n.get(q('w:id')))+1)
            for n in rt.xpath('.//wp:docPr',namespaces=NS):
                if n.get('id','').isdigit():self.drawing_id=max(self.drawing_id,int(n.get('id'))+1)

    def _type(self,part):
        for n in self.source_types:
            if n.tag=='{'+CT+'}Override' and n.get('PartName')=='/'+part:return n.get('ContentType')
        ext=part.rsplit('.',1)[-1]
        for n in self.source_types:
            if n.tag=='{'+CT+'}Default' and n.get('Extension')==ext:return n.get('ContentType')
        raise BimeError('Missing donor content type: '+part)

    def add_type(self,part,content_type):
        if not any(n.get('PartName')=='/'+part for n in self.types):
            n=E.SubElement(self.types,'{'+CT+'}Override');n.set('PartName','/'+part);n.set('ContentType',content_type)

    def get_rels(self,part):
        path=rels_name(part)
        if path not in self.rels_cache:
            rt=self.dst.getxml(path)
            if rt is None:rt=E.Element('{'+REL+'}Relationships',nsmap={None:REL})
            self.rels_cache[path]=rt
        return self.rels_cache[path]

    def add_rel(self,part,typ,target,external=False):
        rt=self.get_rels(part);ids={n.get('Id') for n in rt};i=1
        while f'rIdBIME{i}' in ids:i+=1
        rid=f'rIdBIME{i}';n=E.SubElement(rt,'{'+REL+'}Relationship')
        n.set('Id',rid);n.set('Type',typ);n.set('Target',target)
        if external:n.set('TargetMode','External')
        return rid

    def ensure_doc_part(self,part,typ):
        rels=self.get_rels('word/document.xml')
        if not any(n.get('Type')==R+'/'+typ for n in rels):
            self.add_rel('word/document.xml',R+'/'+typ,posixpath.relpath(part,'word'))

    def clone_part(self,part):
        if part in self.clone_cache:return self.clone_cache[part]
        if part not in self.src.parts:raise BimeError('Broken donor relationship: '+part)
        name=posixpath.join('word',self.prefix,posixpath.basename(part))
        stem,ext=posixpath.splitext(name);i=0
        while name in self.dst.parts:i+=1;name=f'{stem}_{i}{ext}'
        self.clone_cache[part]=name;self.dst.parts[name]=self.src.parts[part];self.add_type(name,self._type(part))
        rels=self.src.getxml(rels_name(part))
        if rels is not None:
            rt=copy.deepcopy(rels)
            for n in rt:
                if n.get('TargetMode')=='External':continue
                old=posixpath.normpath(posixpath.join(posixpath.dirname(part),n.get('Target')))
                new=self.clone_part(old);n.set('Target',posixpath.relpath(new,posixpath.dirname(name)))
            self.dst.setxml(rels_name(name),rt)
        return name

    def rewire_rels(self,nodes,source_part,dest_part):
        rels=self.src.getxml(rels_name(source_part));srcmap={} if rels is None else {n.get('Id'):n for n in rels}
        mapping={}
        for root in nodes:
            for node in root.iter():
                for attr,value in list(node.attrib.items()):
                    if not attr.startswith('{'+R+'}'):continue
                    if value not in mapping:
                        rel=srcmap.get(value)
                        if rel is None:raise BimeError(f'Unknown donor relationship {source_part}:{value}')
                        external=rel.get('TargetMode')=='External';dest=rel.get('Target')
                        if not external:
                            old=posixpath.normpath(posixpath.join(posixpath.dirname(source_part),dest))
                            new=self.clone_part(old);dest=posixpath.relpath(new,posixpath.dirname(dest_part))
                        mapping[value]=self.add_rel(dest_part,rel.get('Type'),dest,external)
                    node.set(attr,mapping[value])

    def merge_styles_numbering(self):
        source=self.src.getxml('word/styles.xml');target=self.dst.getxml('word/styles.xml')
        if source is None:raise BimeError('Donor lacks styles.')
        if target is None:target=E.Element(q('w:styles'),nsmap={'w':W})
        copies=[]
        for s in source.findall(q('w:style')):
            sid=s.get(q('w:styleId'));self.style_map[sid]=self.prefix+'_'+sid
        sn=self.src.getxml('word/numbering.xml');tn=self.dst.getxml('word/numbering.xml')
        if sn is not None:
            if sn.findall(q('w:numPicBullet')):raise BimeError('Picture-bullet numbering is not supported for donor insertion.')
            if tn is None:tn=E.Element(q('w:numbering'),nsmap={'w':W})
            ai=max([int(n.get(q('w:abstractNumId'))) for n in tn.findall(q('w:abstractNum'))]+[-1])+1
            ni=max([int(n.get(q('w:numId'))) for n in tn.findall(q('w:num'))]+[0])+1
            amap={}
            for a in sn.findall(q('w:abstractNum')):
                old=a.get(q('w:abstractNumId'));amap[old]=str(ai);ai+=1
                c=copy.deepcopy(a);c.set(q('w:abstractNumId'),amap[old]);self.remap_styles(c)
                # Word numbering order: abstractNum nodes precede concrete num nodes.
                first=tn.find(q('w:num'))
                if first is None:tn.append(c)
                else:first.addprevious(c)
            for n in sn.findall(q('w:num')):
                old=n.get(q('w:numId'));self.num_map[old]=str(ni);ni+=1
                c=copy.deepcopy(n);c.set(q('w:numId'),self.num_map[old]);a=c.find(q('w:abstractNumId'))
                if a is not None:a.set(q('w:val'),amap[a.get(q('w:val'))])
                tn.append(c)
            self.dst.setxml('word/numbering.xml',tn);self.add_type('word/numbering.xml','application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml');self.ensure_doc_part('word/numbering.xml','numbering')
        for s in source.findall(q('w:style')):
            c=copy.deepcopy(s);c.set(q('w:styleId'),self.style_map[s.get(q('w:styleId'))]);c.attrib.pop(q('w:default'),None)
            name=c.find(q('w:name'))
            if name is not None:name.set(q('w:val'),self.prefix+' '+name.get(q('w:val'),''))
            for tag in ('basedOn','next','link'):
                n=c.find(q('w:'+tag))
                if n is not None and n.get(q('w:val')) in self.style_map:n.set(q('w:val'),self.style_map[n.get(q('w:val'))])
            self.remap_styles(c);self.remap_numbering(c);target.append(c)
        self.dst.setxml('word/styles.xml',target);self.add_type('word/styles.xml','application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml');self.ensure_doc_part('word/styles.xml','styles')

    def remap_styles(self,node):
        for n in node.iter():
            if n.tag in (q('w:pStyle'),q('w:rStyle'),q('w:tblStyle'),q('w:styleLink'),q('w:numStyleLink')):
                old=n.get(q('w:val'))
                if old in self.style_map:n.set(q('w:val'),self.style_map[old])

    def remap_numbering(self,node):
        for n in node.iter(q('w:numId')):
            old=n.get(q('w:val'))
            if old in self.num_map:n.set(q('w:val'),self.num_map[old])

    def transform(self,nodes):
        source_res=Resolver(self.src)
        for root in nodes:
            for p in ([root] if root.tag==q('w:p') else root.xpath('.//w:p',namespaces=NS)):
                if p.find('w:pPr/w:pStyle',NS) is None:
                    pp=child(p,'w:pPr');st=el('w:pStyle',val=source_res.default_style);pp.insert(0,st)
            self.remap_styles(root);self.remap_numbering(root)
            for n in root.xpath('.//wp:docPr',namespaces=NS):n.set('id',str(self.drawing_id));self.drawing_id+=1
        self.remap_bookmarks(nodes)

    def remap_bookmarks(self,nodes):
        maxid=self.bookmark_id
        ids={};names={}
        for root in nodes:
            for n in ([root] if root.tag==q('w:bookmarkStart') else [])+root.xpath('.//w:bookmarkStart',namespaces=NS):
                old=n.get(q('w:id'));ids.setdefault(old,str(maxid));maxid+=1;n.set(q('w:id'),ids[old])
                name=n.get(q('w:name'))
                if name:
                    new=(self.prefix+'_'+name)[:30]+'_'+hashlib.sha256(name.encode()).hexdigest()[:8];names[name]=new;n.set(q('w:name'),new)
        self.bookmark_id=maxid
        for root in nodes:
            for n in root.iter():
                if n.tag==q('w:bookmarkEnd') and n.get(q('w:id')) in ids:n.set(q('w:id'),ids[n.get(q('w:id'))])
                if n.tag==q('w:hyperlink') and n.get(q('w:anchor')) in names:n.set(q('w:anchor'),names[n.get(q('w:anchor'))])
                if n.tag==q('w:instrText') and n.text:
                    for old,new in names.items():n.text=re.sub(r'(\b(?:REF|PAGEREF)\s+)'+re.escape(old)+r'(?=\s|$)',lambda m:m.group(1)+new,n.text)
                if n.tag==q('w:fldSimple'):
                    instruction=n.get(q('w:instr'),'')
                    for old,new in names.items():instruction=re.sub(r'(\b(?:REF|PAGEREF)\s+)'+re.escape(old)+r'(?=\s|$)',lambda m:m.group(1)+new,instruction)
                    n.set(q('w:instr'),instruction)

    def merge_notes(self,nodes,kind):
        refs=[]
        for root in nodes:refs.extend(root.xpath('.//w:'+kind+'Reference',namespaces=NS))
        if not refs:return
        part='word/'+kind+'s.xml';source=self.src.getxml(part)
        if source is None:raise BimeError('Missing donor '+kind+'s.')
        target=self.dst.getxml(part)
        if target is None:target=E.Element(q('w:'+kind+'s'),nsmap={'w':W,'r':R})
        index={n.get(q('w:id')):n for n in source};used={n.get(q('w:id')) for n in target}
        nid=max([int(n) for n in used if n.lstrip('-').isdigit()]+[0])+1;mapping={};copies=[]
        for ref in refs:
            old=ref.get(q('w:id'))
            if old not in mapping:
                if old not in index:raise BimeError('Broken '+kind+' id '+str(old))
                mapping[old]=str(nid);nid+=1;c=copy.deepcopy(index[old]);c.set(q('w:id'),mapping[old]);copies.append(c)
            ref.set(q('w:id'),mapping[old])
        for n in source:
            if n.get(q('w:id')) in ('-1','0') and n.get(q('w:id')) not in used:target.append(copy.deepcopy(n))
        self.rewire_rels(copies,part,part);self.transform(copies)
        for c in copies:target.append(c)
        self.dst.setxml(part,target);self.add_type(part,'application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'s+xml');self.ensure_doc_part(part,kind+'s')

    def finish(self):
        for name,rt in self.rels_cache.items():self.dst.setxml(name,rt)
        self.dst.setxml('[Content_Types].xml',self.types);declare_media_defaults(self.dst)
        settings=self.dst.getxml('word/settings.xml')
        if settings is not None:
            child(settings,'w:updateFields').set(q('w:val'),'true');self.dst.setxml('word/settings.xml',settings)


KEEP_RUN_PROPS={'rStyle','b','bCs','i','iCs','u','strike','dstrike','vertAlign','caps','smallCaps','noProof','lang'}

def target_styles(pkg):
    """Heading and numbered caption styles the recipient already uses (friend-template compatibility)."""
    res=Resolver(pkg);numbering=Numbering(pkg,res);found={}
    for sid,s in res.index.items():
        if s.get(q('w:type'))!='paragraph':continue
        nm=s.find(q('w:name'));name=(nm.get(q('w:val')) if nm is not None else '').strip().lower()
        hit=re.fullmatch(r'heading ([1-6])',name)
        if hit:found[('heading',int(hit.group(1)))]=sid
    for num_id,info in numbering.nums.items():
        for ilvl,lvl in info['levels'].items():
            text_value=lvl['text'] or ''
            if lvl['pstyle'] and re.match(r'^(圖|Figure)',text_value,re.I):found.setdefault(('caption','figure'),lvl['pstyle'])
            if lvl['pstyle'] and re.match(r'^(表|Table)',text_value,re.I):found.setdefault(('caption','table'),lvl['pstyle'])
    return found,res

def style_numbered(res,sid):
    return any(s.find('w:pPr/w:numPr',NS) is not None for s in res.chain(sid))

def strip_direct(p):
    """Let the recipient style decide the look: drop direct paragraph and font formatting, keep emphasis."""
    pp=p.find(q('w:pPr'))
    if pp is not None:
        for c in list(pp):
            if c.tag!=q('w:pStyle'):pp.remove(c)
    for rp in p.xpath('.//w:r/w:rPr',namespaces=NS):
        for c in list(rp):
            if E.QName(c).localname not in KEEP_RUN_PROPS:rp.remove(c)

LITERAL=re.compile(r'^\s*(?:第\s*[0-9零一二三四五六七八九十百]+\s*章|chapter\s+\d+|\d+(?:[.-]\d+)*|(?:圖|表|figure|table)\s*\d+\s*[-－–]\s*\d+)[\s\u3000]*',re.I)

def strip_literal_number(p):
    """Remove the typed number so Word's own list numbering is not doubled; return the removed label."""
    ts=p.xpath('.//w:t',namespaces=NS)
    full=''.join(t.text or '' for t in ts)
    m=LITERAL.match(full)
    if not m:return None
    remove=m.end();label=m.group(0).strip()
    for t in ts:
        if remove<=0:break
        value=t.text or ''
        cut=min(len(value),remove);t.text=value[cut:];remove-=cut
    # The list level supplies its own separator; drop a tab left between the removed label and the title.
    for n in p.xpath('.//w:r/w:t | .//w:r/w:tab',namespaces=NS):
        if n.tag==q('w:t'):
            if (n.text or '').strip(): break
            continue
        n.getparent().remove(n);break
    for t in p.xpath('.//w:t',namespaces=NS):
        if t.text: t.text=t.text.lstrip(' \u3000');break
    return label

def normalise_label(value):
    return re.sub(r'[\s\u3000]+','',value or '').lower()

def map_to_recipient(target,nodes,original_styles,notes):
    """Map inserted headings and captions onto the recipient's own styles; return checks for later."""
    found,res=target_styles(target);checks=[]
    for root in nodes:
        for p in ([root] if root.tag==q('w:p') else root.xpath('.//w:p',namespaces=NS)):
            sid=original_styles.get(p)
            if not sid:continue
            hit=re.fullmatch(r'Heading([1-6])',sid)
            key=('heading',int(hit.group(1))) if hit else ('caption','figure') if sid=='ImageCaption' else ('caption','table') if sid=='TableCaption' else None
            if key not in found:continue
            new=found[key];strip_direct(p);p.find('w:pPr/w:pStyle',NS).set(q('w:val'),new)
            if style_numbered(res,new):
                label=strip_literal_number(p)
                checks.append((p,label))
    if checks:notes.append({'type':'recipient_styles','message':f'{len(checks)} inserted heading/caption paragraph(s) use the recipient\'s auto-numbered styles; typed numbers were removed after checking Word would display the same number.'})
    elif any(True for _ in found):notes.append({'type':'recipient_styles','message':'Inserted headings/captions use the recipient\'s heading/caption styles.'})
    return checks

def verify_numbers(target,checks):
    res=Resolver(target);numbering=Numbering(target,res);labels={}
    for p in target.body.iter(q('w:p')):labels[p]=numbering.label(p)
    bad=[]
    for p,typed in checks:
        shown=labels.get(p,'')
        if typed is None:bad.append((None,shown.strip()));continue
        typed_norm=normalise_label(typed);shown_norm=normalise_label(shown)
        if typed_norm!=shown_norm and not (typed_norm.startswith('第') and shown_norm==typed_norm):bad.append((typed,shown.strip()))
    return bad

def locate(pkg,mode,anchor,occurrence=None):
    children=list(pkg.body)
    if mode=='at_end':
        return next((i for i,c in enumerate(children) if c.tag==q('w:sectPr')),len(children)),None
    # Spaces, tabs and the ideographic space in '第一章　前言' compare equal.
    norm=lambda x:re.sub(r'\s+',' ',x).strip()
    matches=[(i,p) for i,p in enumerate(children) if p.tag==q('w:p') and norm(text(p))==norm(anchor)]
    if not matches:raise BimeError('Exact anchor not found among top-level body paragraphs. Use inspect; no fuzzy insertion was attempted.')
    if occurrence is None and len(matches)>1:raise BimeError('Anchor is ambiguous. Use --occurrence with a 1-based match index.')
    occ=occurrence or 1
    if occ<1 or occ>len(matches):raise BimeError('Anchor occurrence is outside the available matches.')
    index,p=matches[occ-1]
    if mode=='after':return index+1,index+1
    if mode=='before':
        while index>0 and children[index-1].tag==q('w:bookmarkStart'):index-=1
        return index,index+1
    res=Resolver(pkg);level=res.heading_level(p)
    if not level:raise BimeError('--under requires a paragraph with a recognized heading level.')
    for j in range(index+1,len(children)):
        c=children[j]
        if c.tag==q('w:p'):
            nxt=res.heading_level(c)
            if nxt and nxt<=level:
                while j>0 and children[j-1].tag==q('w:bookmarkStart'):j-=1
                return j,index+1
    return next((i for i,c in enumerate(children) if c.tag==q('w:sectPr')),len(children)),index+1


def insert(source:Path,markdown:Path,output:Path,cfg,scope='fragment',*,mode='at_end',anchor='',occurrence=None,overwrite=False,dry_run=False,expected_sha=None,allow_draft=False,recipient_styles=True):
    source=Path(source);output=Path(output)
    if source.resolve()==output.resolve():raise BimeError('The source must remain unchanged; choose a different output path.')
    if output.exists() and not overwrite and not dry_run:raise BimeError('Output exists: '+str(output))
    before_hash=sha(source)
    if expected_sha and before_hash!=expected_sha:raise BimeError('Source hash no longer matches the inspected version. Inspect again before insertion.')
    target=Package(source);target.writable();at,anchor_index=locate(target,mode,anchor,occurrence)
    before=audit(source,cfg,scope)
    preserved_nodes=[(n,E.tostring(n,method='c14n')) for n in target.body]
    original_parts=dict(target.parts)
    # The inserted text follows the recipient's writing language (三.1), not its own.
    donor_cfg=dict(cfg)
    if cfg['language']=='auto':
        donor_cfg['language']=document_language([r['text'] for r in paragraph_records(target,scope) if r['region']=='body' and r['kind']=='body'])
    with tempfile.TemporaryDirectory(prefix='bime-insert-') as td:
        td=Path(td);donor_path=td/'donor.docx';temporary=td/'merged.docx'
        generation=convert(markdown,donor_path,donor_cfg,'fragment',for_insert=True)
        donor=Package(donor_path)
        nodes=[copy.deepcopy(n) for n in donor.body if n.tag!=q('w:sectPr')]
        original_styles={}
        for root in nodes:
            for p in ([root] if root.tag==q('w:p') else root.xpath('.//w:p',namespaces=NS)):
                st=p.find('w:pPr/w:pStyle',NS)
                if st is not None:original_styles[p]=st.get(q('w:val'))
        if not any(text(n).strip() or n.xpath('.//w:drawing | .//m:oMath',namespaces=NS) for n in nodes):raise BimeError('Insertion fragment contains no visible text, image, table, or equation.')
        if any(n.xpath('.//w:sectPr',namespaces=NS) for n in nodes):raise BimeError('Donor contains section breaks; insertion must not overwrite recipient pagination.')
        merger=Merger(target,donor);merger.merge_styles_numbering();merger.rewire_rels(nodes,'word/document.xml','word/document.xml')
        merger.merge_notes(nodes,'footnote');merger.merge_notes(nodes,'endnote');merger.transform(nodes)
        checks=map_to_recipient(target,nodes,original_styles,generation['decisions']) if recipient_styles else []
        for i,n in enumerate(nodes):target.body.insert(at+i,n)
        bad=verify_numbers(target,checks)
        if bad:
            detail='; '.join(f'typed {t or "(none)"} but Word would show {s or "(nothing)"}' for t,s in bad[:5])
            raise BimeError('The recipient numbers headings/captions automatically and the inserted numbers do not match their position; nothing was written. '+detail)
        merger.finish()
        if not all(E.tostring(n,method='c14n')==content for n,content in preserved_nodes):
            raise BimeError('Original body preservation invariant failed; no output was committed.')
        target.save(temporary)
        after=audit(temporary,cfg,scope)
        def sig(f):return (f['rule_id'],f['message'],json.dumps(f['actual'],ensure_ascii=False,sort_keys=True))
        baseline=collections.Counter(sig(f) for f in before['findings'] if f['severity']=='error')
        added=[]
        for finding in after['findings']:
            if finding['severity']!='error':continue
            key=sig(finding)
            if baseline[key]:baseline[key]-=1
            else:added.append(finding)
        if added and not allow_draft and not dry_run:
            brief='; '.join(x['rule_id']+': '+x['message'] for x in added[:5])
            raise BimeError('Insertion introduces new hard violations; output was not committed. Fix the Markdown or explicitly request --allow-draft. '+brief)
        if sha(source)!=before_hash:raise BimeError('Source changed during insertion; no output was committed.')
        changed=[n for n,b in original_parts.items() if target.parts.get(n)!=b]
        preserved=[n for n,b in original_parts.items() if target.parts.get(n)==b]
        result={'operation':'insert','dry_run':dry_run,'source':str(source),'source_sha256':before_hash,'output':str(output),'anchor':{'mode':mode,'text':anchor,'matched_body_index':anchor_index,'insertion_before_body_index':at+1},'inserted_body_nodes':len(nodes),'original_body_subtrees_unchanged':True,'preserved_existing_parts':preserved,'changed_existing_parts':changed,'added_parts':[n for n in target.parts if n not in original_parts],'new_hard_violations':added,'baseline_summary':before['summary'],'result_summary':after['summary'],'generation_decisions':generation['decisions'],'layout_verified':False,'scope':scope,'policy':cfg}
        if not dry_run:
            target.save(output,overwrite);result['output_sha256']=sha(output);after['source']=str(output);after['source_sha256']=sha(output)
        result['notes']=['Original text numbering and cross-reference field codes were preserved, not globally renumbered.', 'Update and verify all fields in the target Word. Style-based TOC/LOF/LOT may need the inserted namespaced styles added to their collection rules.', 'Preserving original XML is not a guarantee of unchanged physical pagination.']
        result['audit_after']=after
        return result
