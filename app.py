import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

# Import models so SQLAlchemy registers all table definitions.
from fittrackr import models as _models  # noqa: F401
from fittrackr.calculations import (
    calculate_bmi,
    calculate_maintenance_calories,
)
from fittrackr.database import APP_ENV, Base, engine, get_session
from fittrackr.services.profile import (
    create_profile,
    get_latest_weight,
    get_profile,
    update_profile,
)


st.set_page_config(
    page_title="FitTrackr",
    page_icon="💪",
    layout="centered",
)

# Ensure the tables exist before accessing profile data.
Base.metadata.create_all(bind=engine)


ACTIVITY_LEVELS = [
    "Sedentary",
    "Lightly active",
    "Moderately active",
    "Very active",
    "Extra active",
]


def load_current_profile():
    """Fetch the saved profile and its latest weight measurement."""
    with get_session() as session:
        profile = get_profile(session)
        latest_weight = get_latest_weight(session)

        return profile, latest_weight


# Environment indicator and safety warning.
with st.sidebar:
    st.header("FitTrackr")
    st.caption("Your personal fitness tracker")

    if APP_ENV == "test":
        st.warning(
            "TEST MODE\n\n"
            "Use fictional details while testing. "
            "Your personal database is separate."
        )
    else:
        st.info("PERSONAL MODE — Changes affect your personal database.")

    st.divider()
    st.caption("More features will be added as development continues.")


st.title("💪 FitTrackr")
st.caption("Build consistency. Track progress.")

flash_message = st.session_state.pop("profile_flash", None)
if flash_message:
    st.success(flash_message)

profile, latest_weight = load_current_profile()


# Display current profile metrics when a profile already exists.
if profile is not None:
    st.subheader(f"Welcome back, {profile.name}!")

    if latest_weight is not None:
        bmi = calculate_bmi(
            weight_kg=latest_weight.weight_kg,
            height_cm=profile.height_cm,
        )

        maintenance_calories = calculate_maintenance_calories(
            age=profile.age,
            gender=profile.gender,
            height_cm=profile.height_cm,
            weight_kg=latest_weight.weight_kg,
            activity_level=profile.activity_level,
        )

        weight_col, bmi_col, calories_col = st.columns(3)

        weight_col.metric(
            "Current weight",
            f"{latest_weight.weight_kg:.1f} kg",
        )
        bmi_col.metric("Current BMI", f"{bmi:.1f}")
        calories_col.metric(
            "Maintenance estimate",
            f"{maintenance_calories:,} kcal/day",
        )

        st.caption(
            f"Latest weight measurement: {latest_weight.measured_on:%d %b %Y}"
        )
        st.caption(
            "Calorie needs are estimates, not exact measurements."
        )

    st.divider()
    st.subheader("Edit profile")
    st.write("Update your details whenever they change.")
else:
    st.subheader("Set up your profile")
    st.write(
        "Enter your details below. Your profile will be saved "
        "so it is available when you reopen FitTrackr."
    )


# Prepare existing values for the form.
current_name = profile.name if profile else ""
current_age = profile.age if profile else None
current_gender = profile.gender if profile else "Select gender"
current_height = profile.height_cm if profile else None
current_weight = (
    latest_weight.weight_kg
    if latest_weight is not None
    else None
)

current_activity = (
    profile.activity_level.replace("_", " ").lower()
    if profile is not None
    else "select activity level"
)

gender_options = ["Select gender", "Male", "Female"]
activity_options = ["Select activity level", *ACTIVITY_LEVELS]

gender_index = (
    gender_options.index(current_gender)
    if current_gender in gender_options
    else 0
)

activity_index = next(
    (
        index
        for index, option in enumerate(activity_options)
        if option.lower() == current_activity
    ),
    0,
)


with st.form("profile_form"):
    name = st.text_input(
        "Name",
        value=current_name,
        placeholder="Enter your name",
        required=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        age = st.number_input(
            "Age (years)",
            min_value=1,
            max_value=120,
            value=current_age,
            step=1,
            placeholder="Enter age",
            required=True,
        )

    with col2:
        gender = st.selectbox(
            "Gender",
            options=gender_options,
            index=gender_index,
            help=(
                "The Mifflin–St Jeor calorie equation uses "
                "male/female coefficients. This selection is "
                "used for that estimate."
            ),
        )

    col3, col4 = st.columns(2)

    with col3:
        height_cm = st.number_input(
            "Height (cm)",
            min_value=50.0,
            max_value=250.0,
            value=current_height,
            step=0.5,
            format="%.1f",
            placeholder="Enter height",
            required=True,
        )

    with col4:
        weight_kg = st.number_input(
            "Current weight (kg)",
            min_value=1.0,
            max_value=500.0,
            value=current_weight,
            step=0.1,
            format="%.1f",
            placeholder="Enter weight",
            required=True,
            help=(
                "Your initial weight becomes your first history entry. "
                "Changing this value later records a new measurement "
                "instead of overwriting the existing history."
            ),
        )

    activity_level = st.selectbox(
        "Activity level",
        options=activity_options,
        index=activity_index,
        help=(
            "Choose the level that best represents your usual activity. "
            "This affects your estimated maintenance calories."
        ),
    )

    submitted = st.form_submit_button(
        "Create profile" if profile is None else "Save changes",
        type="primary",
        width="stretch",
    )


if submitted:
    if not name.strip():
        st.error("Please enter your name.")
    elif gender not in {"Male", "Female"}:
        st.error("Please select a gender for the calorie estimate.")
    elif activity_level == "Select activity level":
        st.error("Please select your activity level.")
    elif age is None or height_cm is None or weight_kg is None:
        st.error("Please complete all required numerical fields.")
    else:
        try:
            with get_session() as session:
                if get_profile(session) is None:
                    create_profile(
                        session,
                        name=name,
                        age=age,
                        gender=gender,
                        height_cm=height_cm,
                        weight_kg=weight_kg,
                        activity_level=activity_level,
                    )
                    success_message = "Profile created successfully!"
                else:
                    update_profile(
                        session,
                        name=name,
                        age=age,
                        gender=gender,
                        height_cm=height_cm,
                        weight_kg=weight_kg,
                        activity_level=activity_level,
                    )
                    success_message = "Profile updated successfully!"

        except ValueError as exc:
            st.error(str(exc))
        except SQLAlchemyError as exc:
            print(f"FitTrackr database error: {exc}")
            st.error(
                "Could not save the profile because of a database error. "
                "Check the terminal for details."
            )
        else:
            st.session_state["profile_flash"] = success_message
            st.rerun()
