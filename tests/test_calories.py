
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fittrackr import models as _models
from fittrackr.database import Base
from fittrackr.services.profile import create_profile
from fittrackr.services.calories import (
    add_calorie_entry,
    delete_calorie_entry,
    get_calorie_entries,
    get_daily_calorie_total,
    update_calorie_entry,
)


@pytest.fixture
def session():
    """Use a fresh in-memory database for each test."""
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
    """Create a fictional profile for calorie tests."""
    return create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )


def test_add_and_subtract_calories(session):
    create_test_profile(session)
    today = date.today()

    add_calorie_entry(
        session,
        log_date=today,
        description="Breakfast",
        delta_kcal=400,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Lunch",
        delta_kcal=650,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Correction",
        delta_kcal=-100,
    )

    assert get_daily_calorie_total(session, log_date=today) == 950
    assert len(get_calorie_entries(session, log_date=today)) == 3


def test_historical_calorie_totals_are_independent(session):
    create_test_profile(session)
    yesterday = date.today() - timedelta(days=1)
    today = date.today()

    add_calorie_entry(
        session,
        log_date=yesterday,
        description="Yesterday's meals",
        delta_kcal=1800,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Today's breakfast",
        delta_kcal=400,
    )

    assert get_daily_calorie_total(session, log_date=yesterday) == 1800
    assert get_daily_calorie_total(session, log_date=today) == 400


def test_updating_entry_recalculates_total_without_duplicate(session):
    create_test_profile(session)
    today = date.today()

    entry = add_calorie_entry(
        session,
        log_date=today,
        description="Breakfast",
        delta_kcal=400,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Lunch",
        delta_kcal=650,
    )

    update_calorie_entry(
        session,
        entry_id=entry.id,
        description="Corrected breakfast",
        delta_kcal=300,
    )

    assert get_daily_calorie_total(session, log_date=today) == 950
    assert len(get_calorie_entries(session, log_date=today)) == 2


def test_adjustment_cannot_make_total_negative(session):
    create_test_profile(session)
    today = date.today()

    add_calorie_entry(
        session,
        log_date=today,
        description="Breakfast",
        delta_kcal=400,
    )

    with pytest.raises(ValueError, match="negative"):
        add_calorie_entry(
            session,
            log_date=today,
            description="Invalid correction",
            delta_kcal=-500,
        )

    assert get_daily_calorie_total(session, log_date=today) == 400
    assert len(get_calorie_entries(session, log_date=today)) == 1


def test_zero_calorie_adjustment_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="non-zero"):
        add_calorie_entry(
            session,
            log_date=date.today(),
            description="No adjustment",
            delta_kcal=0,
        )


def test_empty_description_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="description"):
        add_calorie_entry(
            session,
            log_date=date.today(),
            description="  ",
            delta_kcal=100,
        )


def test_delete_entry_recalculates_total(session):
    create_test_profile(session)
    today = date.today()

    removable = add_calorie_entry(
        session,
        log_date=today,
        description="Snack",
        delta_kcal=200,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Lunch",
        delta_kcal=600,
    )

    delete_calorie_entry(session, entry_id=removable.id)

    assert get_daily_calorie_total(session, log_date=today) == 600
    assert len(get_calorie_entries(session, log_date=today)) == 1


def test_deletion_cannot_make_total_negative(session):
    create_test_profile(session)
    today = date.today()

    positive_entry = add_calorie_entry(
        session,
        log_date=today,
        description="Meal",
        delta_kcal=400,
    )
    add_calorie_entry(
        session,
        log_date=today,
        description="Correction",
        delta_kcal=-100,
    )

    with pytest.raises(ValueError, match="negative"):
        delete_calorie_entry(
            session,
            entry_id=positive_entry.id,
        )

    assert get_daily_calorie_total(session, log_date=today) == 300


def test_future_calorie_date_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="future"):
        add_calorie_entry(
            session,
            log_date=date.today() + timedelta(days=1),
            description="Future meal",
            delta_kcal=500,
        )


def test_calorie_entry_requires_profile(session):
    with pytest.raises(ValueError, match="profile"):
        add_calorie_entry(
            session,
            log_date=date.today(),
            description="Breakfast",
            delta_kcal=400,
        )
