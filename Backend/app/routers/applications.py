
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from Backend.app.database import SessionLocal
from Backend.app.models.application import Application
from Backend.app.models.candidate import Candidate
from Backend.app.models.job import Job
from Backend.app.models.user import User
from Backend.app.models.application_status_history import ApplicationStatusHistory
from Backend.app.models.notification import Notification
from Backend.app.utils.auth import get_current_user


router = APIRouter(
    prefix="/applications",
    tags=["Applications"]
)


# Database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Request body for applying
class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: str | None = None
    candidate_id: int | None = None


# Request body for HR status updates
class ApplicationStatusUpdate(BaseModel):
    new_status: str
    remarks: str | None = None


# Find the logged-in candidate's profile
def get_candidate_for_user(db: Session, user: User):
    if user.role != "CANDIDATE":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can perform this action"
        )

    candidate = db.query(Candidate).filter(
        Candidate.user_id == user.id
    ).first()

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found"
        )

    return candidate


# Find an application
def get_application_or_404(db: Session, application_id: int):
    application = db.query(Application).filter(
        Application.id == application_id
    ).first()

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    return application


# Verify application ownership
def check_application_access(
    application: Application,
    current_user: User,
    db: Session
):
    if current_user.role == "HR":
        return

    if current_user.role == "CANDIDATE":
        candidate = db.query(Candidate).filter(
            Candidate.user_id == current_user.id
        ).first()

        if candidate is None:
            raise HTTPException(
                status_code=404,
                detail="Candidate profile not found"
            )

        if application.candidate_id != candidate.id:
            raise HTTPException(
                status_code=403,
                detail="You cannot access another candidate's application"
            )

        return

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to access this application"
    )


# Calculate profile completion percentage
def calculate_profile_completion(candidate, user):
    score = 0

    if user and user.full_name and user.full_name.strip():
        score += 10

    if candidate.phone and candidate.phone.strip():
        score += 10

    if candidate.qualification and candidate.qualification.strip():
        score += 15

    if candidate.skills and candidate.skills.strip():
        score += 20

    if candidate.experience_years is not None:
        score += 10

    if candidate.resume_path and candidate.resume_path.strip():
        score += 25

    if (
        (candidate.city and candidate.city.strip())
        or (candidate.address and candidate.address.strip())
    ):
        score += 5

    if candidate.graduation_year is not None:
        score += 5

    return score


# Apply for a job
@router.post("/")
def apply_for_job(
    application_data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidate = get_candidate_for_user(db, current_user)

    # Prevent applying on behalf of another candidate
    if (
        application_data.candidate_id is not None
        and application_data.candidate_id != candidate.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You cannot apply on behalf of another candidate"
        )

    # Check profile completion
    completion = calculate_profile_completion(
        candidate,
        current_user
    )

    if completion < 80:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Complete your profile to at least 80% before applying."
                ),
                "profile_completion_percentage": completion,
                "minimum_required_percentage": 80,
                "missing_required_fields": (
                    ["resume"]
                    if not candidate.resume_path
                    else []
                )
            }
        )

    # Require a resume reference
    if not candidate.resume_path or not candidate.resume_path.strip():
        raise HTTPException(
            status_code=400,
            detail="Please provide your resume before applying."
        )

    # Check whether the job exists
    job = db.query(Job).filter(
        Job.id == application_data.job_id
    ).first()

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # Only active jobs accept applications
    if job.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="This job is not currently accepting applications."
        )

    # Check application deadline
    if (
        job.application_deadline is not None
        and job.application_deadline < date.today()
    ):
        raise HTTPException(
            status_code=400,
            detail="The application deadline has passed."
        )

    # Prevent duplicate applications
    existing_application = db.query(Application).filter(
        Application.candidate_id == candidate.id,
        Application.job_id == job.id
    ).first()

    if existing_application:
        raise HTTPException(
            status_code=409,
            detail="You have already applied for this job."
        )

    # Limit to 10 non-withdrawn applications in 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)

    recent_application_count = db.query(Application).filter(
        Application.candidate_id == candidate.id,
        Application.applied_at >= thirty_days_ago,
        Application.status != "WITHDRAWN"
    ).count()

    if recent_application_count >= 10:
        raise HTTPException(
            status_code=400,
            detail=(
                "You have reached the limit of 10 applications "
                "in the last 30 days."
            )
        )

    # Create the application
    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        cover_letter=application_data.cover_letter,
        status="APPLIED"
    )

    try:
        db.add(application)
        db.flush()

        # Record initial status in history
        history = ApplicationStatusHistory(
            application_id=application.id,
            old_status=None,
            new_status="APPLIED",
            changed_by=current_user.id,
            remarks="Application submitted by candidate"
        )

        db.add(history)
        db.commit()
        db.refresh(application)

        return {
            "message": "Application submitted successfully.",
            "application": application,
            "profile_completion_percentage": completion
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Application could not be created. "
                "You may have already applied for this job."
            )
        )


# Get applications: HR sees all; candidates see only their own
@router.get("/")
def get_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "HR":
        return db.query(Application).all()

    if current_user.role == "CANDIDATE":
        candidate = get_candidate_for_user(db, current_user)

        return db.query(Application).filter(
            Application.candidate_id == candidate.id
        ).all()

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to view applications"
    )


# Get one application
@router.get("/{application_id}")
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    application = get_application_or_404(db, application_id)
    check_application_access(application, current_user, db)
    return application


# Withdraw an application
@router.post("/{application_id}/withdraw")
def withdraw_application(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    candidate = get_candidate_for_user(db, current_user)
    application = get_application_or_404(db, application_id)

    if application.candidate_id != candidate.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot withdraw another candidate's application"
        )

    if application.status in ["WITHDRAWN", "REJECTED", "HIRED"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot withdraw an application with status {application.status}"
        )

    old_status = application.status

    try:
        application.status = "WITHDRAWN"

        history = ApplicationStatusHistory(
            application_id=application.id,
            old_status=old_status,
            new_status="WITHDRAWN",
            changed_by=current_user.id,
            remarks="Application withdrawn by candidate"
        )

        db.add(history)
        db.commit()
        db.refresh(application)

        return {
            "message": "Application withdrawn successfully",
            "application_id": application.id,
            "old_status": old_status,
            "new_status": application.status
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not withdraw application"
        )


# Update application status: HR only
@router.patch("/{application_id}/status")
def update_application_status(
    application_id: int,
    status_data: ApplicationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "HR":
        raise HTTPException(
            status_code=403,
            detail="Only HR can update application status"
        )

    application = get_application_or_404(db, application_id)

    allowed_transitions = {
        "APPLIED": ["UNDER_REVIEW", "WITHDRAWN"],
        "UNDER_REVIEW": ["SHORTLISTED", "REJECTED", "WITHDRAWN"],
        "SHORTLISTED": [
            "INTERVIEW_SCHEDULED",
            "REJECTED",
            "WITHDRAWN"
        ],
        "INTERVIEW_SCHEDULED": [
            "SELECTED",
            "REJECTED",
            "WITHDRAWN"
        ],
        "SELECTED": ["HIRED", "REJECTED"],
        "REJECTED": [],
        "HIRED": [],
        "WITHDRAWN": []
    }

    new_status = status_data.new_status.upper()
    old_status = application.status

    if new_status not in allowed_transitions:
        raise HTTPException(
            status_code=400,
            detail="Invalid application status"
        )

    if new_status not in allowed_transitions[old_status]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Transition from {old_status} to {new_status} "
                "is not allowed"
            )
        )

    try:
        # Update application status
        application.status = new_status

        # Record status change in history
        history = ApplicationStatusHistory(
            application_id=application.id,
            old_status=old_status,
            new_status=new_status,
            changed_by=current_user.id,
            remarks=status_data.remarks
        )
        db.add(history)

        # Find the candidate who owns this application
        candidate = db.query(Candidate).filter(
            Candidate.id == application.candidate_id
        ).first()

        # Create a notification for the candidate
        if candidate is not None:
            notification = Notification(
                user_id=candidate.user_id,
                title="Application Status Updated",
                message=(
                    f"Your application for job ID {application.job_id} "
                    f"has changed from {old_status} to {new_status}."
                ),
                type="APPLICATION_STATUS",
                is_read=False
            )
            db.add(notification)

        # Save status, history, and notification together
        db.commit()
        db.refresh(application)

        return {
            "message": "Application status updated successfully",
            "application_id": application.id,
            "old_status": old_status,
            "new_status": application.status,
            "notification_created": candidate is not None
        }

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update application status"
        )


# View application status history: HR or owning candidate only
@router.get("/{application_id}/history")
def get_application_history(
    application_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    get_application_or_404(db, application_id)
    application = get_application_or_404(db, application_id)
    check_application_access(application, current_user, db)
    return db.query(ApplicationStatusHistory).filter(
        ApplicationStatusHistory.application_id == application_id
    ).order_by(
        ApplicationStatusHistory.changed_at.asc()
    ).all()