import streamlit as st
from database import diagnose_from_symptoms, HeartDiagnosisDB
from pathlib import Path


@st.cache_resource
def init_db_connection(db_file):
    db_file_path = Path(db_file)
    if not db_file_path.exists():
        print(f"Error: Database file not found at {db_file_path}")
        return None
    db = HeartDiagnosisDB(db_file_path)
    return db


#Helper function to determine color based on severity
def get_color_for_severity(severity_value):
    """
    Returns a color string based on the severity value.
    Adjust thresholds as per your actual severity scale.
    """
    if severity_value is None:
        return "grey"  # Default color for unknown or N/A severity
    try:
        severity = int(severity_value)
        if severity >= 7:  # High severity (e.g., 7-10, assuming 10 is max)
            return "red"
        elif severity >= 4:  # Medium severity (e.g., 4-6)
            return "orange"
        elif severity >= 1:  # Low severity (e.g., 1-3)
            return "green"
        else: # For 0 or any unexpected non-positive integers if they can occur
            return "grey" # Treat as unspecified or unknown
    except ValueError:
        return "grey"  # Default for non-integer severity

# --- Streamlit Application ---
st.set_page_config(layout="wide")
st.title("Medical Diagnosis Assistant")  # MODIFIED: Simplified title for example
db_conn = init_db_connection('heart_data_from_json.db')

# Initialize session state
if 'selected_symptoms' not in st.session_state:
    st.session_state.selected_symptoms = []
if 'symptom_options_tuples' not in st.session_state:
    if db_conn:
        st.session_state.symptom_options_tuples = db_conn.get_all_symptoms()  # This provides (id, name, severity)
    else:
        st.session_state.symptom_options_tuples = []
if 'symptom_severities' not in st.session_state:  # NEW: Store severities in a quickly accessible dict
    st.session_state.symptom_severities = {}
    if st.session_state.symptom_options_tuples:
        for _id, name, severity in st.session_state.symptom_options_tuples:
            st.session_state.symptom_severities[name] = severity

# --- Symptom Selection ---
st.sidebar.header("Select Symptoms")


def format_symptom_display(option_tuple_or_str):
    if isinstance(option_tuple_or_str, tuple) and len(option_tuple_or_str) >= 2:
        return option_tuple_or_str[1]
    return str(option_tuple_or_str)


def add_symptom_to_selected_list_from_selector():
    selected_option_tuple = st.session_state.symptom_selector_key
    if isinstance(selected_option_tuple, tuple) and len(selected_option_tuple) >= 2:
        symptom_name_to_add = selected_option_tuple[1]
        if symptom_name_to_add not in st.session_state.selected_symptoms:
            st.session_state.selected_symptoms.append(symptom_name_to_add)
            # Consider if a rerun is needed here for immediate effect if not handled by a main diagnose button


options_for_selectbox = [""]
if st.session_state.symptom_options_tuples and isinstance(st.session_state.symptom_options_tuples, list):
    options_for_selectbox.extend(st.session_state.symptom_options_tuples)

symptom_choice_tuple = st.sidebar.selectbox(
    "Search and select a symptom:",
    options=options_for_selectbox,
    key="symptom_selector_key",
    index=0,
    on_change=add_symptom_to_selected_list_from_selector,
    format_func=format_symptom_display,
    help="Select a symptom. Its name will be added for diagnosis."
)

# --- Display Selected Symptoms ---
if st.session_state.selected_symptoms:
    st.sidebar.subheader("Selected Symptoms (for diagnosis):")
    for symptom_name in list(st.session_state.selected_symptoms):  # Iterate over a copy for safe removal
        col1, col2 = st.sidebar.columns([0.8, 0.2])

        symptom_severity = st.session_state.symptom_severities.get(symptom_name)
        color = get_color_for_severity(symptom_severity)

        display_text = f"<span style='color:{color};'>- {symptom_name}</span>"
        col1.markdown(display_text, unsafe_allow_html=True)

        if col2.button("❌", key=f"remove_db_{symptom_name.replace(' ', '_')}", help=f"Remove {symptom_name}"):
            st.session_state.selected_symptoms.remove(symptom_name)
            st.rerun()

    if st.sidebar.button("Clear All Symptoms", key="clear_all_db"):
        st.session_state.selected_symptoms = []
        st.rerun()

    # NEW: Severity Legend
    st.sidebar.markdown("---")  # Optional separator
    st.sidebar.markdown("##### Severity Legend:")
    legend_html = """
    <ul style="list-style-type: none; padding-left: 0;">
        <li><span style='color:red; font-size: 18px;'>&#9632;</span> High (7+)</li>
        <li><span style='color:orange; font-size: 18px;'>&#9632;</span> Medium (4-6)</li>
        <li><span style='color:green; font-size: 18px;'>&#9632;</span> Low (1-3)</li>
        <li><span style='color:grey; font-size: 18px;'>&#9632;</span> Unknown/NA</li>
    </ul>
    """
    st.sidebar.markdown(legend_html, unsafe_allow_html=True)

else:
    st.sidebar.info("No symptoms selected yet.")

# --- Diagnosis Section ---
st.header("Potential Diagnoses")


def add_suggested_symptom(symptom_name):
    if symptom_name not in st.session_state.selected_symptoms:
        st.session_state.selected_symptoms.append(symptom_name)


if st.session_state.selected_symptoms:
    st.markdown(f"Based on symptoms: **{', '.join(st.session_state.selected_symptoms)}**")

    if db_conn:
        list_of_disease_dicts, predicted_symptoms_list = diagnose_from_symptoms(db_conn,
                                                                                st.session_state.selected_symptoms)

        if list_of_disease_dicts:
            likely_diseases_info = []
            for disease_dict in list_of_disease_dicts:
                disease_name = disease_dict.get('name')
                score = disease_dict.get('score')
                if disease_name is not None and score is not None and score >= 50:
                    likely_diseases_info.append({'name': disease_name, 'score': score})

            if likely_diseases_info:
                st.subheader("Likely Diseases (Score >= 50%):")
                top_disease_info = likely_diseases_info[0]
                top_disease_name = top_disease_info['name']

                for disease_info in likely_diseases_info:
                    st.progress(disease_info['score'] / 100.0, text=f"{disease_info['name']}: {disease_info['score']}%")

                description = db_conn.get_disease_description(top_disease_name)
                actions = db_conn.get_disease_actions(top_disease_name)

                st.markdown("---")
                st.subheader(f"Details for {top_disease_name} (Top Score: {top_disease_info['score']}%)")

                if description:
                    st.markdown(f"**Description:** {description}")
                else:
                    st.markdown("**Description:** Not available.")

                if actions:
                    st.markdown("**Recommended Actions:**")
                    for action in actions:
                        st.markdown(f"- {action}")
                else:
                    st.markdown("**Recommended Actions:** Not available.")
            else:
                st.warning("No diseases found with a likelihood score of 50% or higher.")

            if predicted_symptoms_list:
                st.markdown("---")
                st.subheader("You might also be experiencing (click to add):")

                top_suggested = predicted_symptoms_list[:10]
                num_columns = 3
                cols = st.columns(num_columns)

                symptoms_shown_count = 0
                for i, symptom_info in enumerate(top_suggested):
                    symptom_name = symptom_info['symptom']
                    if symptom_name not in st.session_state.selected_symptoms:
                        if cols[symptoms_shown_count % num_columns].button(symptom_name,
                                                                           key=f"suggest_{symptom_name.replace(' ', '_')}",
                                                                           on_click=add_suggested_symptom,
                                                                           args=(symptom_name,)):
                            st.rerun()
                        symptoms_shown_count += 1

                if symptoms_shown_count == 0 and st.session_state.selected_symptoms:
                    st.info("No new symptoms suggested, or all suggestions are already selected.")
            elif st.session_state.selected_symptoms:
                st.info("No specific additional symptoms suggested based on current selection.")
        else:
            st.info("Could not determine potential diseases or suggest further symptoms with the current selection.")
    else:
        st.error("Database connection is not available. Cannot perform diagnosis.")
else:
    st.info("Please select symptoms to see potential diagnoses.")

st.markdown("---")
st.caption("Disclaimer: This tool is for informational purposes. Consult a healthcare professional for medical advice.")