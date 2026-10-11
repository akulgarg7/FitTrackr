import math


ACTIVITY_FACTORS = {
    "sedentary": 1.20,
    "lightly active": 1.375,
    "moderately active": 1.55,
    "heavily active": 1.725,
    "athlete level": 1.90,
}


def _validate_positive(value: float, field_name: str) -> None:
    """Reject non-positive or non-finite numeric inputs."""
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")


def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Calculate BMI from weight in kilograms and height in centimetres."""
    _validate_positive(weight_kg, "Weight")
    _validate_positive(height_cm, "Height")

    height_m = height_cm / 100
    return weight_kg / (height_m**2)


def calculate_bmr(
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
) -> float:
    """Estimate resting energy expenditure using Mifflin-St Jeor."""
    if isinstance(age, bool) or not isinstance(age, int) or age <= 0:
        raise ValueError("Age must be a positive integer.")

    _validate_positive(height_cm, "Height")
    _validate_positive(weight_kg, "Weight")

    normalized_gender = gender.strip().lower()

    if normalized_gender == "male":
        gender_constant = 5
    elif normalized_gender == "female":
        gender_constant = -161
    else:
        raise ValueError(
            "Gender must be 'Male' or 'Female' for this formula."
        )

    return (
        (10 * weight_kg)
        + (6.25 * height_cm)
        - (5 * age)
        + gender_constant
    )


def calculate_maintenance_calories(
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> int:
    """Estimate daily maintenance calories using an activity multiplier."""
    bmr = calculate_bmr(
        age=age,
        gender=gender,
        height_cm=height_cm,
        weight_kg=weight_kg,
    )

    normalized_activity = " ".join(
        activity_level.strip().lower().replace("_", " ").split()
    )

    if normalized_activity not in ACTIVITY_FACTORS:
        raise ValueError(
            f"Unknown activity level: {activity_level!r}"
        )

    estimated_calories = bmr * ACTIVITY_FACTORS[normalized_activity]
    return round(estimated_calories)
