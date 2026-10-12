
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.application import Application
from Backend.app.models.application_status_history import ApplicationStatusHistory
from Backend.app.models.candidate import Candidate
from Backend.app.utils.auth import get_current_user


router = APIRouter(
    prefix="/application-history",
    tags=["Application History"]
)


@router.get("/{application_id}")
def get_application_history(
    application_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Find the application
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

    # HR can view any application's history.
    # Candidates can view only their own application's history.
    if current_user.role != "HR":
        if current_user.role != "CANDIDATE":
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to view application history"
            )

        candidate = (
            db.query(Candidate)
            .filter(Candidate.user_id == current_user.id)
            .first()
        )

        if candidate is None or application.candidate_id != candidate.id:
            raise HTTPException(
                status_code=403,
                detail="You can only view your own application history"
            )

    # Fetch timeline in chronological order
    history_records = (
        db.query(ApplicationStatusHistory)
        .filter(
            ApplicationStatusHistory.application_id == application_id
        )
        .order_by(ApplicationStatusHistory.changed_at.asc())
        .all()
    )

    return {
        "application_id": application_id,
        "current_status": (
            application.status.value
            if hasattr(application.status, "value")
            else application.status
        ),
        "total_history_records": len(history_records),
        "history": [
            {
                "id": record.id,
                "old_status": (
                    record.old_status.value
                    if hasattr(record.old_status, "value")
                    else record.old_status
                ),
                "new_status": (
                    record.new_status.value
                    if hasattr(record.new_status, "value")
                    else record.new_status
                ),
                "changed_by": record.changed_by,
                "remarks": record.remarks,
                "changed_at": (
                    record.changed_at.isoformat()
                    if record.changed_at
                    else None
                )
            }
            for record in history_records
        ]
    }