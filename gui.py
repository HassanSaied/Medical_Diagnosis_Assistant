import streamlit as st
from database import HeartDiagnosisDB, import_data_from_json_to_db, diagnose_from_symptoms
from pathlib import Path
import tempfile
import os  # For path joining if needed, though pathlib is good

# Database file name
DB_FILE = 'heart_data_from_json.db'


@st.cache_resource
def init_db_connection(db_file):
    """Initializes and returns the database connection."""
    db_file_path = Path(db_file)
    # Check if DB file exists, if not, HeartDiagnosisDB will create it with tables.
    # No need to explicitly check for existence here if HeartDiagnosisDB handles creation.
    db = HeartDiagnosisDB(str(db_file_path))  # HeartDiagnosisDB expects a string path
    if not db.conn:
        st.error(
            f"CRITICAL ERROR: Failed to connect to or initialize database '{db_file}'. Check console for details from dataImporter.py.")
        return None
    return db


def get_color_for_severity(severity_value):
    """Returns a color string based on the severity value."""
    if severity_value is None: return "grey"
    try:
        severity = int(severity_value)
        if severity >= 7:
            return "red"  # High severity
        elif severity >= 4:
            return "orange"  # Medium severity
        elif severity >= 1:
            return "green"  # Low severity
        else:
            return "grey"  # For 0 or other unexpected values
    except ValueError:
        return "grey"  # Default for non-integer severity


# --- Streamlit Application ---
st.set_page_config(layout="wide")
st.title("Medical Diagnosis Assistant")

# Initialize database connection
db_conn = init_db_connection(DB_FILE)


# Initialize session state (robust to db_conn being None initially)
def initialize_session_state(force_reload=False):
    """Initializes or reloads data into session state from the database."""
    if db_conn is None:  # If DB connection failed, don't try to load from it
        st.session_state.selected_symptoms = []
        st.session_state.symptom_options_tuples = []
        st.session_state.symptom_severities = {}
        st.session_state.disease_options = []
        st.session_state.all_symptom_names_for_rules = []  # For rule management symptom selection
        return

    if 'selected_symptoms' not in st.session_state or force_reload:
        st.session_state.selected_symptoms = []

    # Load symptoms for dropdowns and severity coloring
    if 'symptom_options_tuples' not in st.session_state or force_reload:
        symptoms_from_db = db_conn.get_all_symptoms()  # Expected: [(id, name, severity), ...]
        st.session_state.symptom_options_tuples = symptoms_from_db if symptoms_from_db else []

    if 'symptom_severities' not in st.session_state or force_reload:
        st.session_state.symptom_severities = {
            name: sev for _id, name, sev in st.session_state.symptom_options_tuples
        }

    # Load diseases for rule management dropdown
    if 'disease_options' not in st.session_state or force_reload:
        diseases_from_db = db_conn.get_all_diseases()  # Expected: [(id, name, description), ...]
        st.session_state.disease_options = diseases_from_db if diseases_from_db else []

    # For rule management symptom multi-select
    if 'all_symptom_names_for_rules' not in st.session_state or force_reload:
        st.session_state.all_symptom_names_for_rules = [name for _id, name, _sev in
                                                        st.session_state.symptom_options_tuples]


# Attempt to initialize session state after db_conn is established
if 'symptom_options_tuples' not in st.session_state:  # Check if already initialized
    initialize_session_state()

# --- Main Application Logic ---
if db_conn:  # Only proceed if DB connection is successful
    tab1, tab2 = st.tabs(["🩺 Diagnosis", "⚙️ Manage Data"])

    with tab1:
        st.header("Symptom-Based Diagnosis")

        # --- Symptom Selection (Sidebar for Diagnosis Tab) ---
        st.sidebar.header("Select Symptoms for Diagnosis")


        def format_symptom_display(option_tuple_or_str):
            """Formats symptom for display in selectbox (shows name)."""
            if isinstance(option_tuple_or_str, tuple) and len(option_tuple_or_str) >= 2:
                return option_tuple_or_str[1]
            return str(option_tuple_or_str)


        def add_symptom_to_selected_list_from_selector():
            """Callback for symptom selectbox."""
            selected_option_tuple = st.session_state.get("symptom_selector_key")  # Use .get for safety
            if isinstance(selected_option_tuple, tuple) and len(selected_option_tuple) >= 2:
                symptom_name_to_add = selected_option_tuple[1]
                if symptom_name_to_add not in st.session_state.selected_symptoms:
                    st.session_state.selected_symptoms.append(symptom_name_to_add)
                    # Streamlit reruns automatically on widget interaction with on_change
            # Reset selector to allow re-selection or adding another after one is picked
            st.session_state.symptom_selector_key = ""

            # Prepare options for selectbox, ensuring the initial empty string is handled.


        options_for_selectbox = [""]  # Start with an empty option
        if st.session_state.get('symptom_options_tuples') and isinstance(st.session_state.symptom_options_tuples, list):
            options_for_selectbox.extend(st.session_state.symptom_options_tuples)

        st.sidebar.selectbox(
            "Search and select a symptom:",
            options=options_for_selectbox,
            key="symptom_selector_key",
            index=0,
            on_change=add_symptom_to_selected_list_from_selector,
            format_func=format_symptom_display,
            help="Select a symptom. It will be added for diagnosis."
        )

        # --- Display Selected Symptoms & Legend (Sidebar) ---
        if st.session_state.get('selected_symptoms'):
            st.sidebar.subheader("Selected Symptoms:")
            for symptom_name in list(st.session_state.selected_symptoms):  # Iterate copy for safe removal
                col1, col2 = st.sidebar.columns([0.8, 0.2])
                symptom_severity = st.session_state.symptom_severities.get(symptom_name)
                color = get_color_for_severity(symptom_severity)
                display_text = f"<span style='color:{color};'>- {symptom_name}</span>"
                col1.markdown(display_text, unsafe_allow_html=True)
                if col2.button("❌", key=f"remove_db_{symptom_name.replace(' ', '_')}", help=f"Remove {symptom_name}"):
                    st.session_state.selected_symptoms.remove(symptom_name)
                    st.rerun()  # Rerun to update list and diagnosis

            if st.sidebar.button("Clear All Symptoms", key="clear_all_db"):
                st.session_state.selected_symptoms = []
                st.rerun()  # Rerun

            st.sidebar.markdown("---")
            st.sidebar.markdown("##### Severity Legend:")
            legend_html = """<ul style="list-style-type: none; padding-left: 0;">
                <li><span style='color:red; font-size: 1.2em;'>&#9632;</span> High (7+)</li>
                <li><span style='color:orange; font-size: 1.2em;'>&#9632;</span> Medium (4-6)</li>
                <li><span style='color:green; font-size: 1.2em;'>&#9632;</span> Low (1-3)</li>
                <li><span style='color:grey; font-size: 1.2em;'>&#9632;</span> Unknown/NA</li></ul>"""
            st.sidebar.markdown(legend_html, unsafe_allow_html=True)
        else:
            st.sidebar.info("No symptoms selected yet.")

        # --- Diagnosis Results (Main area of Diagnosis Tab) ---
        st.subheader("Potential Diagnoses")
        if st.session_state.get('selected_symptoms'):
            st.markdown(f"Based on symptoms: **{', '.join(st.session_state.selected_symptoms)}**")

            # Call the diagnosis function from dataImporter
            list_of_disease_dicts, predicted_symptoms_list = diagnose_from_symptoms(db_conn,
                                                                                    st.session_state.selected_symptoms)

            if list_of_disease_dicts:
                # Filter for diseases with score >= 50% for "Likely Diseases"
                likely_diseases_info = [d for d in list_of_disease_dicts if d.get('score', 0) >= 50]

                if likely_diseases_info:
                    st.markdown("---")
                    st.subheader("Likely Diseases (Score >= 50%):")
                    # Display top scoring disease details first
                    top_disease_info = likely_diseases_info[0]  # Already sorted by diagnose_from_symptoms
                    top_disease_name = top_disease_info['name']

                    for disease_info in likely_diseases_info:
                        st.progress(disease_info['score'] / 100.0,
                                    text=f"{disease_info['name']}: {disease_info['score']}%")

                    description = db_conn.get_disease_description(top_disease_name)
                    actions = db_conn.get_disease_actions(top_disease_name)

                    st.markdown("#### Details for Top Diagnosis:")
                    st.markdown(f"**{top_disease_name}** (Score: {top_disease_info['score']}%)")
                    if description:
                        st.markdown(f"**Description:** {description}")
                    if actions:
                        st.markdown("**Recommended Actions:**")
                        for action in actions:
                            st.markdown(f"- {action}")
                else:
                    st.warning(
                        "No diseases found with a likelihood score of 50% or higher based on current symptoms. Lower scoring diseases might still be relevant.")
                    # Optionally, display all found diseases regardless of score if likely_diseases_info is empty but list_of_disease_dicts is not
                    if list_of_disease_dicts:  # but no one >= 50%
                        st.markdown("---")
                        st.subheader("Other Considered Diseases:")
                        for disease_info in list_of_disease_dicts[:5]:  # Show top 5 considered
                            st.markdown(f"- {disease_info['name']} (Score: {disease_info['score']}%)")

                # --- Suggested Symptoms ---
                if predicted_symptoms_list:
                    st.markdown("---")
                    st.subheader("You might also be experiencing (click to add):")

                    # Filter out already selected symptoms from suggestions
                    suggestions_to_show = [
                                              s_info for s_info in predicted_symptoms_list
                                              if s_info['symptom'] not in st.session_state.selected_symptoms
                                          ][:10]  # Show top 10 new suggestions

                    if suggestions_to_show:
                        num_columns = 3
                        cols = st.columns(num_columns)
                        for i, symptom_info in enumerate(suggestions_to_show):
                            s_name = symptom_info['symptom']
                            # Use a more robust key for buttons
                            button_key = f"suggest_{s_name.replace(' ', '_').replace('/', '_')}"
                            if cols[i % num_columns].button(s_name, key=button_key):
                                if s_name not in st.session_state.selected_symptoms:
                                    st.session_state.selected_symptoms.append(s_name)
                                    st.rerun()  # Rerun to reflect added symptom
                    else:
                        st.info("No new relevant symptoms to suggest, or all suggestions are already selected.")
                elif st.session_state.selected_symptoms:  # If symptoms selected but no predictions
                    st.info("No specific additional symptoms suggested based on current selection.")

            else:  # list_of_disease_dicts is empty
                st.info(
                    "Could not determine potential diseases with the current symptoms. Ensure data (especially rules) is loaded correctly via the 'Manage Data' tab.")
        else:
            st.info("Please select symptoms from the sidebar to see potential diagnoses.")

        st.markdown("---")
        st.caption(
            "Disclaimer: This tool is for informational purposes. Consult a healthcare professional for medical advice.")

    with tab2:
        st.header("Manage Database Content")
        st.markdown("Use this section to upload data in bulk or add individual entries.")

        # st.subheader("Upload Data from JSON Files")
        # st.markdown("""
        #     Upload two JSON files:
        #     1.  **Symptoms JSON**: Contains symptom descriptions and their severities (e.g., `{"symptom_name": severity_value, ...}`).
        #     2.  **Diseases & Rules JSON**: Contains disease info, actions, and rules (see `dataImporter.py` for expected structure).
        #     **Warning**: Importing will clear and overwrite existing database content.
        # """)
        #
        # # Corrected key for symptoms JSON uploader
        # uploaded_symptoms_file = st.file_uploader("Upload Symptoms JSON", type="json", key="symptoms_json_upload_key")
        # uploaded_diseases_file = st.file_uploader("Upload Diseases & Rules JSON", type="json",
        #                                           key="diseases_json_upload_key")
        #
        # if st.button("Import Data from JSON files", key="json_import_button"):
        #     if uploaded_symptoms_file is not None and uploaded_diseases_file is not None:
        #         tmp_symptoms_path, tmp_diseases_path = None, None  # Initialize for finally block
        #         try:
        #             # Save uploaded symptoms JSON to a temporary file
        #             with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="wb") as tmp_symptoms:
        #                 tmp_symptoms.write(uploaded_symptoms_file.getvalue())
        #                 tmp_symptoms_path = tmp_symptoms.name
        #
        #             # Save uploaded diseases/rules JSON to a temporary file
        #             with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="wb") as tmp_diseases:
        #                 tmp_diseases.write(uploaded_diseases_file.getvalue())
        #                 tmp_diseases_path = tmp_diseases.name
        #
        #             # Perform the import using absolute paths of temp files
        #             success = import_data_from_json_to_db(DB_FILE, tmp_diseases_path, tmp_symptoms_path)
        #
        #             if success:
        #                 st.success("Data imported successfully from JSON files!")
        #                 initialize_session_state(force_reload=True)  # Refresh all session data
        #                 st.rerun()
        #             else:
        #                 st.error("Data import failed. Check console for error messages from dataImporter.py.")
        #
        #         except Exception as e:
        #             st.error(f"An error occurred during the JSON import process: {e}")
        #         finally:
        #             # Clean up temporary files
        #             if tmp_symptoms_path and Path(tmp_symptoms_path).exists():
        #                 Path(tmp_symptoms_path).unlink()
        #             if tmp_diseases_path and Path(tmp_diseases_path).exists():
        #                 Path(tmp_diseases_path).unlink()
        #     else:
        #         st.warning("Please upload both JSON files to import.")
        #
        # st.markdown("---")

        st.subheader("Manually Add Data")

        with st.expander("Add New Disease"):
            with st.form("new_disease_form", clear_on_submit=True):
                new_disease_name = st.text_input("Disease Name (Unique)")
                new_disease_desc = st.text_area("Disease Description")
                submitted_disease = st.form_submit_button("Add Disease")
                if submitted_disease:
                    if new_disease_name:  # Description can be optional
                        disease_id = db_conn.add_disease_with_description(new_disease_name, new_disease_desc)
                        if disease_id:
                            st.success(f"Disease '{new_disease_name}' added/updated.")
                            initialize_session_state(force_reload=True)
                        else:
                            st.error(
                                f"Failed to add disease '{new_disease_name}'. It might already exist with a different description, or an error occurred.")
                    else:
                        st.warning("Disease name is required.")

        with st.expander("Add New Symptom"):
            with st.form("new_symptom_form", clear_on_submit=True):
                new_symptom_desc = st.text_input("Symptom Description (Unique)")
                new_symptom_severity = st.number_input("Symptom Severity (e.g., 1-10)", min_value=0, max_value=10,
                                                       step=1, value=None, placeholder="Optional")
                submitted_symptom = st.form_submit_button("Add Symptom")
                if submitted_symptom:
                    if new_symptom_desc:
                        symptom_id = db_conn.add_symptom(new_symptom_desc,
                                                         new_symptom_severity if new_symptom_severity is not None else None)
                        if symptom_id:
                            st.success(f"Symptom '{new_symptom_desc}' added/updated.")
                            initialize_session_state(force_reload=True)
                        else:
                            st.error(
                                f"Failed to add symptom '{new_symptom_desc}'. It might already exist with different severity, or an error occurred.")
                    else:
                        st.warning("Symptom description is required.")

        with st.expander("Add New Rule Condition Group"):
            if not st.session_state.get('disease_options') or not st.session_state.get('all_symptom_names_for_rules'):
                st.warning(
                    "Disease or symptom data not fully loaded. Cannot add rules yet. Try refreshing or importing data.")
            else:
                with st.form("new_rule_form", clear_on_submit=True):
                    disease_name_to_id = {name: d_id for d_id, name, _ in st.session_state.disease_options}

                    # Check if disease_name_to_id is empty before trying to use it in selectbox
                    if not disease_name_to_id:
                        st.warning("No diseases available to select. Please add diseases first.")
                        selected_disease_name_for_rule = None
                    else:
                        selected_disease_name_for_rule = st.selectbox(
                            "Select Disease for Rule",
                            options=list(disease_name_to_id.keys()),
                            key="rule_disease_select"
                        )

                    selected_symptom_names_for_rule = st.multiselect(
                        "Select Symptoms for this Condition Group (AND logic)",
                        options=st.session_state.all_symptom_names_for_rules,
                        key="rule_symptoms_multiselect"
                    )

                    submitted_rule = st.form_submit_button("Add Rule Condition Group")
                    if submitted_rule:
                        if selected_disease_name_for_rule and selected_symptom_names_for_rule:
                            # disease_id = disease_name_to_id[selected_disease_name_for_rule] # Already have name
                            group_id = db_conn.add_rule_condition_group(selected_disease_name_for_rule,
                                                                        selected_symptom_names_for_rule)
                            if group_id:
                                st.success(
                                    f"Rule condition group (ID: {group_id}) added successfully for '{selected_disease_name_for_rule}'.")
                                # No need to reload session state here unless rules affect other dropdowns directly
                            else:
                                st.error("Failed to add rule condition group. Check console for details.")
                        else:
                            st.warning("Please select a disease and at least one symptom for the rule group.")
else:  # db_conn is None
    st.error(
        "CRITICAL: Database connection could not be established. The application cannot function. Please ensure the database file is accessible and correctly configured.")

