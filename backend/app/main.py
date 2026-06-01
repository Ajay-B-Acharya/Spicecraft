import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import projects

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="SpiceCraft API",
    description="AI-Powered LTspice Circuit Generator Backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "SpiceCraft Backend Running"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "SpiceCraft API"}
