
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from fittrackr import models as _models
from fittrackr.database import Base
from fittrackr.models import WeightEntry
from fittrackr.services.profile import create_profile, get_latest_weight
from fittrackr.services.weight import (
    add_weight_entry,
    get_weight_history,
    update_weight_entry,
)


@pytest.fixture
def session():
    """Create a fresh in-memory SQLite database for each test."""

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
    """Create a fictional profile with an initial weight."""

    return create_profile(
        session,
        name="Test User",
        age=25,
        gender="Male",
        height_cm=175,
        weight_kg=72,
        activity_level="moderately active",
    )


def test_add_weight_entry(session):
    create_test_profile(session)

    entry = add_weight_entry(
        session,
        weight_kg=71.5,
        measured_on=date.today(),
    )

    assert entry.weight_kg == 71.5
    assert entry.measured_on == date.today()
    assert get_latest_weight(session).weight_kg == 71.5


def test_past_measurement_does_not_replace_latest_weight(session):
    create_test_profile(session)

    add_weight_entry(
        session,
        weight_kg=73,
        measured_on=date.today() - timedelta(days=3),
    )

    assert get_latest_weight(session).weight_kg == 72
    assert len(get_weight_history(session)) == 2


def test_update_entry_preserves_history_count(session):
    create_test_profile(session)

    entry = add_weight_entry(
        session,
        weight_kg=73,
        measured_on=date.today() - timedelta(days=3),
    )

    update_weight_entry(
        session,
        entry_id=entry.id,
        weight_kg=72.5,
        measured_on=date.today() - timedelta(days=2),
    )

    history = get_weight_history(session)

    assert len(history) == 2
    assert session.get(WeightEntry, entry.id).weight_kg == 72.5


def test_invalid_weight_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="positive"):
        add_weight_entry(session, weight_kg=0)

    assert len(get_weight_history(session)) == 1


def test_future_date_is_rejected(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="future"):
        add_weight_entry(
            session,
            weight_kg=71,
            measured_on=date.today() + timedelta(days=1),
        )

    assert len(get_weight_history(session)) == 1


def test_unknown_entry_cannot_be_updated(session):
    create_test_profile(session)

    with pytest.raises(ValueError, match="not found"):
        update_weight_entry(
            session,
            entry_id=9999,
            weight_kg=71,
            measured_on=date.today(),
        )
