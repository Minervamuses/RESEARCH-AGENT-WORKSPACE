#!/usr/bin/env python3
"""Optional local DOCX→PDF→PNG preview; never changes the input DOCX.

The emitted manifest explicitly does NOT certify fonts, page count, or visual QA.
An agent/person must inspect every PNG. LibreOffice output is not Word identity.
"""
from __future__ import annotations
import argparse,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--dpi',type=int,default=150);a=p.parse_args()
    if not a.source.is_file():p.error('DOCX does not exist.')
    soffice=shutil.which('soffice') or shutil.which('libreoffice');ppm=shutil.which('pdftoppm')
    if not soffice or not ppm:p.error('Install LibreOffice and Poppler, or preview the copy using Microsoft Word. No visual verification has been done.')
    if a.output_dir.exists() and any(a.output_dir.iterdir()):p.error('Use an empty preview directory to avoid confusing stale pages with this run.')
    if not 72<=a.dpi<=300:p.error('dpi must be 72–300')
    source=a.source.resolve();a.output_dir.mkdir(parents=True,exist_ok=True);out=a.output_dir.resolve();digest=hashlib.sha256(source.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='bime-preview-') as td:
        td=Path(td);profile=td/'lo-profile';home=td/'home';home.mkdir();env=dict(os.environ);env['HOME']=str(home)
        subprocess.run([soffice,'-env:UserInstallation='+profile.as_uri(),'--headless','--convert-to','pdf','--outdir',str(out),str(source)],check=True,capture_output=True,timeout=180,env=env)
    pdf=out/(source.stem+'.pdf')
    if not pdf.is_file():raise SystemExit('Renderer did not create the expected PDF; no verification claimed.')
    subprocess.run([ppm,'-png','-r',str(a.dpi),str(pdf),str(out/'page')],check=True,timeout=180)
    pages=sorted(out.glob('page-*.png'))
    if not pages:raise SystemExit('No page images were generated.')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise SystemExit('Input changed during preview; discard this run.')
    manifest={'source':str(source),'source_sha256':digest,'renderer':'LibreOffice + Poppler','page_images':[p.name for p in pages],'visual_inspection_completed':False,'font_identity_verified':False,'note':'Open every page PNG. Rendering alone is not inspection; Word may paginate differently.'}
    (out/'preview.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(manifest,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
