# SpiceCraft Database Schema Documentation

## Overview

SpiceCraft V1 uses **PostgreSQL** with **SQLAlchemy ORM**.

**Authentication:** Firebase Authentication (no auth tables in database)
**User Identifier:** Firebase UID (string)

---

## Database Tables

### 1. `projects`

Stores user-created SpiceCraft projects.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() | Unique project identifier |
| `firebase_uid` | VARCHAR(128) | NOT NULL, INDEXED | Firebase Auth UID |
| `name` | VARCHAR(255) | NOT NULL | Project name |
| `description` | TEXT | NULLABLE | Project description |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp (UTC) |

**Indexes:**
- `ix_projects_firebase_uid` on `firebase_uid`
- `ix_projects_created_at` on `created_at`
- `ix_projects_id` on `id` (primary key index)

**Relationships:**
- One-to-Many: `projects` → `circuit_sources`

---

### 2. `circuit_sources`

Stores circuit references, articles, images, and resources linked to projects.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY, DEFAULT uuid_generate_v4() | Unique source identifier |
| `project_id` | UUID | NOT NULL, FOREIGN KEY → projects(id), ON DELETE CASCADE, INDEXED | Parent project reference |
| `title` | VARCHAR(500) | NOT NULL | Circuit source title |
| `source_name` | VARCHAR(255) | NULLABLE | Source name (e.g., "Electronics Hub") |
| `source_url` | TEXT | NULLABLE | URL to original source |
| `image_url` | TEXT | NULLABLE | URL to circuit diagram/image |
| `description` | TEXT | NULLABLE | Notes or description |
| `created_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Creation timestamp (UTC) |
| `updated_at` | TIMESTAMP | NOT NULL, DEFAULT NOW() | Last update timestamp (UTC) |

**Indexes:**
- `ix_circuit_sources_project_id` on `project_id`
- `ix_circuit_sources_created_at` on `created_at`
- `ix_circuit_sources_id` on `id` (primary key index)

**Relationships:**
- Many-to-One: `circuit_sources` → `projects`

**Cascade Delete:**
When a project is deleted, all associated circuit sources are automatically deleted.

---

## Relationships

```
┌──────────────────┐
│    projects      │
│ ────────────────│
│ id (PK)          │
│ firebase_uid     │◄──── Firebase Auth (external)
│ name             │
│ description      │
│ created_at       │
│ updated_at       │
└────────┬─────────┘
         │ 1
         │
         │ N
┌────────▼─────────┐
│ circuit_sources  │
│ ────────────────│
│ id (PK)          │
│ project_id (FK)  │
│ title            │
│ source_name      │
│ source_url       │
│ image_url        │
│ description      │
│ created_at       │
│ updated_at       │
└──────────────────┘
```

---

## PostgreSQL Schema (SQL)

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Projects table
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    firebase_uid VARCHAR(128) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_projects_firebase_uid ON projects(firebase_uid);
CREATE INDEX ix_projects_created_at ON projects(created_at);

COMMENT ON COLUMN projects.firebase_uid IS 'Firebase Authentication UID';
COMMENT ON COLUMN projects.name IS 'Project name';
COMMENT ON COLUMN projects.description IS 'Project description';
COMMENT ON COLUMN projects.created_at IS 'UTC timestamp of creation';
COMMENT ON COLUMN projects.updated_at IS 'UTC timestamp of last update';

-- Circuit Sources table
CREATE TABLE circuit_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    source_name VARCHAR(255),
    source_url TEXT,
    image_url TEXT,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_circuit_sources_project_id ON circuit_sources(project_id);
CREATE INDEX ix_circuit_sources_created_at ON circuit_sources(created_at);

COMMENT ON COLUMN circuit_sources.project_id IS 'Reference to parent project';
COMMENT ON COLUMN circuit_sources.title IS 'Title or name of the circuit source';
COMMENT ON COLUMN circuit_sources.source_name IS 'Name of the source (e.g., Electronics Hub)';
COMMENT ON COLUMN circuit_sources.source_url IS 'URL to the original source';
COMMENT ON COLUMN circuit_sources.image_url IS 'URL to circuit diagram or schematic image';
COMMENT ON COLUMN circuit_sources.description IS 'Description or notes about this circuit source';
COMMENT ON COLUMN circuit_sources.created_at IS 'UTC timestamp of creation';
COMMENT ON COLUMN circuit_sources.updated_at IS 'UTC timestamp of last update';
```

---

## Usage Examples

### Create a Project

```python
from app.models.project import Project

project = Project(
    firebase_uid="firebase-user-123",
    name="FM Radio Circuit",
    description="Building a frequency modulation receiver"
)
db.add(project)
db.commit()
```

### Get User's Projects

```python
projects = db.query(Project)\
    .filter(Project.firebase_uid == "firebase-user-123")\
    .order_by(Project.created_at.desc())\
    .all()
```

### Add Circuit Source

```python
from app.models.circuit_source import CircuitSource

source = CircuitSource(
    project_id=project.id,
    title="FM Receiver Diagram",
    source_name="Electronics Hub",
    source_url="https://example.com/circuit",
    image_url="https://example.com/diagram.png"
)
db.add(source)
db.commit()
```

### Get Project with Sources

```python
project = db.query(Project)\
    .filter(Project.id == project_id)\
    .first()

sources = project.circuit_sources.all()  # Via relationship
```

---

## Data Validation

All requests/responses use Pydantic schemas:

- `ProjectCreate` - Creating new projects
- `ProjectUpdate` - Updating projects
- `ProjectResponse` - API responses
- `CircuitSourceCreate` - Creating circuit sources
- `CircuitSourceUpdate` - Updating sources
- `CircuitSourceResponse` - API responses

---

## Security Considerations

1. **Firebase UID Verification**: Always verify the Firebase UID from the authenticated token matches the project owner before allowing operations.

2. **Ownership Checks**: 
   ```python
   project = db.query(Project)\
       .filter(
           Project.id == project_id,
           Project.firebase_uid == current_user_firebase_uid
       )\
       .first()
   ```

3. **Cascade Deletes**: Deleting a project automatically deletes all associated circuit sources.

4. **Input Validation**: All inputs are validated through Pydantic schemas before database operations.

---

## Migration Commands

### Create Tables

```bash
cd backend
python create_db.py
```

### Run Example CRUD

```bash
cd backend
python example_crud.py
```

### Using Alembic (Future)

```bash
# Install alembic
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial schema"

# Apply migration
alembic upgrade head
```

---

## Performance Considerations

1. **Indexes**: All foreign keys and commonly queried columns are indexed
2. **Pagination**: Use `offset()` and `limit()` for large result sets
3. **Lazy Loading**: Circuit sources use dynamic loading to avoid N+1 queries
4. **Connection Pooling**: Configured with `pool_size=5` and `max_overflow=10`

---

## Future Extensions (Not in V1)

These tables are NOT included in V1 MVP:

- ❌ `users` table (Firebase handles this)
- ❌ `ai_generations` table
- ❌ `ltspice_exports` table
- ❌ `component_library` table
- ❌ `teams` / `organizations`
- ❌ `api_keys`

Keep the schema minimal and production-ready for MVP.
