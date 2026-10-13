
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from Backend.app.database import SessionLocal
from Backend.app.models.candidate import Candidate
from Backend.app.models.user import User
from Backend.app.models.application import Application
from Backend.app.models.job import Job
from Backend.app.utils.auth import get_current_user, require_role


router = APIRouter(
    prefix="/candidates",
    tags=["Candidates"]
)


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------
# AUTHORIZATION HELPER
# --------------------------------------------------

def get_candidate_for_user(
    candidate_id: int,
    current_user: User,
    db: Session
):
    """
    HR can access any candidate profile.
    Candidates can access only their own profile.
    """

    candidate = db.query(Candidate).filter(
        Candidate.id == candidate_id
    ).first()

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found"
        )

    if current_user.role == "HR":
        return candidate

    if (
        current_user.role == "CANDIDATE"
        and candidate.user_id == current_user.id
    ):
        return candidate

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to access this candidate profile"
    )


# --------------------------------------------------
# REQUEST SCHEMAS
# --------------------------------------------------

class CandidateCreate(BaseModel):
    # Must match the authenticated candidate's user ID.
    user_id: int

    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    qualification: str | None = None
    college: str | None = None
    graduation_year: int | None = Field(
        default=None,
        ge=1950,
        le=2100
    )
    skills: str | None = None
    experience_years: Decimal = Field(
        default=Decimal("0"),
        ge=0
    )
    previous_company: str | None = None
    previous_job_title: str | None = None
    resume_path: str | None = None
    profile_image: str | None = None


class CandidateUpdate(BaseModel):
    date_of_birth: date | None = None
    gender: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    qualification: str | None = None
    college: str | None = None
    graduation_year: int | None = Field(
        default=None,
        ge=1950,
        le=2100
    )
    skills: str | None = None
    experience_years: Decimal | None = Field(
        default=None,
        ge=0
    )
    previous_company: str | None = None
    previous_job_title: str | None = None
    resume_path: str | None = None
    profile_image: str | None = None


# --------------------------------------------------
# PROFILE COMPLETION BUSINESS LOGIC
# --------------------------------------------------

def calculate_profile_completion(candidate, user):
    """
    Total profile completion score: 100%.

    Name: 10
    Phone: 10
    Qualification: 15
    Skills: 20
    Experience: 10
    Resume: 25
    Location: 5
    Graduation year: 5
    """

    score = 0

    if user.full_name and user.full_name.strip():
        score += 10

    if candidate.phone and candidate.phone.strip():
        score += 10

    if candidate.qualification and candidate.qualification.strip():
        score += 15

    if candidate.skills and candidate.skills.strip():
        score += 20

    if (
        candidate.experience_years is not None
        and candidate.experience_years >= 0
    ):
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


def get_profile_completion_details(candidate, user):
    percentage = calculate_profile_completion(candidate, user)

    missing_fields = []

    if not user.full_name or not user.full_name.strip():
        missing_fields.append("full_name")

    if not user.email or not user.email.strip():
        missing_fields.append("email")

    if not candidate.phone or not candidate.phone.strip():
        missing_fields.append("phone")

    if not candidate.qualification or not candidate.qualification.strip():
        missing_fields.append("qualification")

    if not candidate.skills or not candidate.skills.strip():
        missing_fields.append("skills")

    if candidate.experience_years is None:
        missing_fields.append("experience_years")

    if not candidate.resume_path or not candidate.resume_path.strip():
        missing_fields.append("resume")

    can_apply = percentage >= 80 and len(missing_fields) == 0

    return {
        "candidate_id": candidate.id,
        "profile_completion_percentage": percentage,
        "minimum_required_percentage": 80,
        "missing_required_fields": missing_fields,
        "can_apply_for_jobs": can_apply
    }


# --------------------------------------------------
# CREATE CANDIDATE PROFILE
# POST /candidates/
# Only authenticated candidates can create their profile.
# --------------------------------------------------

@router.post("/")
def create_candidate(
    candidate_data: CandidateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CANDIDATE":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can create candidate profiles"
        )

    # Prevent creating a profile for another user.
    if candidate_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can create a profile only for your own account"
        )

    existing = db.query(Candidate).filter(
        Candidate.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This user already has a candidate profile"
        )

    candidate_values = candidate_data.model_dump()
    candidate_values["user_id"] = current_user.id

    candidate = Candidate(**candidate_values)

    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        return {
            "message": "Candidate profile created successfully",
            "candidate": candidate,
            "profile_completion": get_profile_completion_details(
                candidate,
                current_user
            )
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create candidate profile. Check the submitted information."
        )


# --------------------------------------------------
# GET ALL CANDIDATES
# GET /candidates/
# HR only.
# --------------------------------------------------

@router.get("/", dependencies=[Depends(require_role("HR"))])
def get_candidates(
    db: Session = Depends(get_db)
):
    return db.query(Candidate).all()


# --------------------------------------------------
# GET THE LOGGED-IN CANDIDATE'S OWN PROFILE
# GET /candidates/me
# --------------------------------------------------

@router.get("/me")
def get_my_candidate_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "CANDIDATE":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can access this endpoint"
        )

    candidate = db.query(Candidate).filter(
        Candidate.user_id == current_user.id
    ).first()

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found. Create your profile first."
        )

    return candidate


# --------------------------------------------------
# GET PROFILE COMPLETION
# GET /candidates/{candidate_id}/completion
# HR or the profile owner.
# --------------------------------------------------

@router.get("/{candidate_id}/completion")
def get_candidate_completion(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    candidate = get_candidate_for_user(
        candidate_id,
        current_user,
        db
    )

    user = db.query(User).filter(
        User.id == candidate.user_id
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate user account not found"
        )

    return get_profile_completion_details(candidate, user)


# --------------------------------------------------
# UPDATE CANDIDATE PROFILE
# PUT /candidates/{candidate_id}
# HR or the profile owner.
# --------------------------------------------------

@router.put("/{candidate_id}")
def update_candidate(
    candidate_id: int,
    candidate_data: CandidateUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    candidate = get_candidate_for_user(
        candidate_id,
        current_user,
        db
    )

    update_data = candidate_data.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update"
        )

    for field, value in update_data.items():
        setattr(candidate, field, value)

    try:
        db.commit()
        db.refresh(candidate)

        user = db.query(User).filter(
            User.id == candidate.user_id
        ).first()

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="Candidate user account not found"
            )

        return {
            "message": "Candidate profile updated successfully",
            "candidate": candidate,
            "profile_completion": get_profile_completion_details(
                candidate,
                user
            )
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Invalid profile information"
        )

    
@router.get("/me")
def get_my_candidate(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Only candidates can access this endpoint
    if current_user.role.upper() != "CANDIDATE":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can access their own profile"
        )

    candidate = (
        db.query(Candidate)
        .filter(Candidate.user_id == current_user.id)
        .first()
    )

    if not candidate:
        raise HTTPException(
            status_code=404,
            detail="Candidate profile not found. Create your profile first."
        )

    return candidate


# --------------------------------------------------
# GET ONE CANDIDATE
# GET /candidates/{candidate_id}
# HR or the profile owner.
# --------------------------------------------------

@router.get("/{candidate_id}")
def get_candidate(
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    candidate = get_candidate_for_user(
        candidate_id,
        current_user,
        db
    )

    return candidate


# --------------------------------------------------
# HR PROFILE COMPLETION HELPER
# --------------------------------------------------

def _hr_profile_completion(candidate, user):
    return calculate_profile_completion(candidate, user)


# --------------------------------------------------
# HR SEARCH AND FILTER CANDIDATES
# GET /candidates/hr/search
# HR only.
# --------------------------------------------------

@router.get(
    "/hr/search",
    dependencies=[Depends(require_role("HR"))]
)
def search_candidates_for_hr(
    skills: str | None = None,
    qualification: str | None = None,
    location: str | None = None,
    min_experience: float | None = Query(
        default=None,
        ge=0
    ),
    max_experience: float | None = Query(
        default=None,
        ge=0
    ),
    application_status: str | None = None,
    job_role: str | None = None,
    min_completion: int = Query(
        default=0,
        ge=0,
        le=100
    ),
    page: int = Query(
        default=1,
        ge=1
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100
    ),
    db: Session = Depends(get_db)
):
    if (
        min_experience is not None
        and max_experience is not None
        and min_experience > max_experience
    ):
        raise HTTPException(
            status_code=400,
            detail="min_experience cannot exceed max_experience"
        )

    query = db.query(Candidate, User).join(
        User,
        Candidate.user_id == User.id
    )

    # Join applications and jobs only when these filters are used.
    if application_status or job_role:
        query = query.join(
            Application,
            Application.candidate_id == Candidate.id
        ).join(
            Job,
            Job.id == Application.job_id
        )

    if skills:
        query = query.filter(
            Candidate.skills.ilike(f"%{skills.strip()}%")
        )

    if qualification:
        query = query.filter(
            Candidate.qualification.ilike(
                f"%{qualification.strip()}%"
            )
        )

    if location:
        location_filter = f"%{location.strip()}%"

        query = query.filter(
            Candidate.city.ilike(location_filter)
            | Candidate.address.ilike(location_filter)
        )

    if min_experience is not None:
        query = query.filter(
            Candidate.experience_years >= min_experience
        )

    if max_experience is not None:
        query = query.filter(
            Candidate.experience_years <= max_experience
        )

    if application_status:
        valid_statuses = {
            "APPLIED",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "REJECTED",
            "INTERVIEW_SCHEDULED",
            "SELECTED",
            "HIRED",
            "WITHDRAWN"
        }

        status_value = application_status.upper()

        if status_value not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail="Invalid application status"
            )

        query = query.filter(
            Application.status == status_value
        )

    if job_role:
        query = query.filter(
            Job.title.ilike(f"%{job_role.strip()}%")
        )

    # Prevent duplicate candidate results.
    rows = query.distinct().all()

    results = []

    for candidate, user in rows:
        completion = _hr_profile_completion(candidate, user)

        if completion < min_completion:
            continue

        results.append({
            "candidate_id": candidate.id,
            "user_id": candidate.user_id,
            "full_name": user.full_name,
            "email": user.email,
            "phone": candidate.phone,
            "skills": candidate.skills,
            "qualification": candidate.qualification,
            "experience_years": candidate.experience_years,
            "city": candidate.city,
            "resume_path": candidate.resume_path,
            "profile_completion_percentage": completion
        })

    total = len(results)

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "total_candidates": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "candidates": results[start:end]
    }