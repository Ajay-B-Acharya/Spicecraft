# SpiceCraft Phase 3 Database Schema

## Overview

SpiceCraft V1 uses **PostgreSQL** with **SQLAlchemy ORM**.

- **Authentication:** Firebase Authentication
- **User identifier:** `firebase_uid`
- **No auth tables:** no users, roles, permissions, JWT, or password storage tables

---

## Tables

### `projects`

Stores user-created SpiceCraft projects.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `firebase_uid` | VARCHAR(128) | Not null, indexed |
| `name` | VARCHAR(255) | Not null |
| `description` | TEXT | Nullable |
| `created_at` | TIMESTAMPTZ | Not null |
| `updated_at` | TIMESTAMPTZ | Not null |

Indexes:
- `ix_projects_firebase_uid`
- `ix_projects_created_at`

### `circuit_sources`

Stores circuit references, articles, images, and resources linked to a project.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `project_id` | UUID | Not null, foreign key -> `projects.id`, indexed |
| `title` | VARCHAR(255) | Not null |
| `source_name` | VARCHAR(255) | Nullable |
| `source_url` | TEXT | Nullable |
| `image_url` | TEXT | Nullable |
| `created_at` | TIMESTAMPTZ | Not null |
| `updated_at` | TIMESTAMPTZ | Not null |

Indexes:
- `ix_circuit_sources_project_id`
- `ix_circuit_sources_created_at`

---

## Relationship

```text
projects (1) ----< (N) circuit_sources
```

- One project can have many circuit sources.
- Deleting a project cascades to its related `circuit_sources` rows.

---

## PostgreSQL Schema Preview

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    firebase_uid VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_projects_firebase_uid ON projects(firebase_uid);
CREATE INDEX ix_projects_created_at ON projects(created_at);

CREATE TABLE circuit_sources (
    id UUID PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    source_url TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX ix_circuit_sources_project_id ON circuit_sources(project_id);
CREATE INDEX ix_circuit_sources_created_at ON circuit_sources(created_at);
```

---

## Example CRUD

### Create a project

```python
project = Project(
    firebase_uid="firebase-user-123",
    name="FM Radio Circuit",
    description="Building a frequency modulation receiver"
)
db.add(project)
db.commit()
db.refresh(project)
```

### Get all projects for a Firebase user

```python
projects = (
    db.query(Project)
    .filter(Project.firebase_uid == firebase_uid)
    .order_by(Project.created_at.desc())
    .all()
)
```

### Add a circuit source

```python
source = CircuitSource(
    project_id=project.id,
    title="FM Receiver Diagram",
    source_name="Electronics Hub",
    source_url="https://example.com/circuit",
    image_url="https://example.com/diagram.png",
)
db.add(source)
db.commit()
db.refresh(source)
```

### Enforce ownership with Firebase UID

```python
project = (
    db.query(Project)
    .filter(Project.id == project_id, Project.firebase_uid == firebase_uid)
    .first()
)
```
