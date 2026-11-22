"""Move DesktopService methods and module-level names into a mixin module verbatim.

usage: split_service.py <module> <MixinClass> <docstring> --methods a,b,c [--names X,Y]
Run from app/. Only moves text; a fix-up pass adds imports and prunes unused ones.
"""
import argparse, ast, builtins, re, sys
from pathlib import Path

DESKTOP = Path("agent/desktop")
SERVICE = DESKTOP / "service.py"


def span_with_comments(lines, node):
    start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])]) - 1
    while start > 0 and lines[start - 1].strip().startswith("#"):
        start -= 1
    return start, node.end_lineno


def import_block(src):
    tree = ast.parse(src)
    lines = src.split("\n")
    nodes = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) and not (isinstance(n, ast.ImportFrom) and n.module == "__future__")]
    return "\n".join("\n".join(lines[n.lineno - 1:n.end_lineno]) for n in nodes)


def module_level(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = node
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            out[node.targets[0].id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out[node.target.id] = node
    out.pop("DesktopService", None)
    return out


def referenced(nodes):
    return {n.id for node in nodes for n in ast.walk(node) if isinstance(n, ast.Name)}


def move(module, mixin, doc, methods, names):
    src = SERVICE.read_text()
    tree = ast.parse(src)
    lines = src.split("\n")
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DesktopService")
    # Take along every service module-level name the moved code uses (transitively).
    defs = module_level(tree)
    chosen = [n for n in cls.body if getattr(n, "name", None) in methods] + [defs[n] for n in names if n in defs]
    names = set(names)
    while True:
        extra = (referenced(chosen) & set(defs)) - names
        if not extra:
            break
        names |= extra
        chosen += [defs[n] for n in extra]
    print("module-level names moved:", sorted(names))
    spans, method_text, name_text = [], [], []
    found = set()
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in methods:
            a, b = span_with_comments(lines, node)
            spans.append((a, b)); method_text.append((a, "\n".join(lines[a:b]))); found.add(node.name)
    missing = set(methods) - found
    assert not missing, f"methods not found: {missing}"
    found = set()
    for node in tree.body:
        nm = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nm = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            nm = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nm = node.target.id
        if nm in names:
            a, b = span_with_comments(lines, node)
            spans.append((a, b)); name_text.append((a, "\n".join(lines[a:b]))); found.add(nm)
    missing = set(names) - found
    assert not missing, f"names not found: {missing}"
    removed = set()
    for a, b in spans:
        removed.update(range(a, b))
    kept = [l for i, l in enumerate(lines) if i not in removed]
    text = re.sub(r"\n{4,}", "\n\n\n", "\n".join(kept))
    # add the mixin import and base class
    text = text.replace("class DesktopService(", f"class DesktopService({mixin}, ", 1) if "class DesktopService(" in text \
        else text.replace("class DesktopService:", f"class DesktopService({mixin}):", 1)
    tree2 = ast.parse(text)
    last = max(n.end_lineno for n in tree2.body if isinstance(n, (ast.Import, ast.ImportFrom)))
    tl = text.split("\n"); tl.insert(last, f"from agent.desktop.{module} import {mixin}")
    SERVICE.write_text("\n".join(tl))
    body = []
    for _, t in sorted(name_text):
        body.append(t)
    methods_src = "\n\n".join(t for _, t in sorted(method_text))
    out = f'"""{doc}"""\n\nfrom __future__ import annotations\n\n{import_block(src)}\n\n\n'
    if body:
        out += "\n\n\n".join(body) + "\n\n\n"
    out += f"class {mixin}:\n    \"\"\"DesktopService methods moved here unchanged; `self` is the DesktopService.\"\"\"\n\n{methods_src}\n"
    (DESKTOP / f"{module}.py").write_text(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("module"); p.add_argument("mixin"); p.add_argument("doc")
    p.add_argument("--methods", default=""); p.add_argument("--names", default="")
    a = p.parse_args()
    move(a.module, a.mixin, a.doc, [m for m in a.methods.split(",") if m], [n for n in a.names.split(",") if n])
