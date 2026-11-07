"""R4-S3: export the R3-S3 positive proposal copy through DesktopService.dispatch.

Usage (from app/): python <this file> <R3-S3 positive dir> <new empty work dir> <evidence dir>
Only the three inputs are copied; generated files from R3-S3 are never reused.
"""

import asyncio
import hashlib
import json
import shutil
import sys
from pathlib import Path

INPUTS = {  # SHA-256 recorded in evidence/R3-S3/inputs.txt
    "proposal.md": "ed3a0e84d1d7701c7772448e2e2835bc1075ffefaac9d42a31a5b6bc28cf0f89",
    "references.json": "af01074a7aa25fae53bf6970a3a86b07a34cd4a2bad8cb902f5fdabf7c94d6a5",
    "bime-proposal-profile.json": "8a54bd725142626784400027227522aa607f4c40c2d8457c9f2bb3cad28ca2bf",
}
R3_CLI_AUDIT = {"error": 0, "warning": 0, "conflict": 0, "unknown": 0, "manual": 11}  # R3-S3 positive stdout


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def main(positive: Path, work: Path, evidence: Path) -> dict:
    from agent.config import AgentConfig
    from agent.desktop.protocol import validate_result_data
    from agent.desktop.service import DesktopService

    project, runtime = work / "project", work / "runtime"
    project.mkdir(parents=True)
    runtime.mkdir()
    for name, digest in INPUTS.items():
        assert sha(positive / name) == digest, f"{name} differs from the R3-S3 positive input"
        shutil.copy2(positive / name, project / name)
    assert sorted(p.name for p in project.iterdir()) == sorted(INPUTS)
    source_before = sha(project / "proposal.md")

    service = DesktopService(
        original_cwd=project,
        environ={"CONDA_DEFAULT_ENV": "app", "CONDA_PREFIX": str(Path(sys.executable).parent.parent)},
        config=AgentConfig(
            persist_dir=str(runtime / "store"), citation_output_dir=str(runtime / "cite"),
            extension_dropin_dir=str(runtime / "dropin"), extension_state_dir=str(runtime / "state"),
        ),
    )
    preview = await service.dispatch("workspace.select", {"rootPath": str(project), "action": "inspect"})
    await service.dispatch("workspace.select", {
        "rootPath": str(project), "action": "initialize",
        "historyDirectory": preview["historyDirectory"], "expectedFingerprint": preview["researchFingerprint"],
    })
    context = await service.dispatch("document.open", {"path": str(project / "proposal.md")})
    inspect = await service.dispatch("bibliography.inspect", {"documentContext": context})
    data = await service.dispatch("bibliography.export", {"documentContext": context, "format": "bime_docx"})
    validate_result_data("bibliography.export", data)

    target = project / "proposal.bime.docx"
    reports = [project / f"proposal.bime{suffix}" for suffix in (".audit.json", ".audit.md", ".bime.json")]
    summary = json.loads(reports[0].read_text(encoding="utf-8"))["summary"]
    checks = {
        "response path is the new copy's proposal.bime.docx": data["path"] == str(target) and target.is_file(),
        "three reports exist": all(path.is_file() for path in reports),
        "reportPath is the copy's .audit.md": data["audit"]["reportPath"] == str(reports[1]),
        "audit equals the report summary": (data["audit"]["errors"], data["audit"]["warnings"], data["audit"]["manualChecks"])
        == (summary["error"], summary["warning"], summary["manual"]),
        "summary equals the R3-S3 positive CLI audit": summary == R3_CLI_AUDIT,
        "layoutVerified is false": data["audit"]["layoutVerified"] is False,
        "source copy bytes unchanged": sha(project / "proposal.md") == source_before,
        "bibliography was the project's references.json": inspect["libraryPath"] == str(project / "references.json"),
    }
    for path in reports:
        shutil.copy2(path, evidence / path.name)
    result = {
        "work_dir": str(work), "response": data, "report_summary": summary,
        "library": {"path": inspect["libraryPath"], "status": inspect["libraryStatus"], "entries": len(inspect["entries"])},
        "missing_keys": inspect["missing"], "docx_sha256": sha(target), "docx_bytes": target.stat().st_size,
        "checks": checks,
    }
    (evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    outcome = asyncio.run(main(*(Path(arg).resolve() for arg in sys.argv[1:4])))
    print(json.dumps(outcome["checks"], indent=2))
    sys.exit(0 if all(outcome["checks"].values()) else 1)
