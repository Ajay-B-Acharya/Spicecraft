# LTspice Circuit Dataset

This directory contains traceable LTspice `.asc` files collected from approved public GitHub repositories.
Only repositories with a GitHub-identified SPDX license are copied. Files from repositories with unknown licensing remain in the manifest as source references and are not copied.

## Collection

Run from the project root:

```powershell
python -m backend.tools.collect_ltspice --resume
```

Options: `--dry-run`, `--source <repository>`, `--max-files <number>`, `--resume`, and `--refresh-manifest`.
The collector uses GitHub's recursive repository-tree endpoint, downloads only `.asc` files and applicable license notices, applies request timeouts and bounded retries, and does not execute downloaded content.

## Current results

- Repositories successfully accessed: 5
- Discovered `.asc` files: 2269
- Downloaded or reused files: 0
- Unique downloaded files: 0
- Byte-identical duplicate source files: 0
- Files with known licenses: 0
- Files with unknown licenses (not copied): 2269
- Total copied size: 0 bytes

See `manifest.json` for per-file hashes, preliminary inspection, source provenance, duplicate links, and license metadata. See `sources.json` for repository metadata and `collection_report.json` for aggregate counts.
