"""Sequential, offline project verification with logs and honest evidence statuses.

python -B backend/tools/verify_project.py --output /path/to/fresh-artifacts
Use --require-ltspice for a strict native-netlist gate and --visual for rendered
and native visual evidence. REVIEW exits zero, but is never reported as PASS.
No packages are installed. Output directories must be new or empty.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
CATEGORY_ORDER = ("backend", "frontend", "typescript", "build", "electrical",
                  "routing", "ltspice", "visual")
LABELS = dict(zip(CATEGORY_ORDER, ("Backend", "Frontend", "TypeScript", "Build",
                                  "Electrical", "Routing", "LTspice", "Visual")))
GENERATED_FILES = ("next-env.d.ts", "tsconfig.tsbuildinfo")


def positive_timeout(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return result


def positive_samples(value: str) -> int:
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError("samples must be positive")
    return result


def backend_python(root: Path = ROOT) -> str:
    """Use the project's existing virtualenv; never create or install one."""
    for environment in (".venv", "venv"):
        for executable in ("Scripts/python.exe", "bin/python"):
            candidate = root / "backend" / environment / executable
            if candidate.is_file():
                return str(candidate)
    return sys.executable


def backend_command(root: Path = ROOT) -> list[str]:
    return [backend_python(root), "-B", "-m", "unittest", "discover", "-s",
            str(root / "backend/tests"), "-p", "test_*.py", "-v"]


def npm_command() -> list[str]:
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm") or "npm"
    # Invoke npm's JS entrypoint on Windows where possible. This bypasses .cmd
    # shell quoting for project/output paths containing spaces or metacharacters.
    if os.name == "nt":
        cli = Path(executable).parent / "node_modules/npm/bin/npm-cli.js"
        node = shutil.which("node")
        if node and cli.is_file():
            return [node, str(cli)]
    return [executable]


def prepare_output(requested: Path | None, root: Path = ROOT) -> Path:
    if requested is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        requested = root / "backend/tests/artifacts/verification" / f"{stamp}-{os.getpid()}"
    lexical = Path(os.path.abspath(requested.expanduser()))
    if any(part.is_symlink() for part in (lexical, *lexical.parents)):
        raise ValueError("output must not traverse a symbolic link")
    output = lexical.resolve()
    root = root.resolve()
    if output == root or output in root.parents:
        raise ValueError("output must not be the project root or one of its ancestors")
    if output == root / "backend" or (root / "frontend") in (output, *output.parents):
        raise ValueError("output must not be a source directory")
    if (root / "backend") in output.parents:
        artifacts = root / "backend/tests/artifacts"
        if artifacts not in output.parents:
            raise ValueError("backend output must be a child of backend/tests/artifacts")
    if any(part.casefold() in {".git", "node_modules", ".venv", "venv"}
           for part in output.parts):
        raise ValueError("output must not be inside git metadata or dependencies")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output directory must be new or empty (stale evidence is not reused)")
    output.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also rejects another verifier choosing this empty folder.
    with (output / ".verification-run").open("x", encoding="utf-8") as handle:
        handle.write(f"pid={os.getpid()}\n")
    (output / "logs").mkdir()
    return output


def _terminate_tree(process: subprocess.Popen) -> str | None:
    """Reap descendants on timeout before another gate can launch LTspice."""
    try:
        if os.name == "nt":
            stopped = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, text=True, errors="replace", timeout=30,
                check=False,
            )
            if stopped.returncode and process.poll() is None:
                process.kill()
                return f"process-tree cleanup failed: {stopped.stderr or stopped.stdout}"
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except (OSError, subprocess.SubprocessError) as exc:
        if process.poll() is None:
            process.kill()
        return f"process-tree cleanup failed: {exc}"
    return None


def run_command(name: str, command: Sequence[str], *, cwd: Path, output: Path,
                timeout: float) -> dict:
    stdout_path = output / "logs" / f"{name}.stdout.log"
    stderr_path = output / "logs" / f"{name}.stderr.log"
    started = time.monotonic()
    returncode = None
    error = None
    timed_out = False
    cleanup_error = None
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       NEXT_TELEMETRY_DISABLED="1", NPM_CONFIG_UPDATE_NOTIFIER="false")
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
               else {"start_new_session": True})
    # File streams keep even timeout/crash output, without unbounded in-memory logs.
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            process = subprocess.Popen(list(command), cwd=str(cwd), env=environment,
                                       stdout=stdout, stderr=stderr, **options)
            try:
                returncode = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                error = f"command timed out after {timeout:g}s"
                cleanup_error = _terminate_tree(process)
                try:
                    returncode = process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    cleanup_error = cleanup_error or "process did not exit after termination"
        except OSError as exc:
            error = f"could not start command: {exc}"
        if error:
            stderr.write((f"\n[verification] {error}\n").encode("utf-8"))
        if cleanup_error:
            stderr.write((f"[verification] {cleanup_error}\n").encode("utf-8"))
    return {"name": name, "command": list(command), "cwd": str(cwd),
            "status": "PASS" if returncode == 0 and not error else "FAIL",
            "returncode": returncode, "timed_out": timed_out,
            "timeout_seconds": timeout, "duration_seconds": round(time.monotonic() - started, 3),
            "stdout_log": str(stdout_path.relative_to(output)).replace("\\", "/"),
            "stderr_log": str(stderr_path.relative_to(output)).replace("\\", "/"),
            "error": error, "cleanup_error": cleanup_error}


@dataclass(frozen=True)
class FileSnapshot:
    data: bytes | None
    identity: tuple[int, int, int, int] | None


def snapshot(path: Path) -> FileSnapshot:
    if path.is_symlink():
        raise ValueError(f"refusing generated-file symlink: {path}")
    try:
        first = path.stat()
    except FileNotFoundError:
        return FileSnapshot(None, None)
    data = path.read_bytes()
    last = path.stat()
    identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    if identity(first) != identity(last):
        raise ValueError(f"file changed while taking snapshot: {path}")
    return FileSnapshot(data, identity(last))


def known_generated_change(name: str, before: bytes | None, after: bytes | None) -> bool:
    """Only recognize Next's route import and a structured TS compiler cache.

    This is a conservative ownership check, not a git checkout: custom edits are
    conflicts. A second identity+byte check protects edits after the build ends.
    """
    if after is None:
        return False
    try:
        if name == "next-env.d.ts":
            text = after.decode("utf-8").replace("\r\n", "\n")
            route = r'^import [\"\']\./\.next/(?:dev/)?types/routes\.d\.ts[\"\'];?\n'
            clean = lambda value: re.sub(route, "", value, flags=re.MULTILINE)
            if before is not None:
                return clean(text) == clean(before.decode("utf-8").replace("\r\n", "\n"))
            canonical = ('/// <reference types="next" />\n'
                         '/// <reference types="next/image-types/global" />\n\n'
                         '// NOTE: This file should not be edited\n'
                         '// see https://nextjs.org/docs/app/api-reference/config/typescript '
                         'for more information.\n')
            return clean(text) == canonical
        if name == "tsconfig.tsbuildinfo":
            payload = json.loads(after)
            allowed = {"fileNames", "fileIdsList", "fileInfos", "root", "options",
                       "referencedMap", "affectedFilesPendingEmit", "version",
                       "semanticDiagnosticsPerFile", "emitDiagnosticsPerFile",
                       "latestChangedDtsFile", "pendingEmit", "checkPending", "errors"}
            return (isinstance(payload, dict) and set(payload).issubset(allowed)
                    and isinstance(payload.get("version"), str)
                    and isinstance(payload.get("fileNames"), list)
                    and isinstance(payload.get("fileInfos"), list)
                    and isinstance(payload.get("options"), dict))
    except (ValueError, UnicodeError):
        pass
    return False


def restore_generated(frontend: Path, before: dict[str, FileSnapshot],
                      after: dict[str, FileSnapshot]) -> list[str]:
    conflicts = []
    for name in GENERATED_FILES:
        original, generated = before[name], after[name]
        if original.data == generated.data:
            continue
        path = frontend / name
        try:
            if not known_generated_change(name, original.data, generated.data):
                raise ValueError("unexpected change; leaving current bytes untouched")
            if snapshot(path) != generated:
                raise ValueError("concurrent change after build; leaving current bytes untouched")
            if original.data is None:
                path.unlink()
            else:
                # Recheck through the opened handle; do not replace an unexpected file.
                with path.open("r+b") as handle:
                    stat = os.fstat(handle.fileno())
                    identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                    if identity != generated.identity or handle.read() != generated.data:
                        raise ValueError("concurrent change during restore; leaving bytes untouched")
                    handle.seek(0)
                    handle.write(original.data)
                    handle.truncate()
        except (OSError, ValueError) as exc:
            conflicts.append(f"{name}: {exc}")
    return conflicts


def status(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("status", value.get("overall", value.get("result")))
    if isinstance(value, str):
        key = value.strip().upper()
        if key in {"PASS", "PASSED", "OK", "SUCCESS"}:
            return "PASS"
        if key in {"FAIL", "FAILED", "ERROR", "TIMEOUT"}:
            return "FAIL"
    # Missing, skipped, unavailable, and unknown statuses are never evidence of PASS.
    return "REVIEW"


def worst(values: Sequence[str]) -> str:
    return "FAIL" if "FAIL" in values else "REVIEW" if "REVIEW" in values else "PASS"


def read_regression(path: Path, require_ltspice: bool) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("report must be an object")
        raw_categories = payload.get("categories", {})
        if isinstance(raw_categories, list):
            raw_categories = {item["name"]: item for item in raw_categories
                              if isinstance(item, dict) and isinstance(item.get("name"), str)}
        if not isinstance(raw_categories, dict):
            raise ValueError("report categories must be an object or named list")
        categories = {str(key).casefold(): status(value) for key, value in raw_categories.items()}
        notes = []
        for name in ("compiler", "export", "electrical", "routing", "ltspice", "visual"):
            if name not in categories:
                categories[name] = "REVIEW"
                notes.append(f"{name}: no explicit evidence in regression report")
        if require_ltspice and categories["ltspice"] != "PASS":
            categories["ltspice"] = "FAIL"
            notes.append("LTspice is required but native validation did not pass")
        circuits = payload.get("circuits", [])
        if not isinstance(circuits, list):
            raise ValueError("report circuits must be a list")
        if not circuits:
            notes.append("no circuit evidence in regression report")
        overall = worst([status(payload.get("overall")), *categories.values(),
                         "PASS" if circuits else "REVIEW"])
        return {"path": str(path), "overall": overall, "categories": categories,
                "circuits": circuits, "notes": notes, "error": None}
    except (OSError, ValueError) as exc:
        return {"path": str(path), "overall": "FAIL",
                "categories": {key: "FAIL" for key in ("electrical", "routing", "ltspice", "visual")},
                "circuits": [], "notes": [], "error": f"cannot read regression evidence: {exc}"}


def markdown_report(report: dict) -> str:
    lines = ["# Project verification", "", f"Overall: **{report['overall']}**", "",
             "REVIEW means incomplete or unreviewed evidence, not a passing gate.", "",
             "| Gate | Status |", "| --- | --- |"]
    lines.extend(f"| {LABELS[name]} | {report['categories'][name]} |" for name in CATEGORY_ORDER)
    lines.extend(["", "## Commands", "", "| Command | Status | Exit | Timeout | Logs |",
                  "| --- | --- | --- | --- | --- |"])
    for command in report["commands"]:
        code = command["returncode"] if command["returncode"] is not None else "not available"
        logs = (f"[stdout]({command['stdout_log']}) / [stderr]({command['stderr_log']})")
        lines.append(f"| {command['name']} | {command['status']} | {code} | "
                     f"{command['timed_out']} | {logs} |")
    lines.extend(["", "## Evidence", "", "Regression: [regression report](regression/regression_report.json)",
                  f"Circuit records: {len(report['regression']['circuits'])}",
                  f"Compiler: {report['regression']['categories'].get('compiler', 'REVIEW')}; "
                  f"Export: {report['regression']['categories'].get('export', 'REVIEW')}"])
    notes = [*report["build_conflicts"], *report["regression"]["notes"]]
    if report["regression"]["error"]:
        notes.append(report["regression"]["error"])
    for command in report["commands"]:
        notes.extend(str(command[key]) for key in ("error", "cleanup_error") if command.get(key))
    if notes:
        lines.extend(["", "## Notices", "", *("- " + note.replace("\n", " ") for note in notes)])
    return "\n".join(lines) + "\n"


def verify(*, root: Path, output: Path, timeout: float, samples: int,
           require_ltspice: bool = False, visual: bool = False) -> dict:
    frontend = root / "frontend"
    npm = npm_command()
    commands = []

    def run(name: str, argv: Sequence[str], cwd: Path = root) -> dict:
        result = run_command(name, argv, cwd=cwd, output=output, timeout=timeout)
        commands.append(result)
        return result

    run("backend", backend_command(root), root / "backend")
    run("frontend", [*npm, "--prefix", str(frontend), "test"])
    run("typescript-before-build", [*npm, "--prefix", str(frontend), "run", "typecheck"])
    before = {}
    conflicts = []
    for name in GENERATED_FILES:
        try:
            before[name] = snapshot(frontend / name)
        except (OSError, ValueError) as exc:
            conflicts.append(f"{name}: cannot preserve pre-build bytes: {exc}")
    # Unsafe snapshots do not silently skip a build: record an explicit failed gate.
    if len(before) == len(GENERATED_FILES):
        run("build", [*npm, "--prefix", str(frontend), "run", "build"])
        after = {}
        for name in GENERATED_FILES:
            try:
                after[name] = snapshot(frontend / name)
            except (OSError, ValueError) as exc:
                conflicts.append(f"{name}: cannot inspect build side effects: {exc}")
        for name in GENERATED_FILES:
            if name not in after:
                after[name] = before[name]  # Already reported; never overwrite this path.
        conflicts.extend(restore_generated(frontend, before, after))
    else:
        _record_blocked(commands, "build", output, timeout,
                        "Build blocked: generated-file snapshots are unsafe", root)
    # Next ignores TypeScript errors; this independent check MUST follow restoration.
    run("typescript-after-restore", [*npm, "--prefix", str(frontend), "run", "typecheck"])
    regression_command = [sys.executable, "-B", str(root / "backend/tools/run_regression.py"),
                          "--output", str(output / "regression"), "--samples", str(samples)]
    if require_ltspice:
        regression_command.append("--require-ltspice")
    if visual:
        regression_command.extend(["--render", "--native"])
    if any(item.get("cleanup_error") for item in commands):
        _record_blocked(commands, "regression", output, timeout,
                        "Regression blocked: timed-out process tree may still own LTspice", root)
    else:
        run("regression", regression_command)
    regression = read_regression(output / "regression/regression_report.json", require_ltspice)
    by_name = {item["name"]: item for item in commands}
    categories = {"backend": by_name["backend"]["status"],
                  "frontend": by_name["frontend"]["status"],
                  "typescript": worst([by_name["typescript-before-build"]["status"],
                                       by_name["typescript-after-restore"]["status"]]),
                  "build": "FAIL" if conflicts else by_name["build"]["status"]}
    categories.update({name: regression["categories"][name]
                       for name in ("electrical", "routing", "ltspice", "visual")})
    report = {"overall": worst([*categories.values(), regression["overall"],
                                *(item["status"] for item in commands)]),
              "created_at": datetime.now(timezone.utc).isoformat(), "root": str(root),
              "output": str(output), "options": {"timeout_seconds": timeout, "samples": samples,
                                                   "require_ltspice": require_ltspice, "visual": visual},
              "interpreters": {"orchestrator_and_rendering": sys.executable,
                               "backend_unittest": backend_python(root)},
              "categories": categories, "commands": commands, "build_conflicts": conflicts,
              "regression": regression}
    with (output / "verification_report.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    with (output / "verification_report.md").open("x", encoding="utf-8") as handle:
        handle.write(markdown_report(report))
    return report


def refresh_report(output: Path) -> dict:
    """Reaggregate after hash-bound human review, without rerunning any commands.

    The caller updates regression_report.json using its review helper first.
    Existing failing command statuses and build conflicts cannot be erased by a
    later visual acceptance. Only this run's two aggregate reports are rewritten.
    """
    output = Path(output).resolve()
    json_path, md_path = output / "verification_report.json", output / "verification_report.md"
    saved_json, saved_md = snapshot(json_path), snapshot(md_path)
    if saved_json.data is None or saved_md.data is None:
        raise ValueError("both existing verification reports are required for refresh")
    report = json.loads(saved_json.data)
    regression = read_regression(output / "regression/regression_report.json",
                                 report["options"]["require_ltspice"])
    report["regression"] = regression
    by_name = {item["name"]: item for item in report["commands"]}
    categories = report["categories"]
    for name in ("backend", "frontend", "build"):
        categories[name] = status(by_name[name]["status"])
    categories["typescript"] = worst([status(by_name["typescript-before-build"]["status"]),
                                      status(by_name["typescript-after-restore"]["status"])])
    if report["build_conflicts"]:
        categories["build"] = "FAIL"
    categories.update({name: regression["categories"][name]
                       for name in ("electrical", "routing", "ltspice", "visual")})
    report["overall"] = worst([*categories.values(), regression["overall"],
                               *(status(item["status"]) for item in report["commands"])])
    report["refreshed_at"] = datetime.now(timezone.utc).isoformat()
    if snapshot(json_path) != saved_json or snapshot(md_path) != saved_md:
        raise ValueError("aggregate reports changed concurrently; refresh refused")
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(report), encoding="utf-8")
    return report


def _record_blocked(commands: list[dict], name: str, output: Path, timeout: float,
                    reason: str, root: Path) -> None:
    stdout, stderr = output / "logs" / f"{name}.stdout.log", output / "logs" / f"{name}.stderr.log"
    with stdout.open("x", encoding="utf-8"):
        pass
    with stderr.open("x", encoding="utf-8") as handle:
        handle.write(reason + "\n")
    commands.append({"name": name, "command": [], "cwd": str(root), "status": "FAIL",
                     "returncode": None, "timed_out": False, "timeout_seconds": timeout,
                     "duration_seconds": 0, "stdout_log": f"logs/{stdout.name}",
                     "stderr_log": f"logs/{stderr.name}", "error": reason, "cleanup_error": None})


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new/empty directory; default: fresh timestamped artifacts")
    parser.add_argument("--require-ltspice", action="store_true")
    parser.add_argument("--visual", action="store_true", help="request both rendered and native visual evidence")
    parser.add_argument("--timeout", type=positive_timeout, default=900, help="per-command timeout in seconds")
    parser.add_argument("--samples", type=positive_samples, default=3, help="regression timing sample count")
    parser.add_argument("--backend-only", action="store_true", help="run only unittests with the backend virtualenv")
    args = parser.parse_args(argv)
    if args.backend_only:
        if args.output or args.require_ltspice or args.visual:
            parser.error("--backend-only does not accept verification output or evidence flags")
        # This mode is just a portable interpreter wrapper, not another verification run.
        try:
            result = subprocess.run(backend_command(), cwd=str(ROOT / "backend"),
                                    timeout=args.timeout, check=False)
            return result.returncode
        except subprocess.TimeoutExpired:
            print("Backend tests timed out", file=sys.stderr)
            return 124
        except OSError as exc:
            print(f"Cannot launch backend tests: {exc}", file=sys.stderr)
            return 2
    try:
        output = prepare_output(args.output)
        report = verify(root=ROOT, output=output, timeout=args.timeout, samples=args.samples,
                        require_ltspice=args.require_ltspice, visual=args.visual)
    except (OSError, ValueError) as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        return 2
    print(f"Overall: {report['overall']}")
    for name in CATEGORY_ORDER:
        print(f"{LABELS[name]:12} {report['categories'][name]}")
    print(f"JSON: {output / 'verification_report.json'}")
    print(f"Report: {output / 'verification_report.md'}")
    return 1 if report["overall"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
