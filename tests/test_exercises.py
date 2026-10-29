
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fittrackr import models as _models
from fittrackr.database import Base
from fittrackr.models import ExerciseLibrary
from fittrackr.services.profile import create_profile
from fittrackr.services.daily_logs import save_workout
from fittrackr.services.exercises import (
    add_custom_exercise,
    add_workout_exercise,
    delete_workout_exercise,
    get_exercises,
    get_workout_exercises,
    update_workout_exercise,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine, expire_on_commit=False) as db_session:
        yield db_session

    Base.metadata.drop_all(engine)
    engine.dispose()


def prepare_workout(session):
    create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )

    save_workout(
        session,
        log_date=date.today(),
        did_workout=True,
        workout_type="Push",
    )

    return add_custom_exercise(
        session,
        name="Test Bench Press",
        muscle_group="Chest",
        category="strength",
    )


def test_custom_exercise_is_saved(session):
    exercise = add_custom_exercise(
        session,
        name="My Cable Fly",
        muscle_group="Chest",
        category="strength",
    )

    assert exercise.name == "My Cable Fly"
    assert exercise.is_builtin is False


def test_duplicate_exercise_names_are_rejected(session):
    add_custom_exercise(
        session,
        name="My Cable Fly",
        muscle_group="Chest",
        category="strength",
    )

    with pytest.raises(ValueError, match="already exists"):
        add_custom_exercise(
            session,
            name="my cable fly",
            muscle_group="Chest",
            category="strength",
        )


def test_exercise_library_can_be_filtered(session):
    add_custom_exercise(
        session,
        name="Test Chest Exercise",
        muscle_group="Chest",
        category="strength",
    )
    add_custom_exercise(
        session,
        name="Test Cardio Exercise",
        muscle_group="Cardio",
        category="cardio",
    )

    chest = get_exercises(session, muscle_group="chest")
    cardio = get_exercises(session, category="cardio")
    all_exercises = get_exercises(session)

    assert any(item.name == "Test Chest Exercise" for item in chest)
    assert all(item.category == "cardio" for item in cardio)
    assert len(all_exercises) == 2


def test_add_strength_exercise(session):
    exercise = prepare_workout(session)

    entry = add_workout_exercise(
        session,
        log_date=date.today(),
        exercise_id=exercise.id,
        sets=4,
        reps=8,
        weight_kg=50,
    )

    assert entry.sets == 4
    assert entry.reps == 8
    assert entry.weight_kg == 50
    assert entry.duration_minutes is None


def test_add_cardio_exercise(session):
    create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )

    save_workout(
        session,
        log_date=date.today(),
        did_workout=True,
        workout_type="Cardio",
    )

    exercise = add_custom_exercise(
        session,
        name="Test Treadmill",
        muscle_group="Cardio",
        category="cardio",
    )

    entry = add_workout_exercise(
        session,
        log_date=date.today(),
        exercise_id=exercise.id,
        duration_minutes=20,
    )

    assert entry.duration_minutes == 20
    assert entry.sets is None
    assert entry.reps is None


def test_strength_requires_sets_and_reps(session):
    exercise = prepare_workout(session)

    with pytest.raises(ValueError, match="set"):
        add_workout_exercise(
            session,
            log_date=date.today(),
            exercise_id=exercise.id,
            reps=8,
        )


def test_cardio_requires_duration(session):
    create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )
    save_workout(
        session,
        log_date=date.today(),
        did_workout=True,
        workout_type="Cardio",
    )
    exercise = add_custom_exercise(
        session,
        name="Test Cycling",
        muscle_group="Cardio",
        category="cardio",
    )

    with pytest.raises(ValueError, match="duration"):
        add_workout_exercise(
            session,
            log_date=date.today(),
            exercise_id=exercise.id,
        )


def test_workout_exercises_can_be_updated_and_deleted(session):
    exercise = prepare_workout(session)
    entry = add_workout_exercise(
        session,
        log_date=date.today(),
        exercise_id=exercise.id,
        sets=3,
        reps=10,
    )

    update_workout_exercise(
        session,
        entry_id=entry.id,
        sets=4,
        reps=8,
        weight_kg=40,
    )
    assert entry.sets == 4
    assert entry.reps == 8

    delete_workout_exercise(session, entry_id=entry.id)
    assert get_workout_exercises(
        session, log_date=date.today()
    ) == []
