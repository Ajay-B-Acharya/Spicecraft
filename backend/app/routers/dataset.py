"""
Dataset router — serves the ltspice manifest as a browsable, paginated API.

All entries point back to their upstream GitHub source URLs so users can
view or download the original .asc files directly from the repository.
No files are redistributed; only metadata and external links are returned.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).resolve().parents[3] / "dataset" / "ltspice" / "manifest.json"

router = APIRouter(prefix="/dataset", tags=["dataset"])


class DatasetCircuit(BaseModel):
    id: str
    filename: str
    original_relative_path: str
    source_repository: str
    source_repository_url: str
    source_url: str
    license_status: str
    download_status: str


class DatasetCircuitsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    circuits: list[DatasetCircuit]


@lru_cache(maxsize=1)
def _load_manifest() -> list[dict[str, Any]]:
    """Load and cache the manifest. Called once per process lifetime."""
    if not MANIFEST_PATH.exists():
        logger.warning("Manifest not found at %s", MANIFEST_PATH)
        return []
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        circuits = data.get("circuits", [])
        logger.info("Loaded %d circuits from manifest", len(circuits))
        return circuits
    except Exception as exc:
        logger.exception("Failed to load manifest: %s", exc)
        return []


def _to_model(entry: dict[str, Any]) -> DatasetCircuit:
    return DatasetCircuit(
        id=str(entry.get("id", "")),
        filename=str(entry.get("filename", "")),
        original_relative_path=str(entry.get("original_relative_path", "")),
        source_repository=str(entry.get("source_repository", "")),
        source_repository_url=str(entry.get("source_repository_url", "")),
        source_url=str(entry.get("source_url", "")),
        license_status=str(entry.get("license_status", "UNKNOWN")),
        download_status=str(entry.get("download_status", "UNKNOWN")),
    )


@router.get("/circuits", response_model=DatasetCircuitsResponse)
def list_dataset_circuits(
    page: int = Query(default=1, ge=1, description="1-based page number"),
    page_size: int = Query(default=50, ge=1, le=200, description="Items per page (max 200)"),
    search: str = Query(default="", description="Filter by filename substring (case-insensitive)"),
    repository: str = Query(default="", description="Filter by source repository slug"),
) -> DatasetCircuitsResponse:
    """
    Return a paginated list of LTspice .asc circuit entries from the dataset manifest.

    Each entry includes a `source_url` pointing to the original file on GitHub
    so users can view or download the .asc file directly. No files are served
    from this server — only metadata and external links.
    """
    all_circuits = _load_manifest()

    # Apply filters
    filtered = all_circuits
    if search:
        needle = search.lower()
        filtered = [c for c in filtered if needle in c.get("filename", "").lower()
                    or needle in c.get("original_relative_path", "").lower()]
    if repository:
        repo_needle = repository.lower()
        filtered = [c for c in filtered if repo_needle == c.get("source_repository", "").lower()]

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_entries = filtered[start:end]

    try:
        circuits = [_to_model(entry) for entry in page_entries]
    except Exception as exc:
        logger.exception("Failed to serialize manifest entries")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to read dataset manifest", "code": "MANIFEST_ERROR"},
        ) from exc

    return DatasetCircuitsResponse(
        total=total,
        page=page,
        page_size=page_size,
        circuits=circuits,
    )


@router.get("/circuits/{circuit_id}", response_model=DatasetCircuit)
def get_dataset_circuit(circuit_id: str) -> DatasetCircuit:
    """Return a single dataset circuit entry by its manifest ID."""
    all_circuits = _load_manifest()
    for entry in all_circuits:
        if str(entry.get("id", "")) == circuit_id:
            return _to_model(entry)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"message": f"Dataset circuit '{circuit_id}' not found", "code": "NOT_FOUND"},
    )


def _blob_url_to_raw_url(blob_url: str) -> str | None:
    """
    Convert a GitHub blob URL to a raw.githubusercontent.com URL.
    
    Example:
      https://github.com/owner/repo/blob/sha/path/file.asc
      → https://raw.githubusercontent.com/owner/repo/sha/path/file.asc
    """
    match = re.match(
        r"https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.*)",
        blob_url
    )
    if not match:
        return None
    owner, repo, ref, path = match.groups()
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"


@router.get("/circuits/{circuit_id}/content")
def get_dataset_circuit_content(circuit_id: str) -> Response:
    """
    Fetch the actual .asc file content from GitHub for a dataset circuit.
    
    Returns the raw .asc file as text/plain. The file is fetched on-demand
    from the upstream repository and not stored locally.
    """
    # Find the manifest entry
    all_circuits = _load_manifest()
    entry = next((c for c in all_circuits if str(c.get("id", "")) == circuit_id), None)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": f"Dataset circuit '{circuit_id}' not found", "code": "NOT_FOUND"},
        )
    
    blob_url = str(entry.get("source_url", ""))
    raw_url = _blob_url_to_raw_url(blob_url)
    if not raw_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Invalid source URL in manifest", "code": "INVALID_SOURCE_URL"},
        )
    
    # Fetch the .asc content from GitHub
    try:
        logger.info("Fetching .asc content from %s", raw_url)
        response = httpx.get(
            raw_url,
            headers={"User-Agent": "SpiceCraft-Dataset-Viewer/1.0"},
            timeout=30.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        
        # Validate that it looks like an .asc file
        content = response.content
        try:
            text = content.decode("utf-8-sig")
            if not text.strip():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"message": "Retrieved file is empty", "code": "EMPTY_FILE"},
                )
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"message": "Retrieved file is not valid UTF-8", "code": "INVALID_ENCODING"},
            )
        
        filename = entry.get("filename", "circuit.asc")
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "X-Source-URL": blob_url,
            }
        )
    
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "File not found in upstream repository", "code": "UPSTREAM_NOT_FOUND"},
            )
        logger.exception("HTTP error fetching .asc from GitHub: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": f"Failed to fetch file from GitHub (HTTP {exc.response.status_code})", "code": "UPSTREAM_ERROR"},
        )
    except httpx.RequestError as exc:
        logger.exception("Network error fetching .asc from GitHub: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": "Network error connecting to GitHub", "code": "NETWORK_ERROR"},
        )
    except Exception as exc:
        logger.exception("Unexpected error fetching .asc: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Unexpected error fetching circuit content", "code": "INTERNAL_ERROR"},
        )
