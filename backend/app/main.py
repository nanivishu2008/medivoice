from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .seed_data import seed_database
from .routers import doctors, slots, bookings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context: initialize database schema and demonstration data."""
    Base.metadata.create_all(bind=engine)
    seed_database()
    yield


app = FastAPI(
    title="MediVoice AI - Healthcare Appointment Booking System",
    description="FastAPI backend providing real-time doctor availability, dynamic appointment scheduling, and atomic booking transactions.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for local frontend development and production hosting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register feature routers
app.include_router(doctors.router)
app.include_router(slots.router)
app.include_router(bookings.router)


@app.get("/", tags=["Health"])
def health_check():
    """Service health and identification check."""
    return {
        "status": "healthy",
        "service": "MediVoice AI Backend",
        "docs_url": "/docs"
    }
