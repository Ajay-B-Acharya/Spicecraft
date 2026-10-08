# SpiceCraft

SpiceCraft is an AI-assisted electronic circuit discovery and design platform.

## Vision

Instead of drawing circuits from scratch, users can:

* Search for existing electronic circuits
* Browse and edit circuit designs
* Modify component values visually
* Export circuits to LTspice (`.asc`) format
* Use AI assistance to improve and customize circuits

## Current Features

* FastAPI backend
* Next.js frontend
* Circuit search interface
* Responsive dashboard layout
* Swagger API documentation

## Planned Features

### Circuit Library

* Search electronic circuits
* Categorized circuit database
* Circuit metadata and tags

### Circuit Editor

* View circuit components
* Edit component values
* Save modified circuits

### LTspice Export

* Generate `.asc` files
* Download compatible LTspice schematics

### AI Assistant

* Modify circuits using natural language
* Recommend component values
* Generate circuits from user requirements

## Circuit pipeline and production hardening

The current schematic pipeline includes canonical components and pins, electrical net validation, deterministic layout, bounded Manhattan routing, geometry optimization, transactional LTspice export, and post-serialization checks. Unsupported or invalid circuits fail with diagnostics rather than substituted components or partial exports.

- [Architecture, support boundaries, resource limits, errors, and deployment guide](docs/PRODUCTION.md)
- [How to add and verify a component](docs/ADDING_COMPONENTS.md)
- [Regression, corpus, scalability, and browser testing](TESTING.md)
- [Phase 10 audit, measured results, and remaining acceptance limitations](PHASE_10_PRODUCTION_REPORT.md)

Circuit size is classified as small (1–20), medium (21–100), large (101–500), or extreme (501+). These categories are not scalability guarantees; consult the measured report. No live AI-provider integration or simulation is required by this phase.

## Tech Stack

Frontend:

* Next.js
* React
* Tailwind CSS

Backend:

* FastAPI
* Python

Persistence:

* Circuit definitions currently use repository JSON files with atomic updates.
* PostgreSQL remains a planned database integration.

## Project Structure

```text
frontend/
backend/
docs/
```

## Roadmap

Phase 1

* Circuit database
* Search system
* Circuit details page

Phase 2

* Circuit editor
* ASC export

Phase 3

* AI-assisted editing

Phase 4

* Community circuit library
* AI circuit generation

## License

This project is licensed under the Apache License 2.0.

See the LICENSE file for details.

Copyright © 2026 Ajay Acharya.
