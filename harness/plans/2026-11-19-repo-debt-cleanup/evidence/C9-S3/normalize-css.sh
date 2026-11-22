#!/usr/bin/env bash
# usage: normalize-css.sh OUTFILE  (run in app/desktop). Builds with vite into a temp dir,
# then prints the emitted CSS one rule per line, whitespace-insensitive.
set -e
out=$(mktemp -d)
vite_bin=./node_modules/.bin/vite
$vite_bin build --outDir "$out" --emptyOutDir >/dev/null
cat "$out"/assets/*.css | python3 -I -c '
import re,sys
css=sys.stdin.read()
css=re.sub(r"/\*.*?\*/","",css,flags=re.S)
css=re.sub(r"\s+"," ",css)
css=re.sub(r"\s*([{};,:>])\s*",r"\1",css)
out=[];buf="";depth=0;stack=[]
for ch in css:
    if ch=="{":
        # at-rule container (contains nested rules) is decided lazily: look ahead not possible, so mark
        stack.append(len(buf)); buf+=ch; depth+=1
    elif ch=="}":
        buf+=ch; depth-=1
        stack.pop()
        if depth==0:
            out.append(buf); buf=""
    else:
        buf+=ch
# split top-level at-rules with nested rules (@media/@supports/@layer) into opener, inner rules, closer
res=[]
for r in out:
    if re.match(r"@(media|supports|layer|container)",r) and r.count("{")>1:
        head,body=r.split("{",1); body=body[:-1]
        res.append(head+"{")
        for m in re.finditer(r"[^{}]+\{[^{}]*\}",body): res.append("  "+m.group(0))
        res.append("}")
    else: res.append(r)
print("\n".join(res))
'
rm -rf "$out"
