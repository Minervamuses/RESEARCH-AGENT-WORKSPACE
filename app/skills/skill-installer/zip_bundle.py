"""Inspect and prepare one local skill ZIP using only the standard library."""

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile


def _members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members = {}
    for info in archive.infolist():
        name = info.filename.rstrip("/") if info.is_dir() else info.filename
        parts = name.split("/")
        if (not name or "\\" in name or "\x00" in info.orig_filename
                or name.startswith("/") or (len(name) > 1 and name[1] == ":")
                or any(part in {"", ".", ".."} for part in parts)):
            raise ValueError(f"unsafe ZIP path: {info.orig_filename}")
        file_type = stat.S_IFMT(info.external_attr >> 16)
        allowed_type = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
        if file_type not in {0, allowed_type}:
            raise ValueError(f"symlink or special ZIP member: {name}")
        if name in members:
            raise ValueError(f"duplicate ZIP member: {name}")
        members[name] = info
    for name in members:
        for parent in PurePosixPath(name).parents:
            previous = members.get(str(parent))
            if previous is not None and not previous.is_dir():
                raise ValueError(f"ZIP file/directory conflict: {parent}")
    return members


def _read(archive: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int) -> bytes:
    if info.file_size > limit:
        raise ValueError(f"file exceeds size limit: {info.filename}")
    with archive.open(info) as source:
        content = source.read(limit + 1)
    if len(content) > limit or len(content) != info.file_size:
        raise ValueError(f"file exceeds size limit or differs from ZIP size: {info.filename}")
    return content


def _selected(
    archive: zipfile.ZipFile, root: str, *, max_file_bytes: int = 8 * 1024 * 1024,
    max_files: int = 512, max_bundle_bytes: int = 64 * 1024 * 1024,
) -> dict[str, zipfile.ZipInfo]:
    members = _members(archive)
    prefix = "" if root == "." else root + "/"
    skill = members.get(prefix + "SKILL.md")
    if skill is None or skill.is_dir():
        raise ValueError("selected root must directly contain a regular SKILL.md")
    selected = {name[len(prefix):]: info for name, info in members.items()
                if name.startswith(prefix) and name != prefix.rstrip("/")}
    files = [info for info in selected.values() if not info.is_dir()]
    if len(files) > max_files:
        raise ValueError("bundle exceeds file-count limit")
    if any(info.file_size > max_file_bytes for info in files):
        raise ValueError("file exceeds size limit")
    if sum(info.file_size for info in files) > max_bundle_bytes:
        raise ValueError("bundle exceeds total-size limit")
    return selected


def inspect_archive(
    archive: str | Path, *, max_file_bytes: int = 8 * 1024 * 1024,
    max_files: int = 512, max_bundle_bytes: int = 64 * 1024 * 1024,
) -> list[dict[str, str]]:
    """List raw SKILL.md candidates; bundle limits apply only when selecting one."""
    with zipfile.ZipFile(archive) as source:
        members = _members(source)
        return [
            {"root": str(PurePosixPath(name).parent),
             "skill_md": _read(source, info, max_file_bytes).decode("utf-8")}
            for name, info in sorted(members.items())
            if PurePosixPath(name).name == "SKILL.md" and not info.is_dir()
        ]


def extract_archive(
    archive: str | Path, root: str, destination: str | Path, **limits: int,
) -> Path:
    """Prepare original bundle files in a new directory; never execute their code."""
    destination = Path(destination)
    with zipfile.ZipFile(archive) as source:
        selected = _selected(source, root, **limits)
        destination.mkdir(mode=0o700)
        try:
            for name, info in selected.items():
                target = destination / name
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                content = _read(source, info, limits.get("max_file_bytes", 8 * 1024 * 1024))
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output:
                    output.write(content)
                target.chmod(0o755 if info.external_attr >> 16 & 0o111 else 0o644)
        except Exception:
            shutil.rmtree(destination)
            raise
    return destination


def verify_prepared(
    archive: str | Path, root: str, prepared: str | Path, **limits: int,
) -> None:
    """Require original file bytes and executable flags, matching manager identity."""
    prepared = Path(prepared)
    if prepared.is_symlink() or not prepared.is_dir():
        raise ValueError("prepared bundle must be a regular directory")
    with zipfile.ZipFile(archive) as source:
        selected = _selected(source, root, **limits)
        expected = {name: info for name, info in selected.items() if not info.is_dir()}
        actual = {}
        for path in prepared.rglob("*"):
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError(f"symlink or special prepared file: {path.name}")
            if stat.S_ISREG(mode):
                actual[path.relative_to(prepared).as_posix()] = path
        if actual.keys() != expected.keys():
            raise ValueError("prepared bundle files differ from original ZIP")
        for name, info in expected.items():
            path = actual[name]
            if (path.stat().st_size != info.file_size
                    or bool(path.stat().st_mode & 0o111) != bool(info.external_attr >> 16 & 0o111)
                    or path.read_bytes() != _read(
                        source, info, limits.get("max_file_bytes", 8 * 1024 * 1024))):
                raise ValueError(f"prepared bundle differs from original ZIP: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "extract"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--root")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("--max-files", type=int, default=512)
    parser.add_argument("--max-bundle-bytes", type=int, default=64 * 1024 * 1024)
    args = parser.parse_args()
    limits = {"max_file_bytes": args.max_file_bytes, "max_files": args.max_files,
              "max_bundle_bytes": args.max_bundle_bytes}
    try:
        if args.action == "inspect":
            result = inspect_archive(args.archive, **limits)
        else:
            if args.root is None or args.destination is None:
                parser.error("extract requires --root and --destination")
            result = {"prepared": str(extract_archive(
                args.archive, args.root, args.destination, **limits))}
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        parser.exit(1, f"ZIP preparation failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
