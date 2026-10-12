from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from Backend.app.database import get_db
from Backend.app.models.user import User
from Backend.app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse
)
from Backend.app.utils.security import (
    hash_password,
    verify_password
)
from Backend.app.utils.auth import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=TokenResponse
)
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
   
    existing_user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    if request.role not in ["HR", "CANDIDATE"]:
        raise HTTPException(
            status_code=400,
            detail="Role must be HR or CANDIDATE"
        )

    # Create user
    new_user = User(
        full_name=request.full_name,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        phone=request.phone
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(
        user_id=new_user.id,
        role=new_user.role
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    if not verify_password(
        request.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account is inactive"
        )
    token = create_access_token(
        user_id=user.id,
        role=user.role
    )
    return {
        "access_token": token,
        "token_type": "bearer"
    }

from Backend.app.utils.auth import get_current_user


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "phone": current_user.phone,
        "is_active": current_user.is_active
    }