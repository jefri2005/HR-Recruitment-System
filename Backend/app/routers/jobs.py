
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.user import User
from Backend.app.models.job import Job
from Backend.app.models.application import Application
from Backend.app.utils.auth import get_current_user, require_role


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


# =====================================================
# REQUEST SCHEMAS
# =====================================================

class JobCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    department: Optional[str] = Field(default=None, max_length=100)
    location: str = Field(..., min_length=2, max_length=200)

    employment_type: Literal[
        "FULL_TIME",
        "PART_TIME",
        "CONTRACT",
        "INTERNSHIP"
    ] = "FULL_TIME"

    experience_min: int = Field(default=0, ge=0, le=60)
    experience_max: Optional[int] = Field(default=None, ge=0, le=60)

    salary_min: Optional[float] = Field(default=None, ge=0)
    salary_max: Optional[float] = Field(default=None, ge=0)

    required_skills: Optional[str] = None
    description: str = Field(..., min_length=10)
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None

    vacancies: int = Field(default=1, ge=1, le=10000)
    application_deadline: Optional[date] = None

    status: Literal["DRAFT", "ACTIVE", "CLOSED"] = "DRAFT"

    @model_validator(mode="after")
    def validate_job(self):
        if (
            self.experience_max is not None
            and self.experience_max < self.experience_min
        ):
            raise ValueError(
                "Maximum experience cannot be less than minimum experience"
            )

        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError(
                "Maximum salary cannot be less than minimum salary"
            )

        if (
            self.status == "ACTIVE"
            and self.application_deadline is not None
            and self.application_deadline < date.today()
        ):
            raise ValueError(
                "An active job cannot have a past application deadline"
            )

        return self


class JobUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=200)
    department: Optional[str] = Field(default=None, max_length=100)
    location: Optional[str] = Field(default=None, min_length=2, max_length=200)

    employment_type: Optional[
        Literal["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP"]
    ] = None

    experience_min: Optional[int] = Field(default=None, ge=0, le=60)
    experience_max: Optional[int] = Field(default=None, ge=0, le=60)

    salary_min: Optional[float] = Field(default=None, ge=0)
    salary_max: Optional[float] = Field(default=None, ge=0)

    required_skills: Optional[str] = None
    description: Optional[str] = Field(default=None, min_length=10)
    responsibilities: Optional[str] = None
    qualifications: Optional[str] = None

    vacancies: Optional[int] = Field(default=None, ge=1, le=10000)
    application_deadline: Optional[date] = None

    status: Optional[Literal["DRAFT", "ACTIVE", "CLOSED"]] = None

    @model_validator(mode="after")
    def validate_supplied_values(self):
        if (
            self.experience_min is not None
            and self.experience_max is not None
            and self.experience_max < self.experience_min
        ):
            raise ValueError(
                "Maximum experience cannot be less than minimum experience"
            )

        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError(
                "Maximum salary cannot be less than minimum salary"
            )

        if (
            self.status == "ACTIVE"
            and self.application_deadline is not None
            and self.application_deadline < date.today()
        ):
            raise ValueError(
                "An active job cannot have a past application deadline"
            )

        return self


# =====================================================
# HELPER FUNCTIONS
# =====================================================

def get_job_or_404(db: Session, job_id: int):
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )

    return job


def job_to_dict(job: Job):
    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "location": job.location,
        "employment_type": job.employment_type,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "required_skills": job.required_skills,
        "description": job.description,
        "responsibilities": job.responsibilities,
        "qualifications": job.qualifications,
        "vacancies": job.vacancies,
        "application_deadline": job.application_deadline,
        "status": job.status,
        "created_by": job.created_by,
        "created_at": job.created_at,
        "updated_at": job.updated_at
    }


# =====================================================
# CREATE JOB - HR ONLY
# =====================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    data = job_data.model_dump()

    # The creator is always the authenticated HR user.
    data["created_by"] = current_user.id

    new_job = Job(**data)

    try:
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        return {
            "message": "Job created successfully",
            "job": job_to_dict(new_job)
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create job. Check the job model and database fields."
        )


# =====================================================
# LIST AND SEARCH JOBS
# =====================================================

@router.get("/")
def list_jobs(
    search: Optional[str] = Query(default=None, max_length=100),
    department: Optional[str] = None,
    location: Optional[str] = None,
    employment_type: Optional[
        Literal["FULL_TIME", "PART_TIME", "CONTRACT", "INTERNSHIP"]
    ] = None,
    min_experience: Optional[int] = Query(default=None, ge=0, le=60),
    max_experience: Optional[int] = Query(default=None, ge=0, le=60),
    job_status: Optional[
        Literal["DRAFT", "ACTIVE", "CLOSED"]
    ] = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    query = db.query(Job)

    # Non-HR users and unauthenticated visitors can see ACTIVE jobs only.
    is_hr = current_user is not None and current_user.role == "HR"

    if is_hr:
        if job_status is not None:
            query = query.filter(Job.status == job_status)
    else:
        query = query.filter(Job.status == "ACTIVE")

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            Job.title.ilike(term)
            | Job.description.ilike(term)
            | Job.required_skills.ilike(term)
        )

    if department:
        query = query.filter(
            Job.department.ilike(f"%{department.strip()}%")
        )

    if location:
        query = query.filter(
            Job.location.ilike(f"%{location.strip()}%")
        )

    if employment_type:
        query = query.filter(
            Job.employment_type == employment_type
        )

    if min_experience is not None:
        query = query.filter(
            Job.experience_max >= min_experience
        )

    if max_experience is not None:
        query = query.filter(
            Job.experience_min <= max_experience
        )

    total = query.count()

    jobs = (
        query.order_by(Job.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "jobs": [job_to_dict(job) for job in jobs]
    }


# =====================================================
# GET ONE JOB
# =====================================================

@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    job = get_job_or_404(db, job_id)

    is_hr = current_user is not None and current_user.role == "HR"

    job_status = (
        job.status.value
        if hasattr(job.status, "value")
        else job.status
    )

    if job_status != "ACTIVE" and not is_hr:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job_to_dict(job)


# =====================================================
# UPDATE JOB - HR ONLY
# =====================================================

@router.put("/{job_id}")
def update_job(
    job_id: int,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    job = get_job_or_404(db, job_id)

    updates = job_data.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update"
        )

    # Validate combined values against existing values.
    experience_min = updates.get(
        "experience_min", job.experience_min
    )
    experience_max = updates.get(
        "experience_max", job.experience_max
    )
    salary_min = updates.get("salary_min", job.salary_min)
    salary_max = updates.get("salary_max", job.salary_max)
    new_status = updates.get("status", job.status)
    deadline = updates.get(
        "application_deadline", job.application_deadline
    )

    if (
        experience_min is not None
        and experience_max is not None
        and experience_max < experience_min
    ):
        raise HTTPException(
            status_code=422,
            detail="Maximum experience cannot be less than minimum experience"
        )

    if (
        salary_min is not None
        and salary_max is not None
        and salary_max < salary_min
    ):
        raise HTTPException(
            status_code=422,
            detail="Maximum salary cannot be less than minimum salary"
        )

    status_value = (
        new_status.value
        if hasattr(new_status, "value")
        else new_status
    )

    if (
        status_value == "ACTIVE"
        and deadline is not None
        and deadline < date.today()
    ):
        raise HTTPException(
            status_code=422,
            detail="An active job cannot have a past application deadline"
        )

    for field, value in updates.items():
        setattr(job, field, value)

    try:
        db.commit()
        db.refresh(job)

        return {
            "message": "Job updated successfully",
            "job": job_to_dict(job)
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update job"
        )


# =====================================================
# DELETE JOB - HR ONLY
# =====================================================

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    job = get_job_or_404(db, job_id)

    existing_applications = db.query(Application).filter(
        Application.job_id == job_id
    ).count()

    if existing_applications > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "This job has applications and cannot be deleted. "
                "Change its status to CLOSED instead."
            )
        )

    try:
        db.delete(job)
        db.commit()

        return {
            "message": "Job deleted successfully",
            "job_id": job_id
        }
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not delete job"
        )