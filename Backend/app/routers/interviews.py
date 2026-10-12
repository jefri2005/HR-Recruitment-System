
from datetime import date, datetime, time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.interview import Interview
from Backend.app.models.application import Application
from Backend.app.models.candidate import Candidate
from Backend.app.models.notification import Notification
from Backend.app.models.application_status_history import (
    ApplicationStatusHistory,
)
from Backend.app.models.user import User
from Backend.app.utils.auth import get_current_user, require_role


router = APIRouter(prefix="/interviews", tags=["Interviews"])


# -------------------- REQUEST SCHEMAS --------------------

class InterviewCreate(BaseModel):
    application_id: int
    interview_date: date
    interview_time: time
    interview_type: Literal["ONLINE", "PHONE", "IN_PERSON"]
    interviewer: Optional[str] = Field(default=None, max_length=150)
    meeting_link: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = None


class InterviewReschedule(BaseModel):
    interview_date: Optional[date] = None
    interview_time: Optional[time] = None
    interviewer: Optional[str] = Field(default=None, max_length=150)
    meeting_link: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = None


class InterviewFeedback(BaseModel):
    feedback: Optional[str] = None
    result: Literal[
        "PENDING",
        "PASSED",
        "FAILED",
        "RESCHEDULED",
        "CANCELLED",
    ]


# -------------------- HELPER FUNCTIONS --------------------

def get_interview_or_404(
    interview_id: int,
    db: Session,
) -> Interview:
    interview = (
        db.query(Interview)
        .filter(Interview.id == interview_id)
        .first()
    )

    if interview is None:
        raise HTTPException(
            status_code=404,
            detail="Interview not found",
        )

    return interview


def check_interview_access(
    interview: Interview,
    current_user: User,
    db: Session,
):
    # HR can access all interviews.
    if current_user.role == "HR":
        return

    # Only the candidate who owns the application can access it.
    if current_user.role != "CANDIDATE":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this interview",
        )

    application = (
        db.query(Application)
        .filter(Application.id == interview.application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == application.candidate_id)
        .first()
    )

    if candidate is None or candidate.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own interviews",
        )


def notify_candidate(
    db: Session,
    candidate_user_id: int,
    title: str,
    message: str,
):
    notification = Notification(
        user_id=candidate_user_id,
        title=title,
        message=message,
        type="INTERVIEW",
        is_read=False,
    )
    db.add(notification)


def validate_interview_datetime(
    interview_date: date,
    interview_time: time,
):
    scheduled_datetime = datetime.combine(
        interview_date,
        interview_time,
    )

    if scheduled_datetime <= datetime.now():
        raise HTTPException(
            status_code=400,
            detail="Interview date and time must be in the future",
        )


# -------------------- SCHEDULE INTERVIEW --------------------

@router.post("/", status_code=status.HTTP_201_CREATED)
def schedule_interview(
    interview_data: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR")),
):
    validate_interview_datetime(
        interview_data.interview_date,
        interview_data.interview_time,
    )

    application = (
        db.query(Application)
        .filter(Application.id == interview_data.application_id)
        .first()
    )

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    if application.status != "SHORTLISTED":
        raise HTTPException(
            status_code=400,
            detail="Only shortlisted applications can be scheduled for an interview",
        )

    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == application.candidate_id)
        .first()
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found",
        )

    interview = Interview(
        application_id=application.id,
        interview_date=interview_data.interview_date,
        interview_time=interview_data.interview_time,
        interview_type=interview_data.interview_type,
        interviewer=interview_data.interviewer,
        meeting_link=interview_data.meeting_link,
        location=interview_data.location,
        notes=interview_data.notes,
        result="PENDING",
    )

    db.add(interview)

    old_status = application.status
    application.status = "INTERVIEW_SCHEDULED"

    history = ApplicationStatusHistory(
        application_id=application.id,
        old_status=old_status,
        new_status="INTERVIEW_SCHEDULED",
        changed_by=current_user.id,
        remarks="Interview scheduled",
    )
    db.add(history)

    notify_candidate(
        db,
        candidate.user_id,
        "Interview Scheduled",
        (
            f"Your interview is scheduled for "
            f"{interview_data.interview_date} at "
            f"{interview_data.interview_time}."
        ),
    )

    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview scheduled successfully",
        "interview": interview,
    }


# -------------------- LIST INTERVIEWS --------------------

@router.get("/")
def list_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Interview)

    if current_user.role == "CANDIDATE":
        candidate = (
            db.query(Candidate)
            .filter(Candidate.user_id == current_user.id)
            .first()
        )

        if candidate is None:
            return []

        candidate_applications = (
            db.query(Application.id)
            .filter(Application.candidate_id == candidate.id)
            .subquery()
        )

        query = query.filter(
            Interview.application_id.in_(candidate_applications)
        )

    elif current_user.role != "HR":
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to view interviews",
        )

    return query.order_by(
        Interview.interview_date.asc(),
        Interview.interview_time.asc(),
    ).all()


# -------------------- GET ONE INTERVIEW --------------------

@router.get("/{interview_id}")
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interview = get_interview_or_404(interview_id, db)

    check_interview_access(interview, current_user, db)

    return interview


# -------------------- RESCHEDULE INTERVIEW --------------------

@router.patch("/{interview_id}/reschedule")
def reschedule_interview(
    interview_id: int,
    update_data: InterviewReschedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR")),
):
    interview = get_interview_or_404(interview_id, db)

    if interview.result in ("CANCELLED", "PASSED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail="This interview cannot be rescheduled",
        )

    updates = update_data.model_dump(exclude_unset=True)

    new_date = updates.get(
        "interview_date",
        interview.interview_date,
    )
    new_time = updates.get(
        "interview_time",
        interview.interview_time,
    )

    validate_interview_datetime(new_date, new_time)

    for field, value in updates.items():
        setattr(interview, field, value)

    interview.result = "RESCHEDULED"

    application = (
        db.query(Application)
        .filter(Application.id == interview.application_id)
        .first()
    )

    if application:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.id == application.candidate_id)
            .first()
        )

        if candidate:
            notify_candidate(
                db,
                candidate.user_id,
                "Interview Rescheduled",
                (
                    f"Your interview has been rescheduled to "
                    f"{new_date} at {new_time}."
                ),
            )

    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview rescheduled successfully",
        "interview": interview,
    }


# -------------------- UPDATE FEEDBACK / RESULT --------------------

@router.patch("/{interview_id}/feedback")
def update_interview_feedback(
    interview_id: int,
    feedback_data: InterviewFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR")),
):
    interview = get_interview_or_404(interview_id, db)

    if interview.result == "CANCELLED":
        raise HTTPException(
            status_code=400,
            detail="A cancelled interview cannot receive feedback",
        )

    interview.feedback = feedback_data.feedback
    interview.result = feedback_data.result

    application = (
        db.query(Application)
        .filter(Application.id == interview.application_id)
        .first()
    )

    if application:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.id == application.candidate_id)
            .first()
        )

        if candidate:
            notify_candidate(
                db,
                candidate.user_id,
                "Interview Feedback Updated",
                (
                    f"Your interview result is "
                    f"{feedback_data.result}. "
                    f"{feedback_data.feedback or ''}"
                ),
            )

    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview feedback updated successfully",
        "interview": interview,
    }


# -------------------- CANCEL INTERVIEW --------------------

@router.patch("/{interview_id}/cancel")
def cancel_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR")),
):
    interview = get_interview_or_404(interview_id, db)

    if interview.result in ("CANCELLED", "PASSED", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail="This interview cannot be cancelled",
        )

    interview.result = "CANCELLED"

    application = (
        db.query(Application)
        .filter(Application.id == interview.application_id)
        .first()
    )

    if application:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.id == application.candidate_id)
            .first()
        )

        if candidate:
            notify_candidate(
                db,
                candidate.user_id,
                "Interview Cancelled",
                (
                    f"Your interview scheduled for "
                    f"{interview.interview_date} has been cancelled."
                ),
            )

    db.commit()
    db.refresh(interview)

    return {
        "message": "Interview cancelled successfully",
        "interview": interview,
    }