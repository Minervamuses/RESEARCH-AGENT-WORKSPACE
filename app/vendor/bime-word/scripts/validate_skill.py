#!/usr/bin/env python3
"""Validate this package's metadata, source hash, and optional file manifest (stdlib only)."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main() -> int:
    errors=[]
    required=['SKILL.md','README.md','agents/openai.yaml','scripts/bime_word.py','scripts/preview.py','assets/defaults.json','references/rules.json','references/authority.md','references/friend-template.md','references/author-decisions.md','references/source/bime-format-original.docx','tests/test_bime_word.py','tests/test_authority.py']
    for path in required:
        if not (ROOT/path).is_file():errors.append('Missing: '+path)
    if errors:print('\n'.join(errors),file=sys.stderr);return 1
    text=(ROOT/'SKILL.md').read_text(encoding='utf-8')
    front=re.match(r'^---\n(.*?)\n---\n',text,re.S)
    if not front:errors.append('Missing YAML frontmatter.')
    else:
        def field(name):
            m=re.search(r'^'+re.escape(name)+r':\s*(.+)$',front.group(1),re.M)
            return m.group(1).strip().strip('"\'') if m else ''
        name=field('name');description=field('description')
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',name) or len(name)>64:errors.append('Invalid skill name.')
        if name!=ROOT.name:errors.append('Skill name does not match parent folder.')
        if not 1<=len(description)<=1024:errors.append('Invalid description length.')
    if len(text.splitlines())>=500:errors.append('SKILL.md exceeds 500-line recommendation.')
    catalog=json.loads((ROOT/'references/rules.json').read_text(encoding='utf-8'))
    ids=[r['id'] for r in catalog['rules']]
    if len(ids)!=len(set(ids)):errors.append('Rule IDs must be unique.')
    order=catalog.get('authority_order',[])
    if order[:3]!=['regulation','friend_template','author_claude_md']:errors.append('Authority order must be regulation > friend_template > author_claude_md.')
    for r in catalog['rules']:
        if not r.get('quote') or not r.get('source_section'):errors.append('Missing rule provenance: '+r['id'])
        if r.get('authority') not in order:errors.append('Rule without a known authority: '+r['id'])
        if r.get('authority')=='regulation' and not r.get('source_paragraph_1based'):errors.append('Regulation rule without a source paragraph: '+r['id'])
        d=r.get('decision')
        if d and d.get('resolved_by') not in order:errors.append('Decision without a known authority: '+r['id'])
    source=ROOT/'references/source/bime-format-original.docx'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=catalog['sources']['regulation']['sha256']:errors.append('Bundled original source hash mismatch.')
    for p in ROOT.rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.ttf','.otf','.woff','.woff2','.ttc'):errors.append('Unexpected font file: '+str(p))
    count=0
    manifest=ROOT/'manifest.sha256'
    if manifest.exists():
        for line in manifest.read_text(encoding='utf-8').splitlines():
            expected,relative=line.split('  ',1);p=ROOT/relative;count+=1
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:errors.append('Manifest mismatch: '+relative)
    if errors:print('\n'.join(errors),file=sys.stderr);return 1
    print(json.dumps({'valid':True,'name':ROOT.name,'display_name':'bime_word','rules':len(ids),'source_hash_verified':True,'manifest_files_verified':count,'note':'Local package checks; not a claim of host installation or document conformity.'},ensure_ascii=False,indent=2))
    return 0
if __name__=='__main__':sys.exit(main())
