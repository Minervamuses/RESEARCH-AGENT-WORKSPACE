"""Add missing desktop-module imports and drop unused imports in agent/desktop modules.

usage: fixup_imports.py file1.py file2.py ...  (run from app/)
A missing name is imported from the agent.desktop module that defines it at
module level (never from service.py, which would create an import cycle).
"""
import ast, builtins, sys
from pathlib import Path

DESKTOP = Path("agent/desktop")


def module_defs(path):
    tree = ast.parse(path.read_text())
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return out


def used_and_defined(tree):
    defined = set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                defined.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            defined.add(n.id)
        elif isinstance(n, ast.arg):
            defined.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            defined.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            defined.update(n.names)
        elif isinstance(n, ast.comprehension):
            for t in ast.walk(n.target):
                if isinstance(t, ast.Name):
                    defined.add(t.id)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    return used, defined


def fix(path, owners):
    src = path.read_text()
    tree = ast.parse(src)
    used, defined = used_and_defined(tree)
    missing = sorted(used - defined)
    additions = {}
    for name in missing:
        owner = owners.get(name)
        if owner is None or owner == path.stem:
            print(f"{path}: UNRESOLVED {name}")
            continue
        if owner == "service":
            print(f"{path}: needs {name} from service.py (move it to a lower module)")
            continue
        additions.setdefault(owner, []).append(name)
    lines = src.split("\n")
    if additions:
        last = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
        for owner in sorted(additions, reverse=True):
            lines.insert(last, f"from agent.desktop.{owner} import {', '.join(sorted(additions[owner]))}")
    src = "\n".join(lines)
    # prune unused imports
    tree = ast.parse(src)
    lines = src.split("\n")
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    keep_all = path.name == "service.py"  # service re-exports names tests import
    reexport = {"DesktopService", "DesktopServiceError", "DesktopKnowledgeOperations", "_TurnWork"}
    edits = []
    for n in tree.body:
        if not isinstance(n, (ast.Import, ast.ImportFrom)) or (isinstance(n, ast.ImportFrom) and n.module == "__future__"):
            continue
        names = [a for a in n.names if (a.asname or a.name).split(".")[0] in used or (keep_all and (a.asname or a.name) in reexport)]
        if len(names) == len(n.names):
            continue
        if not names:
            new = None
        elif isinstance(n, ast.Import):
            new = "import " + ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in names)
        else:
            parts = [a.name + (f" as {a.asname}" if a.asname else "") for a in names]
            joined = ", ".join(parts)
            head = f"from {'.' * n.level}{n.module or ''} import "
            new = head + joined if len(head + joined) <= 100 else head + "(\n" + "".join(f"    {p},\n" for p in parts) + ")"
        edits.append((n.lineno - 1, n.end_lineno, new))
    for a, b, new in sorted(edits, reverse=True):
        lines[a:b] = [] if new is None else [new]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    owners = {}
    for p in sorted(DESKTOP.glob("*.py"), key=lambda q: q.name == "service.py"):
        for name in module_defs(p):
            owners.setdefault(name, p.stem)
    for f in sys.argv[1:]:
        fix(Path(f), owners)
