
"""Calorie-entry operations for FitTrackr."""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fittrackr.models import CalorieEntry, DailyLog, Profile
from fittrackr.services.daily_logs import get_daily_log


def _validate_date(log_date: date) -> None:
    """Validate a calendar date and disallow future records."""
    if isinstance(log_date, datetime) or not isinstance(log_date, date):
        raise ValueError("Log date must be a valid calendar date.")

    if log_date > date.today():
        raise ValueError("Calorie entries cannot be dated in the future.")


def _validate_calorie_entry(
    description: str,
    delta_kcal: int,
) -> str:
    """Validate an entry description and signed calorie adjustment."""
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Entry description cannot be empty.")

    if len(description.strip()) > 160:
        raise ValueError("Description cannot exceed 160 characters.")

    if (
        isinstance(delta_kcal, bool)
        or not isinstance(delta_kcal, int)
        or delta_kcal == 0
    ):
        raise ValueError(
            "Calorie adjustment must be a non-zero whole number."
        )

    return description.strip()


def _get_or_create_daily_log(
    session: Session,
    log_date: date,
) -> DailyLog:
    """Find or create the daily log needed for calorie entries."""
    if session.get(Profile, 1) is None:
        raise ValueError("Create a profile before recording calories.")

    daily_log = get_daily_log(session, log_date)

    if daily_log is None:
        daily_log = DailyLog(
            profile_id=1,
            log_date=log_date,
        )
        session.add(daily_log)
        session.flush()

    return daily_log


def _total_for_daily_log(
    session: Session,
    daily_log_id: int,
) -> int:
    """Calculate the calorie total for one daily log."""
    total = session.scalar(
        select(func.coalesce(func.sum(CalorieEntry.delta_kcal), 0))
        .where(CalorieEntry.daily_log_id == daily_log_id)
    )

    return int(total or 0)


def get_calorie_entries(
    session: Session,
    *,
    log_date: date,
) -> list[CalorieEntry]:
    """Return calorie entries for a date, oldest first."""
    _validate_date(log_date)

    daily_log = get_daily_log(session, log_date)

    if daily_log is None:
        return []

    statement = (
        select(CalorieEntry)
        .where(CalorieEntry.daily_log_id == daily_log.id)
        .order_by(CalorieEntry.id)
    )

    return list(session.scalars(statement).all())


def get_daily_calorie_total(
    session: Session,
    *,
    log_date: date,
) -> int:
    """Return the sum of all calorie adjustments for a date."""
    _validate_date(log_date)

    daily_log = get_daily_log(session, log_date)

    if daily_log is None:
        return 0

    return _total_for_daily_log(session, daily_log.id)


def add_calorie_entry(
    session: Session,
    *,
    log_date: date,
    description: str,
    delta_kcal: int,
) -> CalorieEntry:
    """Add a positive calorie entry or a negative correction."""
    _validate_date(log_date)
    description = _validate_calorie_entry(description, delta_kcal)

    try:
        daily_log = _get_or_create_daily_log(session, log_date)
        current_total = _total_for_daily_log(session, daily_log.id)
        new_total = current_total + delta_kcal

        if new_total < 0:
            raise ValueError(
                "This adjustment would make the day's calorie total negative."
            )

        entry = CalorieEntry(
            daily_log_id=daily_log.id,
            description=description,
            delta_kcal=delta_kcal,
        )

        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry

    except Exception:
        session.rollback()
        raise


def update_calorie_entry(
    session: Session,
    *,
    entry_id: int,
    description: str,
    delta_kcal: int,
) -> CalorieEntry:
    """Correct an existing entry without creating a duplicate."""
    description = _validate_calorie_entry(description, delta_kcal)

    entry = session.scalar(
        select(CalorieEntry)
        .join(DailyLog)
        .where(
            CalorieEntry.id == entry_id,
            DailyLog.profile_id == 1,
        )
    )

    if entry is None:
        raise ValueError("Calorie entry was not found.")

    try:
        current_total = _total_for_daily_log(
            session, entry.daily_log_id
        )
        revised_total = current_total - entry.delta_kcal + delta_kcal

        if revised_total < 0:
            raise ValueError(
                "This correction would make the day's calorie total negative."
            )

        entry.description = description
        entry.delta_kcal = delta_kcal

        session.commit()
        session.refresh(entry)
        return entry

    except Exception:
        session.rollback()
        raise


def delete_calorie_entry(
    session: Session,
    *,
    entry_id: int,
) -> None:
    """Delete an entry only if the resulting daily total stays non-negative."""
    entry = session.scalar(
        select(CalorieEntry)
        .join(DailyLog)
        .where(
            CalorieEntry.id == entry_id,
            DailyLog.profile_id == 1,
        )
    )

    if entry is None:
        raise ValueError("Calorie entry was not found.")

    try:
        current_total = _total_for_daily_log(
            session, entry.daily_log_id
        )
        revised_total = current_total - entry.delta_kcal

        if revised_total < 0:
            raise ValueError(
                "Deleting this entry would make the day's calorie total negative."
            )

        session.delete(entry)
        session.commit()

    except Exception:
        session.rollback()
        raise
