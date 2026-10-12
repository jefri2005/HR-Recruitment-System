
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.user import User
from Backend.app.models.candidate import Candidate
from Backend.app.models.application import Application
from Backend.app.models.job import Job
from Backend.app.utils.auth import require_role


router = APIRouter(
    prefix="/hr/candidates",
    tags=["HR Candidate Search"]
)


@router.get("/")
def search_candidates(
    skill: Optional[str] = Query(None, description="Search candidate skills"),
    qualification: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    min_experience: Optional[float] = Query(None, ge=0),
    max_experience: Optional[float] = Query(None, ge=0),
    job_id: Optional[int] = Query(None, gt=0),
    application_status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    query = (
        db.query(Candidate, User)
        .join(User, Candidate.user_id == User.id)
    )

    # Filter by skills
    if skill:
        query = query.filter(Candidate.skills.ilike(f"%{skill}%"))

    # Filter by qualification
    if qualification:
        query = query.filter(
            Candidate.qualification.ilike(f"%{qualification}%")
        )

    # Filter by city
    if city:
        query = query.filter(Candidate.city.ilike(f"%{city}%"))

    # Filter by experience range
    if min_experience is not None:
        query = query.filter(
            Candidate.experience_years >= min_experience
        )

    if max_experience is not None:
        query = query.filter(
            Candidate.experience_years <= max_experience
        )

    # Filter candidates who applied for a specific job
    if job_id is not None:
        query = query.join(
            Application,
            Application.candidate_id == Candidate.id
        ).filter(Application.job_id == job_id)

    # Filter by application status
    if application_status:
        if job_id is None:
            query = query.join(
                Application,
                Application.candidate_id == Candidate.id
            )

        query = query.filter(
            Application.status == application_status.upper()
        )

    results = query.order_by(Candidate.id.desc()).offset(skip).limit(limit).all()

    candidates = []

    for candidate, user in results:
        candidates.append({
            "candidate_id": candidate.id,
            "user_id": candidate.user_id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": candidate.phone,
            "city": candidate.city,
            "qualification": candidate.qualification,
            "graduation_year": candidate.graduation_year,
            "skills": candidate.skills,
            "experience_years": candidate.experience_years,
            "previous_company": candidate.previous_company,
            "previous_job_title": candidate.previous_job_title,
            "resume_uploaded": bool(candidate.resume_path)
        })

    return {
        "total_returned": len(candidates),
        "skip": skip,
        "limit": limit,
        "candidates": candidates
    }