
"""Seed FitTrackr's built-in exercise library."""

from sqlalchemy import select

from fittrackr.database import get_session
from fittrackr.models import ExerciseLibrary


BUILTIN_EXERCISES = [
    # Chest
    ("Barbell Bench Press", "Chest", "strength"),
    ("Dumbbell Bench Press", "Chest", "strength"),
    ("Incline Barbell Bench Press", "Chest", "strength"),
    ("Incline Dumbbell Press", "Chest", "strength"),
    ("Machine Chest Press", "Chest", "strength"),
    ("Pec Deck Fly", "Chest", "strength"),
    ("High to Low Cable Crossover(lower chest)", "Chest", "strength"),
    ("Low to High Cable Crossover(upper chest)", "Chest", "strength"),
    ("Push-Up", "Chest", "strength"),
    ("Dips", "Chest", "strength"),

    # Back
    ("Lat Pulldown - wide grip", "Back", "strength"),
    ("Lat Pulldown - close grip", "Back", "strength"),
    ("Pull-Up", "Back", "strength"),
    ("Seated Cable Row", "Back", "strength"),
    ("Barbell Bent-Over Row", "Back", "strength"),
    ("One-Arm Dumbbell Row", "Back", "strength"),
    ("Chest-Supported Row", "Back", "strength"),
    ("Straight-Arm Pulldown", "Back", "strength"),

    # Shoulders
    ("Overhead Press", "Shoulders", "strength"),
    ("Dumbbell Shoulder Press", "Shoulders", "strength"),
    ("Dumbbell Lateral Raise", "Shoulders", "strength"),
    ("Dumbbell Front Raise", "Shoulders", "strength"),
    ("Reverse Pec Deck", "Shoulders", "strength"),
    ("Face Pull", "Shoulders", "strength"),
    ("Shrugs", "Shoulders", "strength"),

    # Biceps
    ("Barbell Curl", "Biceps", "strength"),
    ("Dumbbell Curl", "Biceps", "strength"),
    ("Hammer Curl", "Biceps", "strength"),
    ("Bayesian cable curl", "Biceps", "strength"),
    ("Preacher Curl", "Biceps", "strength"),
    ("Incline Dumbbell Curl", "Biceps", "strength"),

    # Triceps
    ("Cable Triceps Pushdown", "Triceps", "strength"),
    ("Overhead Triceps Extension", "Triceps", "strength"),
    ("Skull Crusher", "Triceps", "strength"),
    ("Close-Grip Bench Press", "Triceps", "strength"),

    # Forearms
    ("Wrist Curl", "Forearms", "strength"),
    ("Reverse Wrist Curl", "Forearms", "strength"),

    # Legs
    ("Barbell Squat", "Legs", "strength"),
    ("Squats", "Legs", "strength"),
    ("Goblet Squats", "Legs", "strength"),
    ("Leg Press", "Legs", "strength"),
    ("Leg Extension", "Legs", "strength"),
    ("Seated Leg Curl", "Legs", "strength"),
    ("Lying Leg Curl", "Legs", "strength"),
    ("Romanian Deadlift", "Legs", "strength"),
    ("Dumbbell Walking Lunge", "Legs", "strength"),
    ("Standing Calf Raise", "Legs", "strength"),
    ("Hip Thrust", "Glutes", "strength"),
    ("Glute Bridge", "Glutes", "strength"),

    # Core
    ("Plank", "Core", "strength"),
    ("Crunch", "Core", "strength"),
    ("Cable Crunch", "Core", "strength"),
    ("Hanging Leg Raise", "Core", "strength"),

    # Full body
    ("Conventional Deadlift", "Full Body", "strength"),
    ("Kettlebell Swing", "Full Body", "strength"),

    # Cardio
    ("Treadmill Walking", "Cardio", "cardio"),
    ("Treadmill Running", "Cardio", "cardio"),
    ("Stationary Cycling", "Cardio", "cardio"),
    ("Outdoor Cycling", "Cardio", "cardio"),
    ("Elliptical Trainer", "Cardio", "cardio"),
    ("Rowing Machine", "Cardio", "cardio"),
    ("Stair Climber", "Cardio", "cardio"),
    ("Jump Rope", "Cardio", "cardio"),
]


def seed_exercises() -> None:
    """Insert missing built-in exercises without duplicating records."""
    inserted = 0
    skipped = 0

    with get_session() as session:
        existing_names = set(
            session.scalars(select(ExerciseLibrary.name)).all()
        )

        for name, muscle_group, category in BUILTIN_EXERCISES:
            if name in existing_names:
                skipped += 1
                continue

            exercise = ExerciseLibrary(
                name=name,
                muscle_group=muscle_group,
                category=category,
                is_builtin=True,
            )
            session.add(exercise)
            existing_names.add(name)
            inserted += 1

        session.commit()

    print("Exercise library seeding complete.")
    print(f"New exercises added: {inserted}")
    print(f"Existing exercises skipped: {skipped}")
    print(f"Built-in exercises defined: {len(BUILTIN_EXERCISES)}")


if __name__ == "__main__":
    seed_exercises()
