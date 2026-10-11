from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from fittrackr.calculations import (
    ACTIVITY_FACTORS,
    calculate_bmi,
    calculate_maintenance_calories,
)
from fittrackr.models import Profile, WeightEntry


def _normalize_gender(gender: str) -> str:
    """Validate and normalize gender for the selected calorie formula."""
    value = gender.strip().lower()

    if value not in {"male", "female"}:
        raise ValueError(
            "Gender must be Male or Female for the selected formula."
        )

    return value.title()



def _normalize_activity_level(activity_level: str) -> str:
    """Validate and normalize the activity level for database storage."""
    value = " ".join(
        activity_level.strip().lower().replace("_", " ").split()
    )

    if value not in ACTIVITY_FACTORS:
        raise ValueError(
            f"Unsupported activity level: {activity_level!r}"
        )

    # Store values using the format required by the database constraint.
    return value.replace(" ", "_")



def _validate_profile_data(
    name: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> tuple[str, str]:
    """Validate profile inputs before saving them."""
    if not name.strip():
        raise ValueError("Name cannot be empty.")

    normalized_gender = _normalize_gender(gender)
    normalized_activity = _normalize_activity_level(activity_level)

    # Reuse the calculation functions to validate measurements.
    calculate_bmi(weight_kg, height_cm)
    calculate_maintenance_calories(
        age=age,
        gender=normalized_gender,
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity_level=normalized_activity,
    )

    return normalized_gender, normalized_activity


def get_profile(session: Session) -> Profile | None:
    """Return the single profile, or None if it has not been created."""
    return session.get(Profile, 1)


def get_latest_weight(session: Session) -> WeightEntry | None:
    """Return the latest measurement by date, then by entry ID."""
    statement = (
        select(WeightEntry)
        .where(WeightEntry.profile_id == 1)
        .order_by(
            WeightEntry.measured_on.desc(),
            WeightEntry.id.desc(),
        )
        .limit(1)
    )

    return session.scalars(statement).first()


def create_profile(
    session: Session,
    *,
    name: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> Profile:
    """Create the profile and its initial dated weight measurement."""
    if get_profile(session) is not None:
        raise ValueError("A FitTrackr profile already exists.")

    normalized_gender, normalized_activity = _validate_profile_data(
        name, age, gender, height_cm, weight_kg, activity_level
    )

    profile = Profile(
        id=1,
        name=name.strip(),
        age=age,
        gender=normalized_gender,
        height_cm=height_cm,
        activity_level=normalized_activity,
    )

    try:
        session.add(profile)
        session.flush()

        initial_weight = WeightEntry(
            profile_id=profile.id,
            weight_kg=weight_kg,
            measured_on=date.today(),
        )
        session.add(initial_weight)

        session.commit()
        session.refresh(profile)
        return profile
    except Exception:
        session.rollback()
        raise


def update_profile(
    session: Session,
    *,
    name: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> Profile:
    """Update current details and record a changed weight as a new entry."""
    profile = get_profile(session)

    if profile is None:
        raise ValueError("Create a profile before trying to update it.")

    normalized_gender, normalized_activity = _validate_profile_data(
        name, age, gender, height_cm, weight_kg, activity_level
    )

    latest_weight = get_latest_weight(session)

    try:
        profile.name = name.strip()
        profile.age = age
        profile.gender = normalized_gender
        profile.height_cm = height_cm
        profile.activity_level = normalized_activity

        # Preserve history rather than overwriting an earlier measurement.
        if (
            latest_weight is None
            or latest_weight.weight_kg != weight_kg
        ):
            session.add(
                WeightEntry(
                    profile_id=profile.id,
                    weight_kg=weight_kg,
                    measured_on=date.today(),
                )
            )

        session.commit()
        session.refresh(profile)
        return profile
    except Exception:
        session.rollback()
        raise
