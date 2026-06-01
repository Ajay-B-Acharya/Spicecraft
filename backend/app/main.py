from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="SpiceCraft API",
    description="AI-Powered LTspice Circuit Generator Backend",
    version="1.0.0"
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "SpiceCraft Backend Running"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "SpiceCraft API"}
