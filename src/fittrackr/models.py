
"""SQLAlchemy models for FitTrackr."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fittrackr.database import Base


class Profile(Base):
    """The single user profile for this version of FitTrackr."""

    __tablename__ = "profile"

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_profile_singleton"),
        CheckConstraint("age > 0", name="ck_profile_age_positive"),
        CheckConstraint("height_cm > 0", name="ck_profile_height_positive"),
        CheckConstraint(
            "activity_level IN "
            "('sedentary', 'lightly_active', 'moderately_active', "
            "'very_active', 'extra_active')",
            name="ck_profile_activity_level",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, default=1, server_default="1"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(30), nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    activity_level: Mapped[str] = mapped_column(
        String(30), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    weight_entries: Mapped[list[WeightEntry]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    daily_logs: Mapped[list[DailyLog]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    note: Mapped[AppNote | None] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        uselist=False,
    )


class WeightEntry(Base):
    """A dated weight measurement."""

    __tablename__ = "weight_entries"

    __table_args__ = (
        CheckConstraint("weight_kg > 0", name="ck_weight_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"),
        default=1,
        server_default="1",
        nullable=False,
        index=True,
    )
    weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(
        back_populates="weight_entries"
    )


class DailyLog(Base):
    """One daily record for steps and workout information."""

    __tablename__ = "daily_logs"

    __table_args__ = (
        UniqueConstraint(
            "profile_id", "log_date", name="uq_daily_log_profile_date"
        ),
        CheckConstraint(
            "steps IS NULL OR steps >= 0",
            name="ck_daily_log_steps_nonnegative",
        ),
        CheckConstraint(
            "did_workout IS NOT FALSE OR workout_type IS NULL",
            name="ck_no_workout_has_no_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"),
        default=1,
        server_default="1",
        nullable=False,
        index=True,
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)

    # None means the value has not been recorded yet.
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    did_workout: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )
    workout_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(back_populates="daily_logs")
    workout_exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="daily_log", cascade="all, delete-orphan"
    )
    calorie_entries: Mapped[list[CalorieEntry]] = relationship(
        back_populates="daily_log", cascade="all, delete-orphan"
    )


class ExerciseLibrary(Base):
    """Built-in and user-created exercises."""

    __tablename__ = "exercise_library"

    __table_args__ = (
        CheckConstraint(
            "category IN ('strength', 'cardio')",
            name="ck_exercise_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    muscle_group: Mapped[str] = mapped_column(
        String(40), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(250), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )

    workout_entries: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="exercise"
    )


class WorkoutExercise(Base):
    """One record per exercise performed on a particular date."""

    __tablename__ = "workout_exercises"

    __table_args__ = (
        UniqueConstraint(
            "daily_log_id", "exercise_id",
            name="uq_workout_exercise_per_day",
        ),
        CheckConstraint(
            "sets IS NULL OR sets >= 1", name="ck_workout_sets_positive"
        ),
        CheckConstraint(
            "reps IS NULL OR reps >= 1", name="ck_workout_reps_positive"
        ),
        CheckConstraint(
            "weight_kg IS NULL OR weight_kg >= 0",
            name="ck_workout_weight_nonnegative",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_workout_duration_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(
        ForeignKey("daily_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise_library.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    sets: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    daily_log: Mapped[DailyLog] = relationship(
        back_populates="workout_exercises"
    )
    exercise: Mapped[ExerciseLibrary] = relationship(
        back_populates="workout_entries"
    )


class CalorieEntry(Base):
    """A single calorie addition or subtraction."""

    __tablename__ = "calorie_entries"

    __table_args__ = (
        CheckConstraint("delta_kcal != 0", name="ck_calorie_delta_nonzero"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_log_id: Mapped[int] = mapped_column(
        ForeignKey("daily_logs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        String(160), nullable=False
    )
    delta_kcal: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    daily_log: Mapped[DailyLog] = relationship(
        back_populates="calorie_entries"
    )


class AppNote(Base):
    """One continuous note belonging to the profile."""

    __tablename__ = "app_notes"

    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"),
        primary_key=True,
        default=1,
        server_default="1",
    )
    content: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    profile: Mapped[Profile] = relationship(back_populates="note")
