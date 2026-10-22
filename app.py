import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from datetime import date

import pandas as pd

from fittrackr.services.weight import (
    add_weight_entry,
    get_weight_history,
    update_weight_entry,
)
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


@st.dialog("Log Weight")
def log_weight_dialog(
    current_weight: float | None = None,
) -> None:
    """Display a dialog for recording a weight measurement."""

    st.write("Record your weight and the date you measured it.")

    with st.form("log_weight_form"):
        weight_kg = st.number_input(
            "Weight (kg)",
            min_value=1.0,
            max_value=500.0,
            value=current_weight,
            step=0.1,
            format="%.1f",
        )

        measured_on = st.date_input(
            "Measurement date",
            value=date.today(),
            max_value=date.today(),
        )

        submitted = st.form_submit_button(
            "Save Weight",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        with get_session() as session:
            add_weight_entry(
                session,
                weight_kg=weight_kg,
                measured_on=measured_on,
            )

    except ValueError as exc:
        st.error(str(exc))

    except SQLAlchemyError as exc:
        print(f"FitTrackr database error: {exc}")
        st.error("Unable to save this measurement. Check the terminal.")

    else:
        st.session_state["weight_flash"] = (
            "Weight measurement saved successfully!"
        )
        st.rerun()


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

    if st.button("＋ Log Weight", type="primary"):
        log_weight_dialog(
            current_weight=(
                latest_weight.weight_kg
                if latest_weight is not None
                else None
            )
        )

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

    with weight_col:
        st.metric(
            "Current Weight",
            f"{latest_weight.weight_kg:.1f} kg",
        )

        # A separate button provides navigation from the weight card.
        if st.button(
            "View Weight History",
            key="open_weight_history",
            width="stretch",
        ):
            st.switch_page(weight_history_nav_page)

    with bmi_col:
        st.metric("Current BMI", f"{bmi:.1f}")

    with calories_col:
        st.metric(
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



def weight_history_page() -> None:
    """Display weight history, a graph, and historical editing."""

    st.title("Weight History")
    st.caption("Track how your weight changes over time.")

    with get_session() as session:
        history = get_weight_history(session)

    if not history:
        st.info("No weight measurements have been recorded yet.")
        return

    # Sort chronologically for the graph.
    chronological = sorted(
        history,
        key=lambda entry: (entry.measured_on, entry.id),
    )

    chart_data = pd.DataFrame(
        {
            "Date": [entry.measured_on for entry in chronological],
            "Weight (kg)": [
                entry.weight_kg for entry in chronological
            ],
        }
    )

    st.subheader("Weight Progress")
    st.line_chart(
        chart_data,
        x="Date",
        y="Weight (kg)",
        x_label="Measurement date",
        y_label="Weight (kg)",
        width="stretch",
    )

    st.subheader("Recorded Measurements")

    newest_first = sorted(
        history,
        key=lambda entry: (entry.measured_on, entry.id),
        reverse=True,
    )

    records_df = pd.DataFrame(
        [
            {
                "Date": entry.measured_on.strftime("%d %b %Y"),
                "Weight (kg)": round(entry.weight_kg, 1),
            }
            for entry in newest_first
        ]
    )

    st.dataframe(
        records_df,
        width="stretch",
        hide_index=True,
    )

    st.divider()
    st.subheader("Correct a Measurement")
    st.caption(
        "Editing a record changes that measurement rather than adding "
        "another entry."
    )

    entries_by_id = {entry.id: entry for entry in newest_first}

    selected_id = st.selectbox(
        "Select a measurement",
        options=list(entries_by_id.keys()),
        format_func=lambda entry_id: (
            f"{entries_by_id[entry_id].measured_on:%d %b %Y}"
            f" — {entries_by_id[entry_id].weight_kg:.1f} kg"
        ),
    )

    selected_entry = entries_by_id[selected_id]

    with st.form("edit_weight_entry_form"):
        edited_weight = st.number_input(
            "Correct weight (kg)",
            min_value=1.0,
            max_value=500.0,
            value=float(selected_entry.weight_kg),
            step=0.1,
            format="%.1f",
            key=f"edit_weight_{selected_id}",
        )

        edited_date = st.date_input(
            "Correct measurement date",
            value=selected_entry.measured_on,
            max_value=date.today(),
            key=f"edit_weight_date_{selected_id}",
        )

        submitted = st.form_submit_button(
            "Save Correction",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    try:
        with get_session() as session:
            update_weight_entry(
                session,
                entry_id=selected_id,
                weight_kg=edited_weight,
                measured_on=edited_date,
            )

    except ValueError as exc:
        st.error(str(exc))

    except SQLAlchemyError as exc:
        print(f"FitTrackr database error: {exc}")
        st.error("Unable to update the measurement. Check the terminal.")

    else:
        st.session_state["weight_flash"] = (
            "Weight measurement updated successfully!"
        )
        st.rerun()


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

weight_history_nav_page = st.Page(
    weight_history_page,
    title="Weight History",
    icon="📈",
    url_path="weight-history",
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
        weight_history_nav_page,
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

if flash_message is None:
    flash_message = st.session_state.pop("weight_flash", None)

if flash_message:
    st.success(flash_message)
    
page.run()
