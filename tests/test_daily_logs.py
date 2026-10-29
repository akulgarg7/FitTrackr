
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fittrackr import models as _models
from fittrackr.database import Base
from fittrackr.services.profile import create_profile
from fittrackr.services.daily_logs import (
    get_daily_log,
    save_steps,
    save_workout,
)


@pytest.fixture
def session():
    """Create a fresh in-memory database for each test."""

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


def create_test_profile(session):
    """Create a fictional profile for daily-log tests."""

    return create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )


def test_save_steps_creates_daily_log(session):
    create_test_profile(session)

    log = save_steps(
        session,
        log_date=date.today(),
        steps=8000,
    )

    assert log.steps == 8000
    assert log.did_workout is None
    assert log.workout_type is None


def test_steps_and_workout_can_be_saved_independently(session):
    create_test_profile(session)
    today = date.today()

    save_steps(session, log_date=today, steps=8000)
    save_workout(
        session,
        log_date=today,
        did_workout=True,
        workout_type="push",
    )

    log = get_daily_log(session, today)

    assert log.steps == 8000
    assert log.did_workout is True
    assert log.workout_type == "Push"

    # Updating the steps must not erase workout information.
    save_steps(session, log_date=today, steps=8500)

    log = get_daily_log(session, today)

    assert log.steps == 8500
    assert log.did_workout is True
    assert log.workout_type == "Push"


def test_workout_status_can_be_no(session):
    create_test_profile(session)
    today = date.today()

    log = save_workout(
        session,
        log_date=today,
        did_workout=False,
    )

    assert log.did_workout is False
    assert log.workout_type is None


def test_workout_can_remain_unrecorded(session):
    create_test_profile(session)

    save_steps(
        session,
        log_date=date.today(),
        steps=100,
    )

    log = get_daily_log(session, date.today())

    assert log is not None
    assert log.did_workout is None


def test_same_date_reuses_existing_daily_log(session):
    create_test_profile(session)
    today = date.today()

    first = save_steps(
        session,
        log_date=today,
        steps=1000,
    )
    second = save_steps(
        session,
        log_date=today,
        steps=2000,
    )

    assert first.id == second.id
    assert second.steps == 2000


@pytest.mark.parametrize("invalid_steps", [-1, 1.5, True, "100"])
def test_invalid_steps_are_rejected(session, invalid_steps):
    create_test_profile(session)

    with pytest.raises(ValueError):
        save_steps(
            session,
            log_date=date.today(),
            steps=invalid_steps,
        )


def test_future_daily_log_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="future"):
        save_steps(
            session,
            log_date=date.today() + timedelta(days=1),
            steps=1000,
        )


def test_workout_type_required_when_workout_is_yes(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="workout type"):
        save_workout(
            session,
            log_date=date.today(),
            did_workout=True,
        )
