"""Offline orchestration tests: every child command is mocked (no recursion/build)."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from tools import verify_project as verification


NEXT_ENV = (b'/// <reference types="next" />\r\n'
            b'/// <reference types="next/image-types/global" />\r\n'
            b'import "./.next/dev/types/routes.d.ts";\r\n\r\n'
            b'// NOTE: This file should not be edited\r\n'
            b'// see https://nextjs.org/docs/app/api-reference/config/typescript '
            b'for more information.\r\n')
BUILD_ENV = NEXT_ENV.replace(b".next/dev/types", b".next/types").replace(b"\r\n", b"\n")
BUILD_INFO = json.dumps({"fileNames": ["a.ts"], "fileInfos": ["hash"],
                         "options": {"strict": True}, "version": "5.7.3"}).encode()


def regression_payload(*, ltspice="PASS", visual="PASS", overall="PASS"):
    return {"overall": overall,
            "categories": {"compiler": "PASS", "export": "PASS", "electrical": "PASS",
                           "routing": "PASS", "ltspice": ltspice, "visual": visual},
            "circuits": [{"id": "test-circuit", "status": "PASS"}]}


class VerificationCommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project with spaces"
        self.frontend = self.root / "frontend"
        self.frontend.mkdir(parents=True)
        (self.root / "backend/tests").mkdir(parents=True)
        (self.frontend / "next-env.d.ts").write_bytes(NEXT_ENV)
        # Deliberately arbitrary pre-existing bytes must be restored, not regenerated.
        (self.frontend / "tsconfig.tsbuildinfo").write_bytes(b"original dirty cache\x00\xff")
        self.output = verification.prepare_output(self.root / "artifacts/run", self.root)
        # A test must never execute a real child even if an orchestration mock is removed.
        self.no_process = patch.object(verification.subprocess, "Popen",
                                       side_effect=AssertionError("unexpected real child process"))
        self.no_process.start()
        self.addCleanup(self.no_process.stop)
        self.calls = []
        self.payload = regression_payload()
        self.failures = set()
        self.build_action = lambda: None

    def fake_command(self, name, command, *, cwd, output, timeout):
        self.calls.append((name, list(command), cwd, timeout))
        stdout_path, stderr_path = output / "logs" / f"{name}.stdout.log", output / "logs" / f"{name}.stderr.log"
        stdout_path.write_text(f"{name} output\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if name == "build":
            self.build_action()
        if name == "typescript-after-restore" and "build" not in self.failures:
            self.after_restore_bytes = (self.frontend / "next-env.d.ts").read_bytes()
        if name == "regression" and self.payload is not None:
            directory = output / "regression"
            directory.mkdir()
            (directory / "regression_report.json").write_text(json.dumps(self.payload), encoding="utf-8")
        return {"name": name, "command": list(command), "cwd": str(cwd),
                "status": "FAIL" if name in self.failures else "PASS",
                "returncode": 7 if name in self.failures else 0, "timed_out": False,
                "timeout_seconds": timeout, "duration_seconds": 0.01,
                "stdout_log": f"logs/{stdout_path.name}", "stderr_log": f"logs/{stderr_path.name}",
                "error": None, "cleanup_error": None}

    def run_verification(self, **kwargs):
        with patch.object(verification, "run_command", side_effect=self.fake_command):
            return verification.verify(root=self.root, output=self.output,
                                       timeout=41, samples=2, **kwargs)

    def test_sequential_commands_explicit_parameters_and_aggregate_reports(self):
        report = self.run_verification(require_ltspice=True, visual=True)
        self.assertEqual([item[0] for item in self.calls], [
            "backend", "frontend", "typescript-before-build", "build",
            "typescript-after-restore", "regression"])
        backend = self.calls[0][1]
        self.assertEqual(backend[1:5], ["-B", "-m", "unittest", "discover"])
        self.assertNotIn("verify_project.py", " ".join(backend))
        regression = self.calls[-1][1]
        self.assertEqual(regression, [sys.executable, "-B", str(self.root / "backend/tools/run_regression.py"),
                                      "--output", str(self.output / "regression"), "--samples", "2",
                                      "--require-ltspice", "--render", "--native"])
        self.assertTrue(all(call[3] == 41 for call in self.calls))
        self.assertEqual(report["overall"], "PASS")
        saved = json.loads((self.output / "verification_report.json").read_text())
        self.assertEqual(saved, report)
        markdown = (self.output / "verification_report.md").read_text()
        for label in verification.LABELS.values():
            self.assertIn(f"| {label} | PASS |", markdown)
        for command in report["commands"]:
            self.assertTrue((self.output / command["stdout_log"]).is_file())
            self.assertTrue((self.output / command["stderr_log"]).is_file())

    def test_optional_ltspice_and_visual_are_review_not_silent_pass(self):
        self.payload = regression_payload(ltspice="unavailable", visual="SKIP", overall="REVIEW")
        report = self.run_verification()
        self.assertEqual(report["overall"], "REVIEW")
        self.assertEqual(report["categories"]["ltspice"], "REVIEW")
        self.assertEqual(report["categories"]["visual"], "REVIEW")
        self.assertNotIn("--require-ltspice", self.calls[-1][1])
        self.assertNotIn("--render", self.calls[-1][1])
        self.assertNotIn("--native", self.calls[-1][1])

    def test_required_missing_ltspice_fails_even_when_runner_exits_zero(self):
        self.payload = regression_payload(ltspice="REVIEW", overall="REVIEW")
        report = self.run_verification(require_ltspice=True)
        self.assertEqual(report["categories"]["ltspice"], "FAIL")
        self.assertEqual(report["overall"], "FAIL")

    def test_failure_keeps_independent_gates_running_and_exit_code(self):
        self.failures = {"backend", "frontend", "typescript-before-build", "build", "regression"}
        report = self.run_verification()
        self.assertEqual(len(self.calls), 6)
        self.assertEqual(report["overall"], "FAIL")
        self.assertEqual(report["commands"][0]["returncode"], 7)
        self.assertEqual(report["categories"]["typescript"], "FAIL")

    def test_post_restore_typecheck_is_an_independent_failure(self):
        self.failures = {"typescript-after-restore"}
        report = self.run_verification()
        self.assertEqual(report["categories"]["build"], "PASS")
        self.assertEqual(report["categories"]["typescript"], "FAIL")
        self.assertEqual(report["overall"], "FAIL")

    def test_known_build_changes_restore_exact_preexisting_bytes(self):
        original_info = (self.frontend / "tsconfig.tsbuildinfo").read_bytes()

        def build():
            (self.frontend / "next-env.d.ts").write_bytes(BUILD_ENV)
            (self.frontend / "tsconfig.tsbuildinfo").write_bytes(BUILD_INFO)

        self.build_action = build
        report = self.run_verification()
        self.assertEqual(report["overall"], "PASS")
        self.assertEqual(report["build_conflicts"], [])
        self.assertEqual((self.frontend / "next-env.d.ts").read_bytes(), NEXT_ENV)
        self.assertEqual((self.frontend / "tsconfig.tsbuildinfo").read_bytes(), original_info)
        self.assertEqual(self.after_restore_bytes, NEXT_ENV)

    def test_failed_build_still_restores_and_runs_post_restore_check(self):
        self.failures = {"build"}
        self.build_action = lambda: (self.frontend / "next-env.d.ts").write_bytes(BUILD_ENV)
        report = self.run_verification()
        self.assertEqual((self.frontend / "next-env.d.ts").read_bytes(), NEXT_ENV)
        self.assertIn("typescript-after-restore", [call[0] for call in self.calls])
        self.assertEqual(report["overall"], "FAIL")

    def test_unexpected_build_change_is_not_overwritten(self):
        changed = BUILD_ENV + b"// someone else's edit\n"
        self.build_action = lambda: (self.frontend / "next-env.d.ts").write_bytes(changed)
        report = self.run_verification()
        self.assertEqual((self.frontend / "next-env.d.ts").read_bytes(), changed)
        self.assertEqual(report["categories"]["build"], "FAIL")
        self.assertIn("unexpected change", report["build_conflicts"][0])
        self.assertEqual(len(self.calls), 6)

    def test_generated_cache_with_unexpected_data_is_a_conflict(self):
        changed = b'{"fileNames": [], "fileInfos": [], "options": {}, "version": "5.7.3", "userNote": 1}'
        self.build_action = lambda: (self.frontend / "tsconfig.tsbuildinfo").write_bytes(changed)
        report = self.run_verification()
        self.assertEqual(report["categories"]["build"], "FAIL")
        self.assertEqual((self.frontend / "tsconfig.tsbuildinfo").read_bytes(), changed)

    def test_concurrent_edit_after_build_snapshot_is_not_overwritten(self):
        before = {name: verification.snapshot(self.frontend / name) for name in verification.GENERATED_FILES}
        (self.frontend / "next-env.d.ts").write_bytes(BUILD_ENV)
        after = {name: verification.snapshot(self.frontend / name) for name in verification.GENERATED_FILES}
        concurrent = BUILD_ENV + b"// concurrent edit\n"
        (self.frontend / "next-env.d.ts").write_bytes(concurrent)
        conflicts = verification.restore_generated(self.frontend, before, after)
        self.assertEqual(len(conflicts), 1)
        self.assertIn("concurrent change", conflicts[0])
        self.assertEqual((self.frontend / "next-env.d.ts").read_bytes(), concurrent)

    def test_new_known_generated_files_removed_if_absent_before_build(self):
        for name in verification.GENERATED_FILES:
            (self.frontend / name).unlink()
        before = {name: verification.snapshot(self.frontend / name) for name in verification.GENERATED_FILES}
        (self.frontend / "next-env.d.ts").write_bytes(BUILD_ENV)
        (self.frontend / "tsconfig.tsbuildinfo").write_bytes(BUILD_INFO)
        after = {name: verification.snapshot(self.frontend / name) for name in verification.GENERATED_FILES}
        self.assertEqual(verification.restore_generated(self.frontend, before, after), [])
        self.assertTrue(all(not (self.frontend / name).exists() for name in verification.GENERATED_FILES))

    def test_missing_regression_report_is_failure(self):
        self.payload = None
        report = self.run_verification()
        self.assertEqual(report["overall"], "FAIL")
        self.assertIn("cannot read regression evidence", report["regression"]["error"])

    def test_missing_categories_and_empty_circuits_never_pass(self):
        self.payload = {"overall": "PASS", "categories": {}, "circuits": []}
        report = self.run_verification()
        self.assertEqual(report["overall"], "REVIEW")
        self.assertEqual(report["categories"]["electrical"], "REVIEW")
        self.assertEqual(report["categories"]["visual"], "REVIEW")
        self.assertTrue(report["regression"]["notes"])

    def test_compiler_and_export_failures_affect_overall(self):
        self.payload["categories"]["export"] = {"status": "FAIL"}
        report = self.run_verification()
        self.assertEqual(report["overall"], "FAIL")
        self.assertTrue(all(value == "PASS" for value in report["categories"].values()))

    def test_named_category_list_is_accepted_without_inventing_passes(self):
        self.payload["categories"] = [{"name": name.upper(), "status": value}
                                      for name, value in self.payload["categories"].items()]
        report = self.run_verification()
        self.assertEqual(report["overall"], "PASS")

    def test_malformed_report_fails(self):
        path = self.output / "malformed.json"
        for malformed in ("not JSON", "[]", '{"categories":3}', '{"categories":{},"circuits":{}}'):
            with self.subTest(malformed=malformed):
                path.write_text(malformed, encoding="utf-8")
                result = verification.read_regression(path, False)
                self.assertEqual(result["overall"], "FAIL")
                self.assertTrue(result["error"])

    def test_refresh_reloads_visual_evidence_without_commands(self):
        self.payload = regression_payload(visual="REVIEW", overall="REVIEW")
        report = self.run_verification()
        self.assertEqual(report["overall"], "REVIEW")
        (self.output / "regression/regression_report.json").write_text(json.dumps(regression_payload()))
        with patch.object(verification, "run_command", side_effect=AssertionError("refresh ran commands")):
            refreshed = verification.refresh_report(self.output)
        self.assertEqual(refreshed["overall"], "PASS")
        self.assertEqual(refreshed["commands"], report["commands"])
        self.assertEqual(refreshed["categories"]["visual"], "PASS")

    def test_refresh_preserves_prior_command_failure(self):
        self.failures = {"typescript-after-restore"}
        self.run_verification()
        refreshed = verification.refresh_report(self.output)
        self.assertEqual(refreshed["overall"], "FAIL")
        self.assertEqual(refreshed["categories"]["typescript"], "FAIL")

    def test_backend_interpreter_windows_unix_and_fallback(self):
        self.assertEqual(verification.backend_python(self.root), sys.executable)
        unix = self.root / "backend/venv/bin/python"
        unix.parent.mkdir(parents=True)
        unix.touch()
        self.assertEqual(verification.backend_python(self.root), str(unix))
        windows = self.root / "backend/.venv/Scripts/python.exe"
        windows.parent.mkdir(parents=True)
        windows.touch()
        self.assertEqual(verification.backend_python(self.root), str(windows))

    def test_unsafe_nonempty_and_source_outputs_rejected_without_overwrite(self):
        victim = self.root / "existing/report.json"
        victim.parent.mkdir()
        victim.write_bytes(b"keep me")
        for candidate in (self.root, self.root.parent, victim.parent, victim,
                          self.root / "backend/tools/output", self.frontend / "generated",
                          self.root / ".git/report", self.root / "node_modules/output"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                verification.prepare_output(candidate, self.root)
        self.assertEqual(victim.read_bytes(), b"keep me")

    def test_fresh_safe_output_and_default_do_not_reuse_stale_artifacts(self):
        empty = self.root / "backend/tests/artifacts/empty"
        empty.mkdir(parents=True)
        self.assertEqual(verification.prepare_output(empty, self.root), empty.resolve())
        with self.assertRaises(ValueError):
            verification.prepare_output(empty, self.root)
        first = verification.prepare_output(None, self.root)
        second = verification.prepare_output(None, self.root)
        self.assertNotEqual(first, second)

    def test_output_symlink_rejected_without_privileged_filesystem_operations(self):
        link = self.root / "linked-output"
        link.mkdir()
        target = link / "new"
        with patch.object(Path, "is_symlink", autospec=True,
                          side_effect=lambda path: path == link), self.assertRaises(ValueError):
            verification.prepare_output(target, self.root)
        self.assertFalse(target.exists())

    def test_npm_entrypoint_avoids_windows_shell_for_paths_with_spaces(self):
        shim = self.root / "node installation/npm.cmd"
        cli = shim.parent / "node_modules/npm/bin/npm-cli.js"
        cli.parent.mkdir(parents=True)
        cli.touch()
        with patch.object(verification.shutil, "which",
                          side_effect=lambda name: str(shim) if name.startswith("npm") else "node.exe"):
            expected = ["node.exe", str(cli)] if os.name == "nt" else [str(shim)]
            self.assertEqual(verification.npm_command(), expected)

    def test_timeout_and_samples_reject_invalid_values_without_running_commands(self):
        for args in (["--timeout", "0"], ["--timeout", "-2"], ["--timeout", "nan"],
                     ["--timeout", "inf"], ["--timeout", "oops"], ["--samples", "0"],
                     ["--samples", "-1"], ["--samples", "1.5"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                verification.main(args)
            self.assertEqual(raised.exception.code, 2)

    def test_run_command_records_logs_returncode_and_preserves_argument_boundaries(self):
        process = Mock()
        process.wait.return_value = 7

        def start(command, **kwargs):
            self.assertEqual(command, ["fake program", "argument with spaces"])
            kwargs["stdout"].write(b"child stdout\n")
            kwargs["stderr"].write(b"child stderr\n")
            self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertNotIn("shell", kwargs)
            return process

        with patch.object(verification.subprocess, "Popen", side_effect=start):
            result = verification.run_command("example", ["fake program", "argument with spaces"],
                                              cwd=self.root, output=self.output, timeout=12)
        self.assertEqual(result["returncode"], 7)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual((self.output / result["stdout_log"]).read_bytes(), b"child stdout\n")
        self.assertEqual((self.output / result["stderr_log"]).read_bytes(), b"child stderr\n")
        process.wait.assert_called_once_with(timeout=12)

    def test_timeout_kills_tree_and_records_actual_termination_code(self):
        process = Mock()
        process.wait.side_effect = [subprocess.TimeoutExpired(["fake"], 0.1), -9]
        with patch.object(verification.subprocess, "Popen", return_value=process), \
             patch.object(verification, "_terminate_tree", return_value=None) as terminate:
            result = verification.run_command("timeout", ["fake"], cwd=self.root,
                                              output=self.output, timeout=0.1)
        terminate.assert_called_once_with(process)
        self.assertEqual(result["returncode"], -9)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("timed out", (self.output / result["stderr_log"]).read_text())

    def test_missing_command_is_explicit_failure_with_logs(self):
        with patch.object(verification.subprocess, "Popen", side_effect=FileNotFoundError("not installed")):
            result = verification.run_command("missing", ["missing"], cwd=self.root,
                                              output=self.output, timeout=1)
        self.assertIsNone(result["returncode"])
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("not installed", result["error"])
        self.assertTrue((self.output / result["stdout_log"]).is_file())

    def test_unreaped_children_block_regression_instead_of_overlapping_ltspice(self):
        def command(*args, **kwargs):
            result = self.fake_command(*args, **kwargs)
            if args[0] == "backend":
                result.update(status="FAIL", cleanup_error="could not kill process tree")
            return result

        with patch.object(verification, "run_command", side_effect=command):
            report = verification.verify(root=self.root, output=self.output, timeout=10, samples=1)
        self.assertNotIn("regression", [call[0] for call in self.calls])
        self.assertEqual(report["commands"][-1]["status"], "FAIL")
        self.assertIn("LTspice", report["commands"][-1]["error"])
        self.assertEqual(report["overall"], "FAIL")

    def test_main_exit_codes_and_backend_wrapper_never_reenter_verify(self):
        for overall, expected in (("PASS", 0), ("REVIEW", 0), ("FAIL", 1)):
            report = {"overall": overall, "categories": dict.fromkeys(verification.CATEGORY_ORDER, overall)}
            with self.subTest(overall=overall), patch.object(verification, "prepare_output", return_value=self.output), \
                 patch.object(verification, "verify", return_value=report), redirect_stdout(io.StringIO()):
                self.assertEqual(verification.main([]), expected)
        with patch.object(verification.subprocess, "run", return_value=Mock(returncode=0)) as launch:
            self.assertEqual(verification.main(["--backend-only"]), 0)
            self.assertIn("unittest", launch.call_args.args[0])
            self.assertNotIn("verify_project.py", " ".join(launch.call_args.args[0]))
        with patch.object(verification.subprocess, "run", side_effect=subprocess.TimeoutExpired("fake", 1)), \
             redirect_stderr(io.StringIO()):
            self.assertEqual(verification.main(["--backend-only", "--timeout", "1"]), 124)

    def test_root_scripts_are_explicit_and_export_uses_semantic_runner(self):
        scripts = json.loads((BACKEND.parent / "package.json").read_text())["scripts"]
        for name in ("test", "test:backend", "test:frontend", "test:regression", "test:export", "verify", "verify:full"):
            self.assertIn(name, scripts)
        self.assertIn("--export-only", scripts["test:export"])
        self.assertIn("--require-ltspice --visual", scripts["verify:full"])
        self.assertIn("--backend-only", scripts["test:backend"])


if __name__ == "__main__":
    unittest.main()
