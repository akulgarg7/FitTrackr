
"""Daily tracking operations for FitTrackr."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from fittrackr.models import DailyLog, Profile, WorkoutExercise


WORKOUT_TYPES = (
    "Push",
    "Pull",
    "Legs",
    "Upper Body",
    "Lower Body",
    "Full Body",
    "Arms",
    "Shoulders",
    "Core",
    "Cardio",
    "Sports",
    "Other",
)

_WORKOUT_TYPE_LOOKUP = {
    " ".join(value.casefold().split()): value
    for value in WORKOUT_TYPES
}


def _validate_date(log_date: date) -> None:
    """Validate a daily-log date."""
    if isinstance(log_date, datetime) or not isinstance(log_date, date):
        raise ValueError("Log date must be a valid calendar date.")


def _validate_recording_date(log_date: date) -> None:
    """Prevent creating or modifying records for future dates."""
    _validate_date(log_date)

    if log_date > date.today():
        raise ValueError("Daily records cannot be dated in the future.")


def _get_or_create_daily_log(
    session: Session,
    log_date: date,
) -> DailyLog:
    """Return the existing log for a date or create an empty one."""

    profile = session.get(Profile, 1)

    if profile is None:
        raise ValueError("Create a profile before recording daily activity.")

    statement = select(DailyLog).where(
        DailyLog.profile_id == 1,
        DailyLog.log_date == log_date,
    )

    daily_log = session.scalars(statement).first()

    if daily_log is None:
        daily_log = DailyLog(
            profile_id=1,
            log_date=log_date,
        )
        session.add(daily_log)

    return daily_log


def get_daily_log(
    session: Session,
    log_date: date,
) -> DailyLog | None:
    """Retrieve the daily log for a date without creating one."""

    _validate_date(log_date)

    statement = select(DailyLog).where(
        DailyLog.profile_id == 1,
        DailyLog.log_date == log_date,
    )

    return session.scalars(statement).first()


def save_steps(
    session: Session,
    *,
    log_date: date,
    steps: int | None,
) -> DailyLog:
    """Save or clear the step count without changing workout information."""

    _validate_recording_date(log_date)

    if steps is not None:
        if (
            isinstance(steps, bool)
            or not isinstance(steps, int)
            or steps < 0
        ):
            raise ValueError(
                "Steps must be a non-negative whole number."
            )

    try:
        daily_log = _get_or_create_daily_log(session, log_date)
        daily_log.steps = steps

        session.commit()
        session.refresh(daily_log)
        return daily_log

    except Exception:
        session.rollback()
        raise


def save_workout(
    session: Session,
    *,
    log_date: date,
    did_workout: bool | None,
    workout_type: str | None = None,
) -> DailyLog:
    """Save workout status and type without changing the step count.

    did_workout:
        True  = worked out.
        False = did not work out.
        None  = not recorded.

    A workout type is required when did_workout is True.
    Setting status to False or None also clears associated exercise
    entries, because those entries would no longer represent the
    selected workout status.
    """

    _validate_recording_date(log_date)

    if did_workout is not None and not isinstance(did_workout, bool):
        raise ValueError("Workout status must be True, False, or None.")

    normalized_workout_type = None

    if did_workout is True:
        if not isinstance(workout_type, str) or not workout_type.strip():
            raise ValueError(
                "Select a workout type when recording a workout."
            )

        key = " ".join(workout_type.casefold().split())

        if key not in _WORKOUT_TYPE_LOOKUP:
            raise ValueError(
                f"Unsupported workout type: {workout_type!r}"
            )

        normalized_workout_type = _WORKOUT_TYPE_LOOKUP[key]

    elif workout_type is not None:
        raise ValueError(
            "A workout type can only be set when workout status is True."
        )

    try:
        daily_log = _get_or_create_daily_log(session, log_date)

        daily_log.did_workout = did_workout
        daily_log.workout_type = normalized_workout_type

        # A No or not-recorded status must not leave old exercises
        # attached to a day that is no longer marked as a workout.
        if did_workout is not True:
            for exercise_entry in list(daily_log.workout_exercises):
                session.delete(exercise_entry)

        session.commit()
        session.refresh(daily_log)
        return daily_log

    except Exception:
        session.rollback()
        raise
