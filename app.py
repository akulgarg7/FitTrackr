import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

# Import models so SQLAlchemy registers all tables.
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
    layout="wide",
)

# Create any missing tables. This does not delete existing records.
Base.metadata.create_all(bind=engine)


ACTIVITY_LEVELS = [
    "Sedentary",
    "Lightly active",
    "Moderately active",
    "Very active",
    "Extra active",
]

GENDER_OPTIONS = ["Select gender", "Male", "Female"]
ACTIVITY_OPTIONS = ["Select activity level", *ACTIVITY_LEVELS]


def load_profile_data():
    """Load the profile and latest weight measurement."""
    with get_session() as session:
        profile = get_profile(session)
        latest_weight = get_latest_weight(session)
        return profile, latest_weight


def render_profile_form(*, setup: bool) -> None:
    """Render either first-time profile setup or profile editing."""
    profile, latest_weight = load_profile_data()

    prefix = "setup" if setup else "settings"

    if setup:
        st.title("Welcome to FitTrackr")
        st.write(
            "Let's set up your profile. Your details will be saved "
            "so you won't need to enter them each time you open the app."
        )
    else:
        st.title("Profile Settings")
        st.write(
            "Update your personal details here. Your current BMI and "
            "maintenance-calorie estimate will update accordingly."
        )

    current_name = profile.name if profile else ""
    current_age = profile.age if profile else None
    current_gender = profile.gender if profile else GENDER_OPTIONS[0]
    current_height = profile.height_cm if profile else None
    current_weight = (
        latest_weight.weight_kg if latest_weight is not None else None
    )

    current_activity = (
        profile.activity_level.replace("_", " ").lower()
        if profile is not None
        else ""
    )

    gender_index = (
        GENDER_OPTIONS.index(current_gender)
        if current_gender in GENDER_OPTIONS
        else 0
    )

    activity_index = next(
        (
            index
            for index, option in enumerate(ACTIVITY_OPTIONS)
            if option.lower() == current_activity
        ),
        0,
    )

    with st.form(f"profile_form_{prefix}"):
        name = st.text_input(
            "Name",
            value=current_name,
            placeholder="Enter your name",
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
            )

        with col2:
            gender = st.selectbox(
                "Gender",
                options=GENDER_OPTIONS,
                index=gender_index,
                help=(
                    "The selected gender coefficient is used by the "
                    "Mifflin–St Jeor calorie-estimation formula."
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
                help=(
                    "Your initial weight is saved as your first "
                    "measurement. Changing it later preserves history."
                ),
            )

        activity_level = st.selectbox(
            "Activity level",
            options=ACTIVITY_OPTIONS,
            index=activity_index,
        )

        submitted = st.form_submit_button(
            "Save Details" if setup else "Save Changes",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    if not name.strip():
        st.error("Please enter your name.")
        return

    if gender not in {"Male", "Female"}:
        st.error("Please select a gender.")
        return

    if activity_level == "Select activity level":
        st.error("Please select your activity level.")
        return

    if age is None or height_cm is None or weight_kg is None:
        st.error("Please complete all numerical fields.")
        return

    try:
        with get_session() as session:
            existing_profile = get_profile(session)

            if setup:
                if existing_profile is not None:
                    st.error(
                        "A profile already exists. "
                        "Please open the dashboard."
                    )
                    return

                create_profile(
                    session,
                    name=name,
                    age=age,
                    gender=gender,
                    height_cm=height_cm,
                    weight_kg=weight_kg,
                    activity_level=activity_level,
                )
                message = "Profile saved successfully!"

            else:
                if existing_profile is None:
                    st.error(
                        "No profile exists yet. Please complete setup."
                    )
                    return

                update_profile(
                    session,
                    name=name,
                    age=age,
                    gender=gender,
                    height_cm=height_cm,
                    weight_kg=weight_kg,
                    activity_level=activity_level,
                )
                message = "Profile updated successfully!"

    except ValueError as exc:
        st.error(str(exc))
        return

    except SQLAlchemyError as exc:
        print(f"FitTrackr database error: {exc}")
        st.error(
            "Could not save your details because of a database error. "
            "Check the terminal for details."
        )
        return

    st.session_state["profile_flash"] = message

    if setup:
        # First-time setup: rerun so the Dashboard becomes available.
        st.rerun()
    else:
        # Profile Settings: navigate directly to the Dashboard.
        st.switch_page(dashboard_nav_page)


def profile_setup_page() -> None:
    """Show only the first-time profile setup form."""
    render_profile_form(setup=True)


def profile_settings_page() -> None:
    """Show the form for editing an existing profile."""
    render_profile_form(setup=False)


def dashboard_page() -> None:
    """Show the current profile metrics."""
    profile, latest_weight = load_profile_data()

    if profile is None:
        st.warning("Please complete your profile setup first.")
        st.rerun()

    st.title("FitTrackr")
    st.subheader(f"Welcome back, {profile.name}!")
    st.caption("Your current fitness overview")

    if latest_weight is None:
        st.warning("No weight measurement is available yet.")
        return

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
        "Current Weight",
        f"{latest_weight.weight_kg:.1f} kg",
    )
    bmi_col.metric("Current BMI", f"{bmi:.1f}")
    calories_col.metric(
        "Maintenance Estimate",
        f"{maintenance_calories:,} kcal/day",
    )

    st.caption(
        f"Latest weight measurement: "
        f"{latest_weight.measured_on:%d %b %Y}"
    )
    st.caption(
        "Maintenance calories are an estimate. "
        "More tracking features will be added as development continues."
    )


# Decide which screens are available based on saved profile data.
with get_session() as session:
    profile_exists = get_profile(session) is not None


# Define page objects once so we can navigate to them programmatically.
dashboard_nav_page = st.Page(
    dashboard_page,
    title="Dashboard",
    icon="🏠",
    url_path="dashboard",
    default=True,
)

profile_settings_nav_page = st.Page(
    profile_settings_page,
    title="Profile Settings",
    icon="👤",
    url_path="profile-settings",
)

profile_setup_nav_page = st.Page(
    profile_setup_page,
    title="Profile Setup",
    icon="💪",
    url_path="setup",
    default=True,
)

# Only make the appropriate pages available for the current state.
if profile_exists:
    pages = [
        dashboard_nav_page,
        profile_settings_nav_page,
    ]
else:
    pages = [profile_setup_nav_page]


# Hide navigation entirely during first-time setup.
page = st.navigation(
    pages,
    position="sidebar" if profile_exists else "hidden",
)

# Show test/personal environment details only after setup.
if profile_exists:
    with st.sidebar:
        st.title("FitTrackr")

        if APP_ENV == "test":
            st.warning(
                "TEST MODE\n\n"
                "Changes are saved to the test database."
            )
        else:
            st.info(
                "PERSONAL MODE\n\n"
                "Changes affect your personal database."
            )

# Show the message following a successful save.
flash_message = st.session_state.pop("profile_flash", None)
if flash_message:
    st.success(flash_message)

page.run()
