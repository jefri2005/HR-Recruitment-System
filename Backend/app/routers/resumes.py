
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from Backend.app.database import get_db
from Backend.app.models.candidate import Candidate
from Backend.app.models.user import User
from Backend.app.utils.auth import get_current_user, require_role


router = APIRouter(prefix="/resumes", tags=["Resumes"])

# Project root: HR-Recruitment-System/
PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Private resume storage directory
RESUME_DIR = PROJECT_ROOT / "uploads" / "resumes"
RESUME_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
CHUNK_SIZE = 64 * 1024


def get_candidate_by_user_id(
    db: Session,
    user_id: int,
) -> Candidate:
    candidate = (
        db.query(Candidate)
        .filter(Candidate.user_id == user_id)
        .first()
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found. Create your profile first.",
        )

    return candidate


def get_candidate_by_id(
    db: Session,
    candidate_id: int,
) -> Candidate:
    candidate = (
        db.query(Candidate)
        .filter(Candidate.id == candidate_id)
        .first()
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    return candidate


def get_stored_resume_path(resume_path: str) -> Path:
    """Resolve a stored relative path and prevent path traversal."""
    try:
        path = (PROJECT_ROOT / resume_path).resolve()
        path.relative_to(RESUME_DIR.resolve())
    except (ValueError, OSError):
        raise HTTPException(
            status_code=404,
            detail="Resume file not found",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Resume file not found",
        )

    return path


def save_resume_path(
    db: Session,
    candidate: Candidate,
    relative_path: str,
):
    old_resume_path = candidate.resume_path

    candidate.resume_path = relative_path

    try:
        db.commit()
        db.refresh(candidate)
    except Exception:
        db.rollback()
        raise

    # Remove the old file only after the database update succeeds.
    # Never delete a file outside the resume storage directory.
    if old_resume_path:
        try:
            old_path = get_stored_resume_path(old_resume_path)
            if old_path != get_stored_resume_path(relative_path):
                old_path.unlink(missing_ok=True)
        except HTTPException:
            pass

    return candidate


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("CANDIDATE")),
):
    candidate = get_candidate_by_user_id(db, current_user.id)

    original_name = Path(file.filename or "").name

    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF resume files are allowed",
        )

    if file.content_type not in (
        "application/pdf",
        "application/octet-stream",
    ):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file must be a PDF",
        )

    file_bytes = bytearray()

    try:
        while True:
            chunk = await file.read(CHUNK_SIZE)

            if not chunk:
                break

            file_bytes.extend(chunk)

            if len(file_bytes) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Resume file must not exceed 5 MB",
                )

        # Check the PDF signature, not just the filename.
        if not file_bytes.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid PDF",
            )

        stored_filename = f"{uuid4().hex}.pdf"
        destination = RESUME_DIR / stored_filename

        # Store a relative path in MySQL, not the user's original filename.
        relative_path = (
            Path("uploads") / "resumes" / stored_filename
        ).as_posix()

        with destination.open("wb") as resume_file:
            resume_file.write(file_bytes)

        try:
            save_resume_path(db, candidate, relative_path)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return {
            "message": "Resume uploaded successfully",
            "candidate_id": candidate.id,
            "filename": stored_filename,
            "size_bytes": len(file_bytes),
        }

    finally:
        await file.close()


@router.get("/me")
def download_my_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("CANDIDATE")),
):
    candidate = get_candidate_by_user_id(db, current_user.id)

    if not candidate.resume_path:
        raise HTTPException(
            status_code=404,
            detail="You have not uploaded a resume yet",
        )

    path = get_stored_resume_path(candidate.resume_path)

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename="resume.pdf",
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/candidate/{candidate_id}")
def download_candidate_resume(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("HR")),
):
    candidate = get_candidate_by_id(db, candidate_id)

    if not candidate.resume_path:
        raise HTTPException(
            status_code=404,
            detail="This candidate has not uploaded a resume",
        )

    path = get_stored_resume_path(candidate.resume_path)

    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=f"candidate_{candidate.id}_resume.pdf",
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )