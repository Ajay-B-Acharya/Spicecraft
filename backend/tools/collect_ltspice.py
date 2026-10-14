"""Collect traceable LTspice .asc files from the approved public repositories.

The collector uses GitHub's repository tree API rather than code search, downloads
only schematic files and license notices, and never executes downloaded content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = PROJECT_ROOT / "dataset" / "ltspice"
API_ROOT = "https://api.github.com"
USER_AGENT = "SpiceCraft-LTspice-Collector/1.0"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3


@dataclass(frozen=True)
class Source:
    slug: str
    owner: str
    repository: str

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repository}"


SOURCES = (
    Source("analogdevices-ltspice-reference", "analogdevicesinc", "ltspice-reference"),
    Source("alok-ltspice-circuit-design", "Alok018", "LTSpice_Circuit_Design"),
    Source("mr-jaymac-ltspice-circuits", "Mr-Jaymac", "LTSpice-Circuits"),
    Source("bert-ltspice-examples", "bert", "LTSpice-examples"),
    Source("ribster-ltspice", "Ribster", "LTSpice"),
)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return default


def request(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    """Request a URL with bounded retries, honoring GitHub rate-limit resets."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            headers = {"Accept": accept, "User-Agent": USER_AGENT}
            with urlopen(Request(url, headers=headers), timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read()
        except HTTPError as error:
            last_error = error
            retry_after = error.headers.get("Retry-After")
            remaining = error.headers.get("X-RateLimit-Remaining")
            reset = error.headers.get("X-RateLimit-Reset")
            if error.code not in (403, 429, 500, 502, 503, 504):
                raise
            if retry_after and retry_after.isdigit():
                delay = min(int(retry_after), 60)
            elif remaining == "0" and reset and reset.isdigit():
                delay = min(max(1, int(reset) - int(time.time()) + 1), 60)
            else:
                delay = 2**attempt
            if attempt + 1 < MAX_RETRIES:
                time.sleep(delay)
        except (URLError, TimeoutError) as error:
            last_error = error
            if attempt + 1 < MAX_RETRIES:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def api_json(path: str) -> dict[str, Any] | list[Any]:
    return json.loads(request(f"{API_ROOT}{path}").decode("utf-8"))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"Unsafe repository path: {value!r}")
    return path


def looks_like_schematic(data: bytes) -> tuple[str, list[str]]:
    if not data:
        return "INVALID_FILE", []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "NEEDS_REVIEW", []
    records = [line.rstrip("\r") for line in text.splitlines()[:8]]
    first = next((line.strip() for line in records if line.strip()), "")
    if first.startswith("Version ") or any(line.startswith(("SHEET ", "SYMBOL ", "WIRE ", "TEXT ")) for line in records):
        return "PARSE_CANDIDATE", records
    return "NEEDS_REVIEW", records


def source_filter(value: str) -> Source:
    normalized = value.lower().strip()
    for source in SOURCES:
        if normalized in (source.slug, source.repository.lower(), f"{source.owner}/{source.repository}".lower()):
            return source
    raise argparse.ArgumentTypeError(f"Unknown approved source: {value}")


def _git_metadata(source: Source) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Use a blob-filtered shallow clone if GitHub's REST API is rate-limited."""
    with tempfile.TemporaryDirectory(prefix="spicecraft-ltspice-") as temporary:
        checkout = Path(temporary) / "repository"
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--no-checkout", source.url, str(checkout)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        revision = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], check=True,
                                  capture_output=True, text=True, timeout=30).stdout.strip()
        branch_ref = subprocess.run(["git", "-C", str(checkout), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                                    check=True, capture_output=True, text=True, timeout=30).stdout.strip()
        branch = branch_ref.rsplit("/", 1)[-1]
        listing = subprocess.run(["git", "-C", str(checkout), "ls-tree", "-r", "HEAD"], check=True,
                                 capture_output=True, text=True, timeout=30).stdout.splitlines()
        entries = []
        license_files: dict[str, bytes] = {}
        for line in listing:
            metadata, path = line.split("\t", 1)
            mode, kind, object_id = metadata.split()
            if kind != "blob":
                continue
            entries.append({"path": path, "type": "blob", "sha": object_id})
            if PurePosixPath(path).name.lower().startswith(("license", "copying")):
                license_files[path] = subprocess.run(
                    ["git", "-C", str(checkout), "show", f"HEAD:{path}"], check=True,
                    capture_output=True, timeout=30,
                ).stdout
    license_data = next(iter(license_files.values()), b"")
    if b"Apache License" in license_data and b"Version 2.0" in license_data:
        license_info: dict[str, Any] | None = {"name": "Apache License 2.0", "spdx_id": "Apache-2.0"}
    else:
        license_info = None
    return {"default_branch": branch, "license": license_info, "_revision": revision,
            "_license_files": license_files}, entries


def repository_metadata(source: Source) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        repo = api_json(f"/repos/{source.owner}/{source.repository}")
        if not isinstance(repo, dict):
            raise ValueError("Repository endpoint did not return an object")
        tree = api_json(f"/repos/{source.owner}/{source.repository}/git/trees/{repo['default_branch']}?recursive=1")
        if not isinstance(tree, dict) or tree.get("truncated"):
            raise ValueError("Repository tree is unavailable or truncated")
        return repo, [entry for entry in tree.get("tree", []) if isinstance(entry, dict)]
    except HTTPError as error:
        if error.code != 403:
            raise
        return _git_metadata(source)


def license_metadata(source: Source, repo: dict[str, Any], entries: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    info = repo.get("license") if isinstance(repo.get("license"), dict) else {}
    license_path = next((str(entry["path"]) for entry in entries if
                         PurePosixPath(str(entry.get("path", ""))).name.lower().startswith(("license", "copying"))), None)
    spdx_id = str(info.get("spdx_id") or "UNKNOWN")
    name = str(info.get("name") or "UNKNOWN")
    status = "KNOWN" if spdx_id not in ("UNKNOWN", "NOASSERTION", "NONE") else "UNKNOWN"
    # GitHub identifies standard SPDX licenses. Those licenses permit copying
    # subject to their terms; unknown or custom terms are retained as references only.
    redistributable = status == "KNOWN"
    result = {
        "name": name if status == "KNOWN" else "UNKNOWN",
        "spdx_id": spdx_id if status == "KNOWN" else "UNKNOWN",
        "status": status,
        "redistribution_status": "PERMITTED_SUBJECT_TO_LICENSE" if redistributable else "UNCERTAIN_NOT_COPIED",
        "file_path": license_path,
        "source_url": f"{source.url}/blob/{repo['default_branch']}/{license_path}" if license_path else None,
        "local_path": None,
    }
    if license_path and redistributable and not dry_run:
        destination = DATASET_ROOT / "raw" / source.slug / safe_relative_path(license_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        cached_license = repo.get("_license_files", {}).get(license_path)
        if cached_license is not None:
            data = cached_license
        else:
            raw_url = f"https://raw.githubusercontent.com/{source.owner}/{source.repository}/{repo['default_branch']}/{license_path}"
            data = request(raw_url, accept="application/octet-stream")
        destination.write_bytes(data)
        result["local_path"] = destination.relative_to(PROJECT_ROOT).as_posix()
    return result


def collect_source(source: Source, args: argparse.Namespace, sequence: int) -> tuple[list[dict[str, Any]], dict[str, Any], int]:
    repo, tree = repository_metadata(source)
    revision = str(repo.get("_revision") or repo.get("pushed_at") or "")
    if not revision:
        commit = api_json(f"/repos/{source.owner}/{source.repository}/commits/{repo['default_branch']}")
        if isinstance(commit, dict):
            revision = str(commit.get("sha") or "")
    license_info = license_metadata(source, repo, tree, args.dry_run)
    schematic_entries = sorted(
        (entry for entry in tree if entry.get("type") == "blob" and str(entry.get("path", "")).lower().endswith(".asc")),
        key=lambda entry: str(entry["path"]).lower(),
    )
    discovered_count = len(schematic_entries)
    if args.max_files is not None:
        schematic_entries = schematic_entries[:args.max_files]

    records: list[dict[str, Any]] = []
    raw_root = DATASET_ROOT / "raw" / source.slug
    if not args.dry_run:
        raw_root.mkdir(parents=True, exist_ok=True)
    for index, entry in enumerate(schematic_entries, start=1):
        repository_path = str(entry["path"])
        safe_path = safe_relative_path(repository_path)
        relative_path = (Path("raw") / source.slug / Path(*safe_path.parts)).as_posix()
        source_url = f"{source.url}/blob/{revision}/{repository_path}"
        record: dict[str, Any] = {
            "id": f"circuit-{sequence + index:04d}",
            "filename": safe_path.name,
            "relative_path": relative_path,
            "original_relative_path": repository_path,
            "source_repository": source.slug,
            "source_repository_url": source.url,
            "source_url": source_url,
            "repository_revision": revision,
            "license": license_info["name"],
            "license_spdx_id": license_info["spdx_id"],
            "license_status": license_info["status"],
            "license_file_path": license_info["file_path"],
            "license_redistribution_status": license_info["redistribution_status"],
            "sha256": None,
            "file_size_bytes": None,
            "duplicate_of": None,
            "duplicate_source_locations": [],
            "inspection_status": "NOT_INSPECTED",
            "diagnostic_records": [],
            "download_status": "NOT_DOWNLOADED_LICENSE_UNKNOWN" if license_info["status"] == "UNKNOWN" else "PENDING",
        }
        destination = raw_root / Path(*safe_path.parts)
        if args.dry_run or license_info["status"] == "UNKNOWN":
            records.append(record)
            continue
        try:
            data: bytes
            if destination.exists() and destination.is_file() and destination.stat().st_size > 0:
                data = destination.read_bytes()
                record["download_status"] = "REUSED"
            else:
                raw_url = f"https://raw.githubusercontent.com/{source.owner}/{source.repository}/{revision}/{repository_path}"
                data = request(raw_url, accept="application/octet-stream")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                record["download_status"] = "DOWNLOADED"
            record["sha256"] = sha256(data)
            record["file_size_bytes"] = len(data)
            record["inspection_status"], record["diagnostic_records"] = looks_like_schematic(data)
            if not data:
                record["download_status"] = "INVALID_FILE"
        except (HTTPError, URLError, OSError, TimeoutError, ValueError) as error:
            record["download_status"] = "DOWNLOAD_FAILED"
            record["error"] = str(error)
        records.append(record)
    source_summary = {
        "slug": source.slug,
        "repository": f"{source.owner}/{source.repository}",
        "repository_url": source.url,
        "repository_revision": revision,
        "default_branch": repo.get("default_branch"),
        "license": license_info,
        "discovered_asc_files": discovered_count,
        "selected_asc_files": len(schematic_entries),
        "collection_date": utc_now(),
        "status": "SUCCESS",
    }
    return records, source_summary, sequence + len(schematic_entries)


def apply_duplicates(records: list[dict[str, Any]]) -> None:
    canonical_by_hash: dict[str, dict[str, Any]] = {}
    for record in records:
        digest = record.get("sha256")
        if not digest:
            continue
        canonical = canonical_by_hash.get(digest)
        if canonical is None:
            canonical_by_hash[digest] = record
            continue
        record["duplicate_of"] = canonical["id"]
        record["inspection_status"] = "DUPLICATE"
        canonical["duplicate_source_locations"].append({
            "id": record["id"], "source_repository": record["source_repository"],
            "original_relative_path": record["original_relative_path"], "source_url": record["source_url"],
        })


def write_outputs(records: list[dict[str, Any]], sources: list[dict[str, Any]], failures: list[dict[str, str]]) -> None:
    records.sort(key=lambda item: (item["source_repository"], item["original_relative_path"].lower()))
    downloaded = [item for item in records if item["download_status"] in ("DOWNLOADED", "REUSED")]
    duplicates = [item for item in records if item.get("duplicate_of")]
    invalid = [item for item in records if item["inspection_status"] == "INVALID_FILE"]
    known = [item for item in records if item["license_status"] == "KNOWN"]
    total_size = sum(item["file_size_bytes"] or 0 for item in downloaded)
    per_repository = {source["slug"]: {
        "discovered": source["discovered_asc_files"], "selected": source["selected_asc_files"],
        "downloaded_or_reused": sum(1 for item in downloaded if item["source_repository"] == source["slug"]),
    } for source in sources}
    warnings = list(failures)
    warnings.extend({
        "repository": source["slug"],
        "warning": "License is unknown; schematics were recorded as references and were not copied.",
    } for source in sources if source["license"]["status"] == "UNKNOWN")
    manifest = {"schema_version": 1, "generated_at": utc_now(), "circuits": records}
    sources_file = {"schema_version": 1, "generated_at": utc_now(), "sources": sources, "failures": failures}
    report = {
        "schema_version": 1, "generated_at": utc_now(), "repositories_examined": len(sources) + len(failures),
        "repositories_successfully_accessed": len(sources), "repositories_failed": len(failures),
        "files_discovered": sum(source["discovered_asc_files"] for source in sources),
        "files_selected_for_manifest": len(records), "files_downloaded_or_reused": len(downloaded),
        "unique_downloaded_files": len(downloaded) - len(duplicates), "duplicate_files": len(duplicates),
        "invalid_or_empty_files": len(invalid), "files_with_known_licenses": len(known),
        "files_with_unknown_licenses": len(records) - len(known), "total_dataset_size_bytes": total_size,
        "per_repository": per_repository, "errors_and_warnings": warnings,
    }
    json_dump(DATASET_ROOT / "manifest.json", manifest)
    json_dump(DATASET_ROOT / "sources.json", sources_file)
    json_dump(DATASET_ROOT / "collection_report.json", report)
    lines = [
        "# LTspice Circuit Dataset", "", "This directory contains traceable LTspice `.asc` files collected from approved public GitHub repositories.",
        "Only repositories with a GitHub-identified SPDX license are copied. Files from repositories with unknown licensing remain in the manifest as source references and are not copied.", "",
        "## Collection", "", "Run from the project root:", "", "```powershell", "python -m backend.tools.collect_ltspice --resume", "```", "",
        "Options: `--dry-run`, `--source <repository>`, `--max-files <number>`, `--resume`, and `--refresh-manifest`.",
        "The collector uses GitHub's recursive repository-tree endpoint, downloads only `.asc` files and applicable license notices, applies request timeouts and bounded retries, and does not execute downloaded content.", "",
        "## Current results", "", f"- Repositories successfully accessed: {report['repositories_successfully_accessed']}",
        f"- Discovered `.asc` files: {report['files_discovered']}", f"- Downloaded or reused files: {report['files_downloaded_or_reused']}",
        f"- Unique downloaded files: {report['unique_downloaded_files']}", f"- Byte-identical duplicate source files: {report['duplicate_files']}",
        f"- Files with known licenses: {report['files_with_known_licenses']}",
        f"- Files with unknown licenses (not copied): {report['files_with_unknown_licenses']}",
        f"- Total copied size: {report['total_dataset_size_bytes']} bytes", "",
        "See `manifest.json` for per-file hashes, preliminary inspection, source provenance, duplicate links, and license metadata. See `sources.json` for repository metadata and `collection_report.json` for aggregate counts.",
    ]
    (DATASET_ROOT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Discover metadata without copying schematics.")
    parser.add_argument("--source", action="append", type=source_filter, help="Collect only one approved source; may be repeated.")
    parser.add_argument("--max-files", type=int, default=None, help="Limit files selected per requested source.")
    parser.add_argument("--resume", action="store_true", help="Reuse existing non-empty files instead of downloading them again.")
    parser.add_argument("--refresh-manifest", action="store_true", help="Rebuild metadata and reports from the current source revisions.")
    args = parser.parse_args()
    if args.max_files is not None and args.max_files < 1:
        parser.error("--max-files must be at least 1")
    selected = args.source or list(SOURCES)
    if not args.resume and not args.refresh_manifest and not args.dry_run:
        args.resume = True  # Safe default: collection is always resumable and avoids unnecessary downloads.
    if args.refresh_manifest and DATASET_ROOT.exists() and not args.dry_run:
        # Keep raw data and licenses; only generated metadata is replaced below.
        pass
    records: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    sequence = 0
    for source in selected:
        try:
            source_records, summary, sequence = collect_source(source, args, sequence)
            records.extend(source_records)
            summaries.append(summary)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError, KeyError) as error:
            failures.append({"repository": source.slug, "repository_url": source.url, "error": str(error)})
    apply_duplicates(records)
    if not args.dry_run:
        write_outputs(records, summaries, failures)
    print(json.dumps({"sources_accessed": len(summaries), "sources_failed": len(failures), "files_discovered": len(records), "dataset": str(DATASET_ROOT)}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
