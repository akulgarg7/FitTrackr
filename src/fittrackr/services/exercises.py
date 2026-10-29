
"""Exercise library and workout-exercise operations for FitTrackr."""

import math
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fittrackr.models import (
    DailyLog,
    ExerciseLibrary,
    Profile,
    WorkoutExercise,
)
from fittrackr.services.daily_logs import get_daily_log


EXERCISE_CATEGORIES = ("strength", "cardio")


def get_exercises(
    session: Session,
    *,
    muscle_group: str | None = None,
    category: str | None = None,
) -> list[ExerciseLibrary]:
    """Return exercises, optionally filtering by muscle group or category.

    Omitting the filters returns the full exercise library, regardless
    of the selected daily workout type.
    """
    statement = select(ExerciseLibrary)

    if muscle_group:
        statement = statement.where(
            func.lower(ExerciseLibrary.muscle_group)
            == muscle_group.strip().lower()
        )

    if category:
        normalized_category = category.strip().lower()

        if normalized_category not in EXERCISE_CATEGORIES:
            raise ValueError(
                "Category must be 'strength' or 'cardio'."
            )

        statement = statement.where(
            ExerciseLibrary.category == normalized_category
        )

    statement = statement.order_by(
        ExerciseLibrary.muscle_group,
        ExerciseLibrary.name,
    )

    return list(session.scalars(statement).all())


def add_custom_exercise(
    session: Session,
    *,
    name: str,
    muscle_group: str,
    category: str,
    description: str | None = None,
) -> ExerciseLibrary:
    """Add an exercise to the library without marking it as built-in."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Exercise name cannot be empty.")

    if not isinstance(muscle_group, str) or not muscle_group.strip():
        raise ValueError("Muscle group cannot be empty.")

    if len(name.strip()) > 100:
        raise ValueError("Exercise name cannot exceed 100 characters.")

    if len(muscle_group.strip()) > 40:
        raise ValueError("Muscle group cannot exceed 40 characters.")

    if description is not None and len(description.strip()) > 250:
        raise ValueError("Description cannot exceed 250 characters.")

    normalized_category = category.strip().lower()

    if normalized_category not in EXERCISE_CATEGORIES:
        raise ValueError("Category must be 'strength' or 'cardio'.")

    normalized_name = name.strip()

    existing = session.scalar(
        select(ExerciseLibrary).where(
            func.lower(ExerciseLibrary.name)
            == normalized_name.lower()
        )
    )

    if existing is not None:
        raise ValueError(
            "An exercise with this name already exists."
        )

    exercise = ExerciseLibrary(
        name=normalized_name,
        muscle_group=muscle_group.strip(),
        category=normalized_category,
        description=description.strip() if description else None,
        is_builtin=False,
    )

    try:
        session.add(exercise)
        session.commit()
        session.refresh(exercise)
        return exercise
    except Exception:
        session.rollback()
        raise


def _validate_exercise_details(
    *,
    category: str,
    sets: int | None,
    reps: int | None,
    weight_kg: float | None,
    duration_minutes: int | None,
) -> None:
    """Validate strength or cardio fields based on exercise category."""

    if category == "strength":
        if (
            isinstance(sets, bool)
            or not isinstance(sets, int)
            or sets < 1
        ):
            raise ValueError(
                "Strength exercises require at least one set."
            )

        if (
            isinstance(reps, bool)
            or not isinstance(reps, int)
            or reps < 1
        ):
            raise ValueError(
                "Strength exercises require at least one rep per set."
            )

        if duration_minutes is not None:
            raise ValueError(
                "Duration is only used for cardio exercises."
            )

        if weight_kg is not None:
            if (
                isinstance(weight_kg, bool)
                or not isinstance(weight_kg, (int, float))
                or not math.isfinite(weight_kg)
                or weight_kg < 0
            ):
                raise ValueError(
                    "Exercise weight must be a finite, non-negative number."
                )

    elif category == "cardio":
        if sets is not None or reps is not None or weight_kg is not None:
            raise ValueError(
                "Cardio entries use duration, not sets, reps, or weight."
            )

        if (
            isinstance(duration_minutes, bool)
            or not isinstance(duration_minutes, int)
            or duration_minutes < 1
        ):
            raise ValueError(
                "Cardio exercises require a positive duration in minutes."
            )

    else:
        raise ValueError("Unsupported exercise category.")


def add_workout_exercise(
    session: Session,
    *,
    log_date: date,
    exercise_id: int,
    sets: int | None = None,
    reps: int | None = None,
    weight_kg: float | None = None,
    duration_minutes: int | None = None,
) -> WorkoutExercise:
    """Add one exercise to a day already marked as a workout."""

    daily_log = get_daily_log(session, log_date)

    if daily_log is None or daily_log.did_workout is not True:
        raise ValueError(
            "Record a workout with status Yes before adding exercises."
        )

    exercise = session.get(ExerciseLibrary, exercise_id)

    if exercise is None:
        raise ValueError("Exercise was not found in the library.")

    _validate_exercise_details(
        category=exercise.category,
        sets=sets,
        reps=reps,
        weight_kg=weight_kg,
        duration_minutes=duration_minutes,
    )

    existing = session.scalar(
        select(WorkoutExercise).where(
            WorkoutExercise.daily_log_id == daily_log.id,
            WorkoutExercise.exercise_id == exercise_id,
        )
    )

    if existing is not None:
        raise ValueError(
            "This exercise is already recorded for this day. "
            "Update its existing entry instead."
        )

    entry = WorkoutExercise(
        daily_log_id=daily_log.id,
        exercise_id=exercise_id,
        sets=sets,
        reps=reps,
        weight_kg=weight_kg,
        duration_minutes=duration_minutes,
    )

    try:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry
    except Exception:
        session.rollback()
        raise


def get_workout_exercises(
    session: Session,
    *,
    log_date: date,
) -> list[WorkoutExercise]:
    """Return all exercise entries for a date, ordered by exercise name."""

    daily_log = get_daily_log(session, log_date)

    if daily_log is None:
        return []

    statement = (
        select(WorkoutExercise)
        .join(ExerciseLibrary)
        .where(WorkoutExercise.daily_log_id == daily_log.id)
        .order_by(ExerciseLibrary.muscle_group, ExerciseLibrary.name)
    )

    return list(session.scalars(statement).all())


def update_workout_exercise(
    session: Session,
    *,
    entry_id: int,
    sets: int | None = None,
    reps: int | None = None,
    weight_kg: float | None = None,
    duration_minutes: int | None = None,
) -> WorkoutExercise:
    """Correct exercise details without creating another entry."""

    entry = session.scalar(
        select(WorkoutExercise)
        .join(DailyLog)
        .where(
            WorkoutExercise.id == entry_id,
            DailyLog.profile_id == 1,
        )
    )

    if entry is None:
        raise ValueError("Workout exercise entry was not found.")

    if entry.daily_log.did_workout is not True:
        raise ValueError("The associated day is not marked as a workout.")

    _validate_exercise_details(
        category=entry.exercise.category,
        sets=sets,
        reps=reps,
        weight_kg=weight_kg,
        duration_minutes=duration_minutes,
    )

    try:
        entry.sets = sets
        entry.reps = reps
        entry.weight_kg = weight_kg
        entry.duration_minutes = duration_minutes

        session.commit()
        session.refresh(entry)
        return entry
    except Exception:
        session.rollback()
        raise


def delete_workout_exercise(
    session: Session,
    *,
    entry_id: int,
) -> None:
    """Delete one exercise entry without deleting its library definition."""

    entry = session.scalar(
        select(WorkoutExercise)
        .join(DailyLog)
        .where(
            WorkoutExercise.id == entry_id,
            DailyLog.profile_id == 1,
        )
    )

    if entry is None:
        raise ValueError("Workout exercise entry was not found.")

    try:
        session.delete(entry)
        session.commit()
    except Exception:
        session.rollback()
        raise
