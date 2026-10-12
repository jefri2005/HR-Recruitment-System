
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.user import User
from Backend.app.models.candidate import Candidate
from Backend.app.models.job import Job
from Backend.app.models.application import Application
from Backend.app.utils.auth import require_role


router = APIRouter(
    prefix="/hr/applications",
    tags=["HR Application Management"]
)


@router.get("/")
def list_applications(
    job_id: Optional[int] = Query(None, gt=0),
    application_status: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    query = db.query(Application)

    if job_id is not None:
        query = query.filter(Application.job_id == job_id)

    if application_status:
        query = query.filter(
            Application.status == application_status.upper()
        )

    applications = (
        query.order_by(Application.applied_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []

    for application in applications:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.id == application.candidate_id)
            .first()
        )

        job = (
            db.query(Job)
            .filter(Job.id == application.job_id)
            .first()
        )

        user = None
        if candidate:
            user = (
                db.query(User)
                .filter(User.id == candidate.user_id)
                .first()
            )

        results.append({
            "application_id": application.id,
            "candidate_id": application.candidate_id,
            "candidate_name": user.full_name if user else None,
            "candidate_email": user.email if user else None,
            "candidate_phone": candidate.phone if candidate else None,
            "candidate_skills": candidate.skills if candidate else None,
            "candidate_experience_years": (
                candidate.experience_years if candidate else None
            ),
            "job_id": application.job_id,
            "job_title": job.title if job else None,
            "status": (
                application.status.value
                if hasattr(application.status, "value")
                else application.status
            ),
            "cover_letter": application.cover_letter,
            "applied_at": (
                application.applied_at.isoformat()
                if application.applied_at else None
            )
        })

    return {
        "total_returned": len(results),
        "skip": skip,
        "limit": limit,
        "applications": results
    }


@router.get("/{application_id}")
def get_application_details(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    application = (
        db.query(Application)
        .filter(Application.id == application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == application.candidate_id)
        .first()
    )

    job = (
        db.query(Job)
        .filter(Job.id == application.job_id)
        .first()
    )

    user = None
    if candidate:
        user = (
            db.query(User)
            .filter(User.id == candidate.user_id)
            .first()
        )

    return {
        "application_id": application.id,
        "status": (
            application.status.value
            if hasattr(application.status, "value")
            else application.status
        ),
        "cover_letter": application.cover_letter,
        "applied_at": (
            application.applied_at.isoformat()
            if application.applied_at else None
        ),
        "candidate": {
            "id": candidate.id if candidate else None,
            "name": user.full_name if user else None,
            "email": user.email if user else None,
            "phone": candidate.phone if candidate else None,
            "city": candidate.city if candidate else None,
            "qualification": candidate.qualification if candidate else None,
            "skills": candidate.skills if candidate else None,
            "experience_years": (
                candidate.experience_years if candidate else None
            ),
            "resume_uploaded": bool(candidate.resume_path) if candidate else False
        },
        "job": {
            "id": job.id if job else None,
            "title": job.title if job else None,
            "department": job.department if job else None,
            "location": job.location if job else None
        }
    }