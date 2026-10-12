
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.user import User
from Backend.app.models.job import Job
from Backend.app.models.candidate import Candidate
from Backend.app.models.application import Application
from Backend.app.models.interview import Interview
from Backend.app.utils.auth import get_current_user, require_role


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)


# =====================================================
# HR DASHBOARD
# =====================================================

@router.get("/hr")
def get_hr_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR"))
):
    total_jobs = db.query(Job).count()

    active_jobs = db.query(Job).filter(
        Job.status == "ACTIVE"
    ).count()

    draft_jobs = db.query(Job).filter(
        Job.status == "DRAFT"
    ).count()

    closed_jobs = db.query(Job).filter(
        Job.status == "CLOSED"
    ).count()

    total_applications = db.query(Application).count()

    total_candidates = db.query(Candidate).count()

    total_interviews = db.query(Interview).count()

    applications_by_status = (
        db.query(
            Application.status,
            func.count(Application.id)
        )
        .group_by(Application.status)
        .all()
    )

    status_summary = {
        str(status.value if hasattr(status, "value") else status): count
        for status, count in applications_by_status
    }

    # Recent applications
    recent_records = (
        db.query(Application)
        .order_by(Application.applied_at.desc())
        .limit(5)
        .all()
    )

    recent_applications = []

    for application in recent_records:
        candidate = db.query(Candidate).filter(
            Candidate.id == application.candidate_id
        ).first()

        candidate_user = None

        if candidate:
            candidate_user = db.query(User).filter(
                User.id == candidate.user_id
            ).first()

        job = db.query(Job).filter(
            Job.id == application.job_id
        ).first()

        recent_applications.append({
            "application_id": application.id,
            "candidate_id": application.candidate_id,
            "candidate_name": (
                candidate_user.full_name
                if candidate_user else None
            ),
            "job_id": application.job_id,
            "job_title": job.title if job else None,
            "status": (
                application.status.value
                if hasattr(application.status, "value")
                else application.status
            ),
            "applied_at": application.applied_at
        })

    # Upcoming interviews
    upcoming_interviews = (
        db.query(Interview)
        .filter(
            Interview.interview_date >= date.today(),
            Interview.result.notin_(
                ["CANCELLED", "PASSED", "FAILED"]
            )
        )
        .order_by(
            Interview.interview_date.asc(),
            Interview.interview_time.asc()
        )
        .limit(10)
        .all()
    )

    return {
        "message": "HR dashboard loaded successfully",
        "summary": {
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "draft_jobs": draft_jobs,
            "closed_jobs": closed_jobs,
            "total_applications": total_applications,
            "total_candidates": total_candidates,
            "total_interviews": total_interviews,
            "applications_by_status": status_summary
        },
        "recent_applications": recent_applications,
        "upcoming_interviews": [
            {
                "interview_id": interview.id,
                "application_id": interview.application_id,
                "interview_date": interview.interview_date,
                "interview_time": interview.interview_time,
                "interview_type": interview.interview_type,
                "interviewer": interview.interviewer,
                "result": interview.result
            }
            for interview in upcoming_interviews
        ]
    }


# =====================================================
# CANDIDATE DASHBOARD
# =====================================================

@router.get("/candidate")
def get_candidate_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("CANDIDATE"))
):
    # Find the candidate profile belonging to the logged-in user
    candidate = db.query(Candidate).filter(
        Candidate.user_id == current_user.id
    ).first()

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found. Create your profile first."
        )

    # Get the candidate's user account to access full_name
    candidate_user = db.query(User).filter(
        User.id == candidate.user_id
    ).first()

    # Get this candidate's applications
    applications = db.query(Application).filter(
        Application.candidate_id == candidate.id
    ).order_by(
        Application.applied_at.desc()
    ).all()

    applications_by_status = {}

    for application in applications:
        status_name = (
            application.status.value
            if hasattr(application.status, "value")
            else application.status
        )

        applications_by_status[status_name] = (
            applications_by_status.get(status_name, 0) + 1
        )

    # Prepare application details
    application_details = []

    for application in applications:
        job = db.query(Job).filter(
            Job.id == application.job_id
        ).first()

        application_details.append({
            "application_id": application.id,
            "job_id": application.job_id,
            "job_title": job.title if job else None,
            "department": job.department if job else None,
            "location": job.location if job else None,
            "application_status": (
                application.status.value
                if hasattr(application.status, "value")
                else application.status
            ),
            "applied_at": application.applied_at
        })

    # Calculate profile completion
    completion = 0

    if candidate_user and candidate_user.full_name:
        completion += 10

    if candidate.phone:
        completion += 10

    if candidate.qualification:
        completion += 15

    if candidate.skills:
        completion += 20

    if candidate.experience_years is not None:
        completion += 10

    if candidate.resume_path:
        completion += 25

    if candidate.city or candidate.address:
        completion += 5

    if candidate.graduation_year:
        completion += 5

    completion = min(completion, 100)

    # Upcoming interviews belonging to this candidate
    candidate_application_ids = [
        application.id for application in applications
    ]

    upcoming_interviews = []

    if candidate_application_ids:
        upcoming_interviews = (
            db.query(Interview)
            .filter(
                Interview.application_id.in_(
                    candidate_application_ids
                ),
                Interview.interview_date >= date.today(),
                Interview.result.notin_(
                    ["CANCELLED", "PASSED", "FAILED"]
                )
            )
            .order_by(
                Interview.interview_date.asc(),
                Interview.interview_time.asc()
            )
            .all()
        )

    return {
        "message": "Candidate dashboard loaded successfully",
        "candidate": {
            "candidate_id": candidate.id,
            "user_id": candidate.user_id,
            "full_name": (
                candidate_user.full_name
                if candidate_user else None
            ),
            "email": (
                candidate_user.email
                if candidate_user else None
            )
        },
        "profile": {
            "completion_percentage": completion,
            "can_apply_for_jobs": (
                completion >= 80 and bool(candidate.resume_path)
            ),
            "has_resume": bool(candidate.resume_path)
        },
        "summary": {
            "total_applications": len(applications),
            "applications_by_status": applications_by_status
        },
        "applications": application_details,
        "upcoming_interviews": [
            {
                "interview_id": interview.id,
                "application_id": interview.application_id,
                "interview_date": interview.interview_date,
                "interview_time": interview.interview_time,
                "interview_type": interview.interview_type,
                "interviewer": interview.interviewer,
                "meeting_link": interview.meeting_link,
                "location": interview.location,
                "result": interview.result
            }
            for interview in upcoming_interviews
        ]
    }