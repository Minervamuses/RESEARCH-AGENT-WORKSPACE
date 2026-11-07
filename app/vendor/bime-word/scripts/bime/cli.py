"""Command-line interface with explicit scope, sidecar reports, and safe exit codes."""
from __future__ import annotations
import argparse,json,platform,shutil,subprocess,sys
from pathlib import Path
from importlib.metadata import version,PackageNotFoundError
from .common import *
from .convert import convert
from .audit import audit,report_markdown
from .insert import insert


def reports(report,base):
    base=Path(base)
    if base.suffix in ('.json','.md'): base=base.with_suffix('')
    jp=Path(str(base)+'.json');mp=Path(str(base)+'.md')
    safe_json(jp,report);mp.write_text(report_markdown(report),encoding='utf-8')
    return [str(jp),str(mp)]

def doctor():
    data={'python':sys.version.split()[0],'platform':platform.platform(),'packages':{},'executables':{},'fonts':{},'network_required_at_runtime':False}
    for name in ('python-docx','lxml'):
        try:data['packages'][name]=version(name)
        except PackageNotFoundError:data['packages'][name]='MISSING'
    for name in ('pandoc','soffice','libreoffice','pdftoppm','fc-match'):data['executables'][name]=shutil.which(name)
    if shutil.which('pandoc'):
        p=subprocess.run(['pandoc','--version'],capture_output=True,text=True,timeout=10);data['pandoc_version']=p.stdout.splitlines()[0] if p.stdout else 'unknown'
    if shutil.which('fc-match'):
        for font in ('DFKai-SB','MingLiU','Times New Roman'):
            p=subprocess.run(['fc-match','-f','%{family}',font],capture_output=True,text=True,timeout=10)
            data['fonts'][font]={'resolved_family':p.stdout,'note':'A substitute family is not proof that the requested font is installed.'}
    else:data['fonts']={'status':'Verify requested fonts manually in the target Word environment.'}
    data['readiness']={'audit':all(v!='MISSING' for v in data['packages'].values()),'convert_and_insert':bool(shutil.which('pandoc')) and all(v!='MISSING' for v in data['packages'].values()),'png_preview':bool((shutil.which('soffice') or shutil.which('libreoffice')) and shutil.which('pdftoppm'))}
    return data

def parser():
    p=argparse.ArgumentParser(description='bime_word: Markdown→DOCX, safe insertion, and source-grounded auditing.')
    p.add_argument('--version',action='version',version='bime_word 1.1.5')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Report dependencies/font resolution without downloading anything.')
    sub.add_parser('rules',help='Print the source-linked rule catalog as JSON.')
    for name in ('convert','insert','audit','inspect'):
        sp=sub.add_parser(name)
        sp.add_argument('source',type=Path,help='Markdown for convert; DOCX for other commands.')
        sp.add_argument('--config',type=Path)
        sp.add_argument('--scope',choices=['fragment','thesis'],default='fragment',help='fragment does not require a complete thesis front matter.')
        if name in ('convert','insert'):
            sp.add_argument('-o','--output',type=Path,required=True)
            sp.add_argument('--overwrite',action='store_true',help='Replace an existing output file, never the source.')
            sp.add_argument('--bibliography',type=Path,help='CSL-JSON (.json) or BibTeX/BibLaTeX (.bib) items for [@key] citations.')
        if name=='insert':
            sp.add_argument('--md',type=Path,required=True)
            group=sp.add_mutually_exclusive_group(required=True)
            for flag in ('before','after','under'):group.add_argument('--'+flag,metavar='EXACT_TEXT')
            group.add_argument('--at-end',action='store_true')
            sp.add_argument('--occurrence',type=int)
            sp.add_argument('--expect-sha256')
            sp.add_argument('--dry-run',action='store_true')
            sp.add_argument('--allow-draft',action='store_true',help='Explicitly permit new hard violations and retain them in the report.')
            sp.add_argument('--keep-bime-styles',action='store_true',help='Do not map inserted headings/captions onto the recipient\'s own styles.')
        if name=='audit':
            sp.add_argument('--report',type=Path,required=True,help='Report basename; writes .json and .md, never the DOCX.')
            sp.add_argument('--fail-on',choices=['error','warning','unresolved','none'],default='error')
        if name=='inspect':sp.add_argument('--output',type=Path,help='Optional JSON output; otherwise stdout only.')
    return p

def main(argv=None):
    a=parser().parse_args(argv)
    try:
        if a.command=='doctor':print(json.dumps(doctor(),ensure_ascii=False,indent=2));return 0
        if a.command=='rules':print((ROOT/'references/rules.json').read_text(encoding='utf-8'));return 0
        cfg=load_config(a.config)
        for key in ('reference_manifest','bibliography'):
            if cfg[key] and a.config:
                cfg[key]=str((a.config.parent/cfg[key]).resolve())
        if getattr(a,'bibliography',None):cfg['bibliography']=str(a.bibliography.resolve())
        if a.command=='inspect':
            pkg=Package(a.source);rs=paragraph_records(pkg,a.scope);sections=pkg.doc.xpath('.//w:sectPr',namespaces=NS)
            data={'source':str(a.source),'sha256':sha(a.source),'scope':a.scope,'sections':len(sections),'paragraphs':[{k:v for k,v in r.items() if k!='element'} for r in rs], 'notes':['Anchor matching is exact against top-level body paragraphs. Table-cell/text-box paragraphs cannot be used as insertion anchors.']}
            if a.output:safe_json(a.output,data)
            print(json.dumps(data,ensure_ascii=False,indent=2));return 0
        if a.command=='audit':
            result=audit(a.source,cfg,a.scope);paths=reports(result,a.report)
            print(json.dumps({'overall':result['overall'],'summary':result['summary'],'reports':paths},ensure_ascii=False,indent=2))
            threshold={'error':['error'],'warning':['error','warning'],'unresolved':['error','warning','conflict','unknown','manual'],'none':[]}[a.fail_on]
            return int(any(result['summary'][s] for s in threshold))
        if a.command=='convert':
            result=convert(a.source,a.output,cfg,a.scope,overwrite=a.overwrite)
            report=audit(a.output,cfg,a.scope);rp=a.output.with_suffix('.audit')
            paths=reports(report,rp);op=a.output.with_suffix('.bime.json');safe_json(op,result)
            print(json.dumps({'output':str(a.output),'language':result['language'],'audit':report['summary'],'reports':paths,'operation_report':str(op),'layout_verified':False},ensure_ascii=False,indent=2))
            return int(report['summary']['error']>0)
        if a.command=='insert':
            mode='at_end';anchor=''
            for opt in ('before','after','under'):
                value=getattr(a,opt)
                if value is not None:mode=opt;anchor=value
            result=insert(a.source,a.md,a.output,cfg,a.scope,mode=mode,anchor=anchor,occurrence=a.occurrence,overwrite=a.overwrite,dry_run=a.dry_run,expected_sha=a.expect_sha256,allow_draft=a.allow_draft,recipient_styles=not a.keep_bime_styles)
            report=result.pop('audit_after')
            if not a.dry_run:
                result['audit_reports']=reports(report,a.output.with_suffix('.audit'))
                safe_json(a.output.with_suffix('.bime.json'),result)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 1 if result['new_hard_violations'] else 0
    except (BimeError,FileNotFoundError,PermissionError,ValueError,KeyError,E.XMLSyntaxError,subprocess.TimeoutExpired) as exc:
        print('bime_word: '+str(exc),file=sys.stderr);return 2
    return 0
