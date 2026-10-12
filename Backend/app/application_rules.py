
from datetime import date, datetime, timedelta


MAX_APPLICATIONS_PER_30_DAYS = 10
MIN_PROFILE_COMPLETION = 80

VALID_STATUS_TRANSITIONS = {
    "APPLIED": {"UNDER_REVIEW", "REJECTED", "WITHDRAWN"},
    "UNDER_REVIEW": {"SHORTLISTED", "REJECTED", "WITHDRAWN"},
    "SHORTLISTED": {
        "INTERVIEW_SCHEDULED",
        "REJECTED",
        "SELECTED",
        "WITHDRAWN",
    },
    "INTERVIEW_SCHEDULED": {
        "SELECTED",
        "REJECTED",
        "WITHDRAWN",
    },
    "SELECTED": {"HIRED", "REJECTED"},
    "HIRED": set(),
    "REJECTED": set(),
    "WITHDRAWN": set(),
}


def normalize_status(status):
    """Return a status enum or string as uppercase text."""
    value = getattr(status, "value", status)
    return str(value).upper()


def can_transition_status(old_status, new_status):
    """Check whether an application status change is permitted."""
    old_value = normalize_status(old_status)
    new_value = normalize_status(new_status)

    return new_value in VALID_STATUS_TRANSITIONS.get(old_value, set())


def is_job_open(job, today=None):
    """A job is open only when active and before its deadline."""
    today = today or date.today()

    status = normalize_status(job.status)
    if status != "ACTIVE":
        return False

    deadline = job.application_deadline
    if deadline is not None and deadline < today:
        return False

    return True


def profile_completion_percentage(candidate, user=None):
    """Calculate profile completion using the project's profile fields."""
    score = 0

    if user and getattr(user, "full_name", None):
        score += 10
    if getattr(candidate, "phone", None):
        score += 10
    if getattr(candidate, "qualification", None):
        score += 15
    if getattr(candidate, "skills", None):
        score += 20
    if getattr(candidate, "experience_years", None) is not None:
        score += 10
    if getattr(candidate, "resume_path", None):
        score += 25
    if getattr(candidate, "city", None) or getattr(candidate, "address", None):
        score += 5
    if getattr(candidate, "graduation_year", None):
        score += 5

    return min(score, 100)


def applications_allowed_in_window(
    recent_application_count,
    limit=MAX_APPLICATIONS_PER_30_DAYS,
):
    """Return whether another application is allowed."""
    return recent_application_count < limit