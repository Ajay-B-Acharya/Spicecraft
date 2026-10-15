import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import circuits, circuit_sources, dataset, projects, search
from app.request_limits import CircuitRequestLimits, circuit_http_error, circuit_validation_error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Build allowed origins from CORS_ORIGINS env var (comma-separated),
# then ensure localhost is always present for local development.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
for _origin in ["http://localhost:3000"]:
    if _origin not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(_origin)

app = FastAPI(
    title="SpiceCraft API",
    description="AI-Powered LTspice Circuit Generator Backend",
    version="1.0.0",
)

app.add_exception_handler(RequestValidationError, circuit_validation_error)
app.add_exception_handler(StarletteHTTPException, circuit_http_error)
app.add_middleware(CircuitRequestLimits)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(circuit_sources.router)
app.include_router(search.router)
app.include_router(circuits.router)
app.include_router(dataset.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SpiceCraft Backend Running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "SpiceCraft API"}
