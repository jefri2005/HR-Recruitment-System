
from fastapi import FastAPI
from sqlalchemy import text

from Backend.app.database import engine, Base
from Backend.app.models import (
    User,
    Candidate,
    Job,
    Application,
    Interview,
    ApplicationStatusHistory,
    Notification,
)

from Backend.app.routers.auth import router as auth_router
from Backend.app.routers.jobs import router as jobs_router
from Backend.app.routers.applications import router as applications_router
from Backend.app.routers.candidates import router as candidates_router
from Backend.app.routers import notifications
from Backend.app.routers.interviews import router as interviews_router
from Backend.app.routers.resumes import router as resumes_router
from Backend.app.routers.dashboard import router as dashboard_router
from Backend.app.routers import application_history
from Backend.app.routers import hr_candidates
from Backend.app.routers import hr_applications
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="HR Recruitment Management System",
    description="HR and Candidate Recruitment Management API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(applications_router)
app.include_router(candidates_router)
app.include_router(notifications.router)
app.include_router(interviews_router)
app.include_router(resumes_router)
app.include_router(dashboard_router)
app.include_router(application_history.router)
app.include_router(hr_candidates.router)
app.include_router(hr_applications.router)

# Create tables for imported models
Base.metadata.create_all(bind=engine)


@app.get("/")
def home():
    return {
        "message": "HR Recruitment Management System is running!"
    }


@app.get("/test-db")
def test_database():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "result": result.scalar(),
        }