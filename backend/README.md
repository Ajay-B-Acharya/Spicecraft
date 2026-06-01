# SpiceCraft Backend

AI-Powered LTspice Circuit Generator - FastAPI Backend

## Setup

### 1. Create Virtual Environment

```bash
cd "Spice Craft/backend"
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your database credentials and API keys.

### 5. Run the Server

```bash
uvicorn app.main:app --reload
```

The API will be available at: `http://localhost:8000`

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application entry point
│   ├── database.py       # Database configuration
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── routers/          # API route handlers
│   └── services/         # Business logic
├── .env                  # Environment variables (not in git)
├── .env.example          # Example environment file
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Database Setup

### Create Database Tables

```bash
python create_db.py
```

### Run Example CRUD Operations

```bash
python example_crud.py
```

### View Schema Documentation

See [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md) for complete schema details.

## Development

### Add New Routes

1. Create router in `app/routers/`
2. Import and include in `app/main.py`

### Add Database Models

1. Create model in `app/models/`
2. Add to `app/models/__init__.py`
3. Create corresponding Pydantic schema in `app/schemas/`
4. Run `python create_db.py` to create tables

## Testing

```bash
pytest
```

## Database Models

### Current Models

- **Project** - User projects with Firebase UID
- **CircuitSource** - Circuit references and resources

### Relationships

- One Project → Many Circuit Sources (CASCADE delete)

## Next Steps

- [ ] Add database migrations with Alembic
- [ ] Implement API routers for projects and circuit sources
- [ ] Add Firebase token verification middleware
- [ ] Add circuit generation services
- [ ] Integrate OpenAI API
- [ ] Add comprehensive tests
