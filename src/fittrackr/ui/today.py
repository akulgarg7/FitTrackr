
"""Today page for FitTrackr daily tracking."""

from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

from fittrackr.database import get_session
from fittrackr.services.profile import get_profile
from fittrackr.services.daily_logs import (
    WORKOUT_TYPES,
    get_daily_log,
    save_steps,
    save_workout,
)
from fittrackr.services.exercises import (
    add_custom_exercise,
    add_workout_exercise,
    delete_workout_exercise,
    get_exercises,
    get_workout_exercises,
    update_workout_exercise,
)
from fittrackr.services.calories import (
    add_calorie_entry,
    delete_calorie_entry,
    get_calorie_entries,
    get_daily_calorie_total,
    update_calorie_entry,
)


def _set_flash_and_rerun(key: str, message: str) -> None:
    """Show a confirmation after refreshing the page."""
    st.session_state[key] = message
    st.rerun()


def _show_save_error(exc: Exception) -> None:
    """Display validation errors and log database errors."""
    if isinstance(exc, ValueError):
        st.error(str(exc))
    else:
        print(f"FitTrackr database error: {exc}")
        st.error("The change could not be saved. Check the terminal.")


def _load_day_data(log_date: date) -> dict:
    """Load the selected day's log, exercises, and calorie entries."""
    with get_session() as session:
        daily_log = get_daily_log(session, log_date)

        log_data = None
        if daily_log is not None:
            log_data = {
                "id": daily_log.id,
                "steps": daily_log.steps,
                "did_workout": daily_log.did_workout,
                "workout_type": daily_log.workout_type,
            }

        library = [
            {
                "id": item.id,
                "name": item.name,
                "muscle_group": item.muscle_group,
                "category": item.category,
                "is_builtin": item.is_builtin,
            }
            for item in get_exercises(session)
        ]

        workout_entries = []
        for entry in get_workout_exercises(
            session, log_date=log_date
        ):
            # Access relationships while the session is still open.
            workout_entries.append(
                {
                    "id": entry.id,
                    "exercise_id": entry.exercise_id,
                    "name": entry.exercise.name,
                    "muscle_group": entry.exercise.muscle_group,
                    "category": entry.exercise.category,
                    "sets": entry.sets,
                    "reps": entry.reps,
                    "weight_kg": entry.weight_kg,
                    "duration_minutes": entry.duration_minutes,
                }
            )

        calorie_entries = [
            {
                "id": entry.id,
                "description": entry.description,
                "delta_kcal": entry.delta_kcal,
            }
            for entry in get_calorie_entries(
                session, log_date=log_date
            )
        ]

        calorie_total = get_daily_calorie_total(
            session, log_date=log_date
        )

    return {
        "daily_log": log_data,
        "library": library,
        "workout_entries": workout_entries,
        "calorie_entries": calorie_entries,
        "calorie_total": calorie_total,
    }


def _render_steps_section(log_date: date, log_data: dict | None) -> None:
    """Render the independent step-count editor."""
    st.header("Steps")
    st.caption(
        "Enter your total steps for the selected date. "
        "Leave this section untouched if you have not recorded steps yet."
    )

    date_key = log_date.isoformat()
    saved_steps = log_data["steps"] if log_data else None

    with st.form(f"steps_form_{date_key}"):
        steps = st.number_input(
            "Total steps",
            min_value=0,
            max_value=200_000,
            value=int(saved_steps) if saved_steps is not None else 0,
            step=100,
            key=f"steps_value_{date_key}",
        )

        clear_steps = st.checkbox(
            "Clear the saved step count (mark as not recorded)",
            value=False,
            key=f"clear_steps_{date_key}",
        )

        submitted = st.form_submit_button(
            "Save Steps",
            type="primary",
            width="stretch",
        )

    if submitted:
        try:
            with get_session() as session:
                save_steps(
                    session,
                    log_date=log_date,
                    steps=None if clear_steps else int(steps),
                )
        except (ValueError, SQLAlchemyError) as exc:
            _show_save_error(exc)
        else:
            _set_flash_and_rerun(
                "daily_flash", "Step count saved successfully."
            )


def _render_workout_section(
    log_date: date,
    data: dict,
) -> None:
    """Render workout status and type controls."""
    st.header("Workout")

    log_data = data["daily_log"]
    entries = data["workout_entries"]
    date_key = log_date.isoformat()

    if log_data is None or log_data["did_workout"] is None:
        saved_status = "Not recorded"
    elif log_data["did_workout"]:
        saved_status = "Yes"
    else:
        saved_status = "No"

    status_options = ["Not recorded", "Yes", "No"]

    status = st.selectbox(
        "Did you work out on this date?",
        options=status_options,
        index=status_options.index(saved_status),
        key=f"workout_status_{date_key}",
    )

    workout_type = None

    if status == "Yes":
        saved_type = (
            log_data["workout_type"] if log_data else None
        )
        type_index = (
            WORKOUT_TYPES.index(saved_type)
            if saved_type in WORKOUT_TYPES
            else 0
        )

        workout_type = st.selectbox(
            "Workout type",
            options=list(WORKOUT_TYPES),
            index=type_index,
            key=f"workout_type_{date_key}",
            help=(
                "This labels the day's workout. It does not restrict "
                "which exercises you can select below."
            ),
        )

    confirm_clear = False

    if status != "Yes" and entries:
        st.warning(
            "Changing this day to No or Not recorded will remove its "
            "logged exercises. Confirm below to continue."
        )
        confirm_clear = st.checkbox(
            "I understand that the logged exercises will be removed.",
            key=f"confirm_clear_exercises_{date_key}",
        )

    if st.button(
        "Save Workout Status",
        type="primary",
        key=f"save_workout_{date_key}",
    ):
        if status != "Yes" and entries and not confirm_clear:
            st.error(
                "Confirm the removal of logged exercises before saving."
            )
            return

        did_workout = {
            "Not recorded": None,
            "Yes": True,
            "No": False,
        }[status]

        try:
            with get_session() as session:
                save_workout(
                    session,
                    log_date=log_date,
                    did_workout=did_workout,
                    workout_type=workout_type,
                )
        except (ValueError, SQLAlchemyError) as exc:
            _show_save_error(exc)
        else:
            _set_flash_and_rerun(
                "daily_flash", "Workout status saved successfully."
            )


def _render_custom_exercise_form() -> None:
    """Allow an exercise to be added permanently to the library."""
    with st.expander("Add a custom exercise"):
        with st.form("custom_exercise_form"):
            name = st.text_input("Exercise name")
            muscle_group = st.text_input(
                "Muscle group",
                placeholder="e.g. Chest, Back, Glutes, Cardio",
            )
            category = st.selectbox(
                "Exercise category",
                options=["strength", "cardio"],
                format_func=lambda value: value.title(),
            )
            description = st.text_input(
                "Description (optional)"
            )

            submitted = st.form_submit_button(
                "Add to Exercise Library"
            )

        if submitted:
            try:
                with get_session() as session:
                    add_custom_exercise(
                        session,
                        name=name,
                        muscle_group=muscle_group,
                        category=category,
                        description=description or None,
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "exercise_flash",
                    "Custom exercise added to the library.",
                )


def _render_exercise_fields(
    exercise: dict,
    date_key: str,
    *,
    existing_entry: dict | None = None,
) -> dict:
    """Render fields appropriate to the selected exercise category."""
    prefix = (
        f"edit_exercise_{existing_entry['id']}"
        if existing_entry is not None
        else f"new_exercise_{date_key}_{exercise['id']}"
    )

    if exercise["category"] == "strength":
        default_sets = (
            existing_entry["sets"]
            if existing_entry and existing_entry["sets"] is not None
            else 3
        )
        default_reps = (
            existing_entry["reps"]
            if existing_entry and existing_entry["reps"] is not None
            else 10
        )
        default_weight = (
            existing_entry["weight_kg"]
            if existing_entry
            else None
        )

        sets = st.number_input(
            "Sets",
            min_value=1,
            max_value=100,
            value=int(default_sets),
            key=f"{prefix}_sets",
        )
        reps = st.number_input(
            "Reps per set",
            min_value=1,
            max_value=1000,
            value=int(default_reps),
            key=f"{prefix}_reps",
        )

        no_external_weight = st.checkbox(
            "Bodyweight / do not record external weight",
            value=default_weight is None,
            key=f"{prefix}_no_weight",
        )
        weight = st.number_input(
            "Weight (kg)",
            min_value=0.0,
            max_value=1000.0,
            value=float(default_weight or 0.0),
            step=0.5,
            disabled=no_external_weight,
            key=f"{prefix}_weight",
        )

        return {
            "sets": int(sets),
            "reps": int(reps),
            "weight_kg": None if no_external_weight else float(weight),
            "duration_minutes": None,
        }

    default_duration = (
        existing_entry["duration_minutes"]
        if existing_entry
        and existing_entry["duration_minutes"] is not None
        else 20
    )

    duration = st.number_input(
        "Duration (minutes)",
        min_value=1,
        max_value=1440,
        value=int(default_duration),
        key=f"{prefix}_duration",
    )

    return {
        "sets": None,
        "reps": None,
        "weight_kg": None,
        "duration_minutes": int(duration),
    }


def _render_exercise_section(log_date: date, data: dict) -> None:
    """Render exercise selection, logging, editing, and deletion."""
    st.header("Exercises")
    date_key = log_date.isoformat()
    log_data = data["daily_log"]

    _render_custom_exercise_form()

    if log_data is None or log_data["did_workout"] is not True:
        st.info(
            "Save the workout status as Yes before logging exercises."
        )
        return

    library = data["library"]
    by_id = {item["id"]: item for item in library}

    st.caption(
        "You can choose any muscle group here, regardless of the "
        "workout type selected above."
    )

    muscle_groups = sorted(
        {item["muscle_group"] for item in library}
    )
    group_options = ["All muscle groups", *muscle_groups]

    selected_group = st.selectbox(
        "Filter by muscle group",
        options=group_options,
        key=f"exercise_group_{date_key}",
    )

    if selected_group == "All muscle groups":
        filtered = library
    else:
        filtered = [
            item
            for item in library
            if item["muscle_group"] == selected_group
        ]

    if filtered:
        exercise_ids = [item["id"] for item in filtered]

        selected_id = st.selectbox(
            "Exercise",
            options=exercise_ids,
            format_func=lambda exercise_id: (
                f"{by_id[exercise_id]['muscle_group']} — "
                f"{by_id[exercise_id]['name']} "
                f"({by_id[exercise_id]['category']})"
            ),
            key=f"exercise_choice_{date_key}_{selected_group}",
        )

        selected_exercise = by_id[selected_id]

        st.caption(
            f"Selected category: **{selected_exercise['category'].title()}**"
        )

        with st.form(
            f"add_exercise_form_{date_key}_{selected_id}"
        ):
            fields = _render_exercise_fields(
                selected_exercise, date_key
            )
            submitted = st.form_submit_button(
                "Add Exercise",
                type="primary",
                width="stretch",
            )

        if submitted:
            try:
                with get_session() as session:
                    add_workout_exercise(
                        session,
                        log_date=log_date,
                        exercise_id=selected_id,
                        **fields,
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "exercise_flash", "Exercise added to the workout."
                )
    else:
        st.info("No exercises are available for this muscle group.")

    entries = data["workout_entries"]

    st.subheader("Logged Exercises")

    if not entries:
        st.caption("No exercises have been logged for this date yet.")
        return

    display_rows = []
    for item in entries:
        if item["category"] == "strength":
            details = (
                f"{item['sets']} sets × {item['reps']} reps; "
                f"{item['weight_kg'] if item['weight_kg'] is not None else 'bodyweight'}"
            )
        else:
            details = f"{item['duration_minutes']} minutes"

        display_rows.append(
            {
                "Exercise": item["name"],
                "Muscle group": item["muscle_group"],
                "Details": details,
            }
        )

    st.dataframe(
        pd.DataFrame(display_rows),
        hide_index=True,
        width="stretch",
    )

    with st.expander("Edit or remove a logged exercise"):
        entry_by_id = {item["id"]: item for item in entries}
        selected_entry_id = st.selectbox(
            "Select exercise entry",
            options=list(entry_by_id),
            format_func=lambda entry_id: (
                f"{entry_by_id[entry_id]['name']} "
                f"({entry_by_id[entry_id]['muscle_group']})"
            ),
            key=f"edit_exercise_selection_{date_key}",
        )
        selected_entry = entry_by_id[selected_entry_id]
        selected_library_exercise = by_id[
            selected_entry["exercise_id"]
        ]

        with st.form(f"edit_exercise_form_{selected_entry_id}"):
            fields = _render_exercise_fields(
                selected_library_exercise,
                date_key,
                existing_entry=selected_entry,
            )
            save_edit = st.form_submit_button(
                "Save Exercise Changes"
            )

        if save_edit:
            try:
                with get_session() as session:
                    update_workout_exercise(
                        session,
                        entry_id=selected_entry_id,
                        **fields,
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "exercise_flash", "Exercise entry updated."
                )

        if st.button(
            "Remove Selected Exercise",
            key=f"delete_exercise_{selected_entry_id}",
        ):
            try:
                with get_session() as session:
                    delete_workout_exercise(
                        session,
                        entry_id=selected_entry_id,
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "exercise_flash", "Exercise removed from the workout."
                )


def _render_calorie_section(log_date: date, data: dict) -> None:
    """Render calorie totals, additions, corrections, and deletion."""
    st.header("Calories")

    total = data["calorie_total"]
    st.metric("Calories consumed", f"{total:,} kcal")
    st.caption(
        "Add food or meal estimates throughout the day. Use a negative "
        "adjustment to correct an overestimate."
    )

    date_key = log_date.isoformat()

    with st.form(f"add_calorie_form_{date_key}"):
        description = st.text_input(
            "Description",
            placeholder="e.g. Breakfast, lunch, snack",
        )
        action = st.selectbox(
            "Adjustment",
            options=["Add calories", "Subtract calories"],
        )
        amount = st.number_input(
            "Calories (kcal)",
            min_value=1,
            max_value=100_000,
            value=300,
            step=50,
        )

        submitted = st.form_submit_button(
            "Add Calorie Entry",
            type="primary",
            width="stretch",
        )

    if submitted:
        delta = int(amount) if action == "Add calories" else -int(amount)

        try:
            with get_session() as session:
                add_calorie_entry(
                    session,
                    log_date=log_date,
                    description=description,
                    delta_kcal=delta,
                )
        except (ValueError, SQLAlchemyError) as exc:
            _show_save_error(exc)
        else:
            _set_flash_and_rerun(
                "calorie_flash", "Calorie entry saved."
            )

    entries = data["calorie_entries"]

    st.subheader("Entries for this date")

    if not entries:
        st.caption("No calorie entries have been recorded for this date.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Description": entry["description"],
                    "Adjustment (kcal)": (
                        f"{entry['delta_kcal']:+,}"
                    ),
                }
                for entry in entries
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    with st.expander("Correct or remove a calorie entry"):
        entry_by_id = {item["id"]: item for item in entries}

        selected_entry_id = st.selectbox(
            "Select calorie entry",
            options=list(entry_by_id),
            format_func=lambda entry_id: (
                f"{entry_by_id[entry_id]['description']} "
                f"({entry_by_id[entry_id]['delta_kcal']:+,} kcal)"
            ),
            key=f"edit_calorie_selection_{date_key}",
        )

        selected_entry = entry_by_id[selected_entry_id]

        with st.form(f"edit_calorie_form_{selected_entry_id}"):
            edited_description = st.text_input(
                "Description",
                value=selected_entry["description"],
                key=f"edit_calorie_description_{selected_entry_id}",
            )
            edited_delta = st.number_input(
                "Signed adjustment (kcal; positive or negative)",
                min_value=-100_000,
                max_value=100_000,
                value=int(selected_entry["delta_kcal"]),
                step=50,
                key=f"edit_calorie_delta_{selected_entry_id}",
            )

            save_edit = st.form_submit_button(
                "Save Calorie Correction"
            )

        if save_edit:
            try:
                with get_session() as session:
                    update_calorie_entry(
                        session,
                        entry_id=selected_entry_id,
                        description=edited_description,
                        delta_kcal=int(edited_delta),
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "calorie_flash", "Calorie entry corrected."
                )

        if st.button(
            "Delete Selected Calorie Entry",
            key=f"delete_calorie_{selected_entry_id}",
        ):
            try:
                with get_session() as session:
                    delete_calorie_entry(
                        session,
                        entry_id=selected_entry_id,
                    )
            except (ValueError, SQLAlchemyError) as exc:
                _show_save_error(exc)
            else:
                _set_flash_and_rerun(
                    "calorie_flash", "Calorie entry deleted."
                )


def today_page() -> None:
    """Render the single-date daily-tracking page."""
    with get_session() as session:
        profile = get_profile(session)

    if profile is None:
        st.error("Please complete profile setup before using Today.")
        return

    st.title("Today")
    st.caption(
        "Log steps, workout activity, exercises, and calories. "
        "Select a previous date to review or correct its records."
    )

    selected_date = st.date_input(
        "Tracking date",
        value=date.today(),
        max_value=date.today(),
        key="daily_tracking_date",
    )

    st.subheader(selected_date.strftime("%A, %d %B %Y"))

    data = _load_day_data(selected_date)

    _render_steps_section(selected_date, data["daily_log"])

    st.divider()
    _render_workout_section(selected_date, data)

    st.divider()
    _render_exercise_section(selected_date, data)

    st.divider()
    _render_calorie_section(selected_date, data)
