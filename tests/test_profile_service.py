
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fittrackr import models as _models
from fittrackr.database import Base
from fittrackr.models import WeightEntry
from fittrackr.services.profile import (
    create_profile,
    get_latest_weight,
    get_profile,
    update_profile,
)


@pytest.fixture
def session():
    """Give each test a fresh in-memory database."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(test_engine)

    with Session(test_engine, expire_on_commit=False) as db_session:
        yield db_session

    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


def create_test_profile(session):
    """Create a reusable fictional profile."""
    return create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )


def test_create_profile_and_initial_weight(session):
    profile = create_test_profile(session)

    assert profile.name == "Test User"
    assert get_profile(session).id == 1

    weight = get_latest_weight(session)
    assert weight.weight_kg == 72
    assert weight.measured_on == date.today()


def test_profile_cannot_be_created_twice(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="already exists"):
        create_test_profile(session)


def test_weight_update_preserves_history(session):
    create_test_profile(session)

    update_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=71.5,
        activity_level="moderately active",
    )

    entries = session.scalars(
        select(WeightEntry).order_by(WeightEntry.id)
    ).all()

    assert len(entries) == 2
    assert entries[0].weight_kg == 72
    assert get_latest_weight(session).weight_kg == 71.5


def test_unchanged_weight_does_not_add_history_entry(session):
    create_test_profile(session)

    update_profile(
        session,
        name="Test User",
        age=26,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )

    entries = session.scalars(select(WeightEntry)).all()

    assert len(entries) == 1
    assert get_profile(session).age == 26


def test_invalid_gender_does_not_create_profile(session):
    with pytest.raises(ValueError):
        create_profile(
            session,
            name="Test User",
            age=25,
            gender="Unknown",
            height_cm=175,
            weight_kg=72,
            activity_level="moderately active",
        )

    assert get_profile(session) is None
