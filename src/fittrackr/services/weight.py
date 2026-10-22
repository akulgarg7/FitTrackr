
"""Weight tracking operations for FitTrackr."""

import math
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from fittrackr.models import Profile, WeightEntry


def _validate_measurement(
    weight_kg: float,
    measured_on: date,
) -> None:
    """Validate the weight and its measurement date."""

    if (
        isinstance(weight_kg, bool)
        or not isinstance(weight_kg, (int, float))
        or not math.isfinite(weight_kg)
        or weight_kg <= 0
    ):
        raise ValueError("Weight must be a positive, finite number.")

    if not isinstance(measured_on, date):
        raise ValueError("Measurement date must be a valid date.")

    if measured_on > date.today():
        raise ValueError("Measurement date cannot be in the future.")


def add_weight_entry(
    session: Session,
    *,
    weight_kg: float,
    measured_on: date | None = None,
) -> WeightEntry:
    """Record a new measurement for the existing profile."""

    measurement_date = measured_on or date.today()
    _validate_measurement(weight_kg, measurement_date)

    if session.get(Profile, 1) is None:
        raise ValueError("Create a profile before recording your weight.")

    entry = WeightEntry(
        profile_id=1,
        weight_kg=weight_kg,
        measured_on=measurement_date,
    )

    try:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    except Exception:
        session.rollback()
        raise


def get_weight_history(session: Session) -> list[WeightEntry]:
    """Return all measurements, newest first."""

    statement = (
        select(WeightEntry)
        .where(WeightEntry.profile_id == 1)
        .order_by(
            WeightEntry.measured_on.desc(),
            WeightEntry.id.desc(),
        )
    )

    return list(session.scalars(statement).all())


def update_weight_entry(
    session: Session,
    *,
    entry_id: int,
    weight_kg: float,
    measured_on: date,
) -> WeightEntry:
    """Correct an existing measurement without creating a new entry."""

    _validate_measurement(weight_kg, measured_on)

    entry = session.scalar(
        select(WeightEntry).where(
            WeightEntry.id == entry_id,
            WeightEntry.profile_id == 1,
        )
    )

    if entry is None:
        raise ValueError("Weight entry was not found.")

    try:
        entry.weight_kg = weight_kg
        entry.measured_on = measured_on

        session.commit()
        session.refresh(entry)
        return entry
    except Exception:
        session.rollback()
        raise
