import sqlite3
import csv
from pathlib import Path # Using pathlib for path handling
import json
from collections import defaultdict # Using defaultdict for easier counting
import traceback

class HeartDiagnosisDB:
    def __init__(self, db_name="heart_diagnosis.db"):
        """Initializes the database connection and creates tables if they don't exist."""
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._connect()
        if self.conn: # Only create tables if connection was successful
           self._create_tables()

    def _connect(self):
        """Establishes a connection to the SQLite database."""
        try:
            # Added timeout for robustness
            self.conn = sqlite3.connect(self.db_name,check_same_thread=False, timeout=10)
            # Enable foreign key support (important for ON DELETE CASCADE)
            self.conn.execute('PRAGMA foreign_keys = ON')
            self.cursor = self.conn.cursor()
            # print(f"Connected to database: {self.db_name}")
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            self.conn = None
            self.cursor = None

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.commit()
                self.conn.close()
                # print("Database connection closed.")
            except sqlite3.Error as e:
                 print(f"Error closing database: {e}")
            self.conn = None
            self.cursor = None

    def _execute_query(self, query, params=(), commit=False):
        """Helper to execute a SQL query."""
        if not self.conn:
            print("No database connection.")
            return None
        try:
            self.cursor.execute(query, params)
            if commit:
                self.conn.commit()
            return self.cursor
        except sqlite3.IntegrityError as e:
             # Handle specific integrity errors like unique constraints
             # print(f"Database integrity error: {e} Query: {query} Params: {params}")
             # Don't necessarily return None for IGNORE inserts
             return self.cursor # Return cursor even on IGNORE
        except sqlite3.Error as e:
            print(f"Database query error: {e} Query: {query} Params: {params}")
            # self.conn.rollback() # Optional: rollback on error for non-commit operations
            return None # Return None on general errors

    # Removed _check_column_exists method

    def _create_tables(self):
        """Creates the necessary tables and columns if they don't exist."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS diseases (
                disease_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT -- Description column included directly
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS symptoms (
                symptom_id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT UNIQUE NOT NULL,
                severity INTEGER -- Severity column included directly
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS rules (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_id INTEGER NOT NULL,
                FOREIGN KEY (disease_id) REFERENCES diseases(disease_id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS condition_groups (
                group_id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                FOREIGN KEY (rule_id) REFERENCES rules(rule_id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS condition_group_symptoms (
                group_id INTEGER NOT NULL,
                symptom_id INTEGER NOT NULL,
                PRIMARY KEY (group_id, symptom_id),
                FOREIGN KEY (group_id) REFERENCES condition_groups(group_id) ON DELETE CASCADE,
                FOREIGN KEY (symptom_id) REFERENCES symptoms(symptom_id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS disease_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                disease_id INTEGER NOT NULL,
                action_text TEXT NOT NULL,
                FOREIGN KEY (disease_id) REFERENCES diseases(disease_id) ON DELETE CASCADE
            );
            """
        ]
        for query in queries:
            self._execute_query(query)

        # Removed ALTER TABLE statements

        self.conn.commit() # Commit all creates at the end
        # print("Tables and columns checked/created.")


    # --- CRUD Operations ---

    # Diseases
    def add_disease(self, name):
        """Adds a new disease. Returns the disease_id or None if error."""
        query = "INSERT OR IGNORE INTO diseases (name) VALUES (?)"
        self._execute_query(query, (name,), commit=True)
        # Return the ID, whether inserted or already existed
        cursor = self._execute_query("SELECT disease_id FROM diseases WHERE name = ?", (name,))
        # Check cursor result before fetching
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    # NEW methods for manual data addition:
    def add_disease_with_description(self, name, description):
        """Adds a new disease to the database."""
        try:
            self.cursor.execute("INSERT INTO diseases (name, description) VALUES (?, ?)", (name, description))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Error: Disease '{name}' may already exist (name must be unique).")
            return None
        except sqlite3.Error as e:
            print(f"Database error in add_disease: {e}")
            return None



    def update_disease_description(self, disease_name, description):
        """Updates the description for an existing disease."""
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            # print(f"Warning: Disease '{disease_name}' not found for description update. Skipping.")
            return False
        query = "UPDATE diseases SET description = ? WHERE disease_id = ?"
        self._execute_query(query, (description, disease_id), commit=True)
        # print(f"Updated description for '{disease_name}'.")
        return True

    def add_disease_action(self, disease_name, action_text):
        """Adds an action for a disease."""
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            # print(f"Warning: Disease '{disease_name}' not found for adding action. Skipping.")
            return False
        # Use INSERT OR IGNORE if you want to prevent adding the exact same action text multiple times for the same disease
        query = "INSERT INTO disease_actions (disease_id, action_text) VALUES (?, ?)"
        self._execute_query(query, (disease_id, action_text), commit=True)
        # print(f"Added action for '{disease_name}'.")
        return True

    def get_disease_id(self, name):
        """Gets the ID of a disease by name."""
        query = "SELECT disease_id FROM diseases WHERE name = ?"
        cursor = self._execute_query(query, (name,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    def get_disease_name(self, disease_id):
        """Gets the name of a disease by ID."""
        query = "SELECT name FROM diseases WHERE disease_id = ?"
        cursor = self._execute_query(query, (disease_id,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    def get_disease_description(self, disease_name):
        """Gets the description of a disease by name."""
        query = "SELECT description FROM diseases WHERE name = ?"
        cursor = self._execute_query(query, (disease_name,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    def get_disease_actions(self, disease_name):
        """Gets all actions for a disease by name."""
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            return []
        query = "SELECT action_text FROM disease_actions WHERE disease_id = ?"
        cursor = self._execute_query(query, (disease_id,))
        return [row[0] for row in cursor.fetchall()] if cursor else []


    def get_all_diseases(self):
        """Retrieves all diseases."""
        query = "SELECT disease_id, name, description FROM diseases"
        cursor = self._execute_query(query)
        return cursor.fetchall() if cursor else []

    # Symptoms
    def add_symptom(self, description, severity=None):
        """Adds a new symptom. Returns the symptom_id or None if error."""
        # Check if symptom exists first
        symptom_id = self.get_symptom_id(description)
        if symptom_id is not None:
            # Symptom already exists, optionally update severity
            if severity is not None:
                self.update_symptom_severity(description, severity)
            return symptom_id # Return existing ID

        # Symptom does not exist, insert it
        query = "INSERT INTO symptoms (description, severity) VALUES (?, ?)"
        self._execute_query(query, (description, severity), commit=True)
         # Return the ID of the newly inserted symptom
        cursor = self._execute_query("SELECT symptom_id FROM symptoms WHERE description = ?", (description,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None


    def update_symptom_severity(self, symptom_description, severity):
        """Updates the severity for an existing symptom."""
        symptom_id = self.get_symptom_id(symptom_description)
        if symptom_id is None:
            # print(f"Warning: Symptom '{symptom_description}' not found for severity update. Skipping.")
            return False
        query = "UPDATE symptoms SET severity = ? WHERE symptom_id = ?"
        # Ensure severity is an integer
        try:
            severity_int = int(severity) if severity is not None else None
        except ValueError:
            print(f"Warning: Invalid severity value '{severity}' for symptom '{symptom_description}'. Skipping update.")
            return False

        self._execute_query(query, (severity_int, symptom_id), commit=True)
        # print(f"Updated severity for '{symptom_description}'.")
        return True


    def get_symptom_id(self, description):
        """Gets the ID of a symptom by description."""
        query = "SELECT symptom_id FROM symptoms WHERE description = ?"
        cursor = self._execute_query(query, (description,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    def get_symptom_description(self, symptom_id):
        """Gets the description of a symptom by ID."""
        query = "SELECT description FROM symptoms WHERE symptom_id = ?"
        cursor = self._execute_query(query, (symptom_id,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None

    def get_symptom_severity(self, symptom_description):
        """Gets the severity of a symptom by description."""
        query = "SELECT severity FROM symptoms WHERE description = ?"
        cursor = self._execute_query(query, (symptom_description,))
        result = cursor.fetchone() if cursor else None
        return result[0] if result else None


    def get_all_symptoms(self):
        """Retrieves all symptoms with their severity."""
        query = "SELECT symptom_id, description, severity FROM symptoms"
        cursor = self._execute_query(query)
        return cursor.fetchall() if cursor else []

    # Rules - More complex CRUD
    def add_rule(self, disease_name, rule_structure):
        """
        Adds a complex rule for a disease.
        rule_structure is a list of lists of symptom descriptions.
        Example: [['symptom1', 'symptom2'], ['symptom3']]
        This translates to: (symptom1 AND symptom2) OR (symptom3) leads to disease_name.

        Returns True on success, False otherwise.
        """
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            print(f"Warning: Disease '{disease_name}' not found when adding rule. Rule skipped.")
            return False

        if not rule_structure:
            # print(f"Warning: Empty rule structure provided for disease '{disease_name}'. Rule skipped.")
            return False

        try:
            self.conn.execute("BEGIN TRANSACTION") # Start transaction

            # 1. Add the rule for the disease
            insert_rule_query = "INSERT INTO rules (disease_id) VALUES (?)"
            cursor = self._execute_query(insert_rule_query, (disease_id,))
            if not cursor: # Check for query execution error
                self.conn.rollback()
                print(f"Error adding rule entry for disease '{disease_name}'. Rolling back.")
                return False
            rule_id = cursor.lastrowid

            # 2. Add condition groups and their symptoms
            for condition_group_symptoms_desc in rule_structure:
                if not condition_group_symptoms_desc:
                     # This case should ideally be handled by the CSV parser filtering,
                     # but added as a safeguard.
                     print("Warning: Empty condition group found in rule structure during DB add. Skipping.")
                     continue

                # Add the condition group
                insert_group_query = "INSERT INTO condition_groups (rule_id) VALUES (?)"
                cursor = self._execute_query(insert_group_query, (rule_id,))
                if not cursor: # Check for query execution error
                    self.conn.rollback()
                    print(f"Error adding condition group for rule {rule_id}. Rolling back.")
                    return False
                group_id = cursor.lastrowid

                # Add symptoms to the condition group
                for symptom_desc in condition_group_symptoms_desc:
                    symptom_id = self.get_symptom_id(symptom_desc)
                    if symptom_id is None:
                        # This case should ideally not happen if symptoms were pre-added
                        print(f"Error: Symptom '{symptom_desc}' not found when adding rule symptoms for disease '{disease_name}'. Rolling back transaction.")
                        self.conn.rollback() # Rollback the entire rule addition
                        return False

                    insert_cgs_query = "INSERT INTO condition_group_symptoms (group_id, symptom_id) VALUES (?, ?)"
                    # Using IGNORE here prevents error if somehow a duplicate symptom_id for the *same group_id* is attempted,
                    # though the parser should prevent this.
                    cursor = self._execute_query(insert_cgs_query, (group_id, symptom_id,), commit=False)
                    if cursor is None: # Check if the last query failed
                         self.conn.rollback()
                         print(f"Error adding symptom link for group {group_id}, symptom '{symptom_desc}'. Rolling back.")
                         return False


            self.conn.commit() # Commit transaction if all successful
            # print(f"Rule added successfully for '{disease_name}'.")
            return True

        except sqlite3.Error as e:
            print(f"Database error adding rule for '{disease_name}': {e}")
            self.conn.rollback() # Rollback on any error during the process
            return False
        except Exception as e:
             print(f"Unexpected error adding rule for '{disease_name}': {e}")
             self.conn.rollback()
             raise # Re-raise unexpected errors

    # --- Rule Management Methods ---
    def get_or_create_rule_for_disease(self, disease_id):
        """
        Gets the existing rule_id for a disease or creates a new one if it doesn't exist.
        This assumes a disease has one primary 'rule' entry in the 'rules' table,
        which then links to multiple condition groups.
        """
        if disease_id is None:
            return None

        query_select = "SELECT rule_id FROM rules WHERE disease_id = ?"
        cursor = self._execute_query(query_select, (disease_id,))
        result = cursor.fetchone() if cursor else None

        if result:
            return result[0]  # Existing rule_id
        else:
            # Create a new rule for this disease
            query_insert = "INSERT INTO rules (disease_id) VALUES (?)"
            insert_cursor = self._execute_query(query_insert, (disease_id,), commit=True)
            return insert_cursor.lastrowid if insert_cursor else None

    def add_rule_condition_group(self, disease_name, symptom_names_in_group):
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            print(f"Error: Disease '{disease_name}' not found. Cannot add rule group.")
            return None

        if not symptom_names_in_group:
            print("Error: No symptoms provided for the condition group.")
            return None

        rule_id = self.get_or_create_rule_for_disease(disease_id)
        if rule_id is None:
            print(f"Error: Could not get or create a rule for disease ID {disease_id}.")
            return None

        symptom_ids_in_group = []
        for sym_name in symptom_names_in_group:
            s_id = self.get_symptom_id(sym_name)
            if s_id is None:
                print(f"Warning: Symptom '{sym_name}' not found. It will be skipped for this rule group.")
            else:
                symptom_ids_in_group.append(s_id)

        if not symptom_ids_in_group:
            print("Error: No valid symptoms (after lookup) found for the condition group. Rule group not added.")
            return None

        try:
            insert_cg_query = "INSERT INTO condition_groups (rule_id) VALUES (?)"
            # Committing here ensures group_id is available if the next step fails partially
            cg_cursor = self._execute_query(insert_cg_query, (rule_id,), commit=True)
            if not cg_cursor or cg_cursor.lastrowid is None:
                print(f"Error: Failed to insert into condition_groups for rule_id {rule_id}.")
                # No explicit rollback needed here as _execute_query doesn't start a transaction
                # and commit=True was for this single statement.
                return None
            new_group_id = cg_cursor.lastrowid

            conditions_to_insert = [(new_group_id, s_id) for s_id in symptom_ids_in_group]

            # For executemany, it's often better to manage transaction explicitly if needed,
            # but here we'll commit after it's done.
            # We need a fresh cursor for executemany if the class cursor was used by _execute_query.
            exec_many_cursor = self.conn.cursor()
            exec_many_cursor.executemany("INSERT INTO condition_group_symptoms (group_id, symptom_id) VALUES (?, ?)",
                                         conditions_to_insert)
            self.conn.commit()

            print(
                f"Successfully added condition group {new_group_id} for disease '{disease_name}' (rule_id {rule_id}).")
            return new_group_id
        except sqlite3.IntegrityError as e:
            print(f"Database integrity error while adding condition group or its symptoms: {e}")
            self.conn.rollback()  # Rollback any part of the transaction if one was implicitly started by Python's sqlite3
            return None
        except sqlite3.Error as e:
            print(f"General database error while adding condition group: {e}")
            self.conn.rollback()
            return None

    def get_rules_for_disease(self, disease_name):
        """
        Retrieves the rule structure for a given disease.
        Returns a list of lists of symptom descriptions.
        Example: [['symptom1', 'symptom2'], ['symptom3']]
        Returns an empty list if disease not found or no rules.
        """
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            # print(f"Disease '{disease_name}' not found.")
            return []

        # Query to get all condition groups and their symptoms for a disease's rules
        query = """
        SELECT
            cg.group_id,
            s.description
        FROM rules r
        JOIN condition_groups cg ON r.rule_id = cg.rule_id
        JOIN condition_group_symptoms cgs ON cg.group_id = cgs.group_id
        JOIN symptoms s ON cgs.symptom_id = s.symptom_id
        WHERE r.disease_id = ?
        ORDER BY cg.group_id, s.description; -- Order by group_id then symptom description for consistent retrieval
        """
        cursor = self._execute_query(query, (disease_id,))
        results = cursor.fetchall() if cursor else []

        if not results:
            return []

        # Reconstruct the rule structure from the flat results
        rule_structure = []
        current_group_id = None
        current_group_symptoms = []

        for group_id, symptom_desc in results:
            if group_id != current_group_id:
                # New group starts
                if current_group_symptoms: # Add the previous group if it exists and is not empty
                    rule_structure.append(current_group_symptoms)
                current_group_symptoms = [symptom_desc]
                current_group_id = group_id
            else:
                # Same group, add symptom
                current_group_symptoms.append(symptom_desc)

        # Add the last group if it exists and is not empty
        if current_group_symptoms:
            rule_structure.append(current_group_symptoms)

        return rule_structure

    # Basic Delete Operations (Optional, can be complex with cascades)
    def delete_disease(self, disease_name):
        """Deletes a disease and cascades to rules, groups, and links."""
        disease_id = self.get_disease_id(disease_name)
        if disease_id is None:
            print(f"Disease '{disease_name}' not found for deletion.")
            return False
        query = "DELETE FROM diseases WHERE disease_id = ?"
        self._execute_query(query, (disease_id,), commit=True)
        print(f"Disease '{disease_name}' and its related data deleted.")
        return True

    def delete_symptom(self, symptom_description):
        """Deletes a symptom. NOTE: Deleting a symptom might break existing rules!"""
        symptom_id = self.get_symptom_id(symptom_description)
        if symptom_id is None:
            print(f"Symptom '{symptom_description}' not found for deletion.")
            return False
        # Deleting a symptom will cascade and remove it from condition_group_symptoms.
        # This might leave condition groups with fewer symptoms or potentially empty.
        # The expert system logic would need to handle potentially empty groups or
        # you could add logic here to clean up empty groups/rules.
        query = "DELETE FROM symptoms WHERE symptom_id = ?"
        self._execute_query(query, (symptom_id,), commit=True)
        print(f"Symptom '{symptom_description}' and its related data deleted.")
        return True

# --- End of HeartDiagnosisDB class ---


def import_all_data_from_csvs(db_path, rules_csv_path, descriptions_csv_path, actions_csv_path, severity_csv_path):
    """
    Reads data from multiple CSV files and imports them into the database.

    Args:
        db_path (str): Path to the SQLite database file.
        rules_csv_path (str): Path to the CSV file containing the rules
                              (Format: Disease,Symptom1,Symptom2,... - ORed rows, ANDed columns).
        descriptions_csv_path (str): Path to the CSV file containing disease descriptions
                                     (Format: Disease,Description).
        actions_csv_path (str): Path to the CSV file containing disease actions
                                (Format: Disease,Action1,Action2,... - multiple action columns per disease).
        severity_csv_path (str): Path to the CSV file containing symptom severity
                                 (Format: Symptom,Severity).
    """
    # Check if all required CSV files exist
    csv_paths = {
        'rules': Path(rules_csv_path),
        'descriptions': Path(descriptions_csv_path),
        'actions': Path(actions_csv_path),
        'severity': Path(severity_csv_path)
    }

    for key, path in csv_paths.items():
        if not path.exists():
            print(f"Error: Required CSV file not found: {path}")
            return

    print(f"Starting data import into {db_path} from CSV files...")

    # --- Phase 1: Collect all unique diseases and symptoms from all CSVs ---
    print("\nCollecting unique diseases and symptoms from all CSVs...")
    all_unique_diseases = set()
    all_unique_symptoms = set()

    # From Rules CSV (assuming format: Disease,Symptom1,Symptom2,...)
    try:
        with open(csv_paths['rules'], mode='r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            # Optional: Skip header row
            try:
                next(csv_reader)
            except StopIteration:
                pass
            for row in csv_reader:
                if not row or len(row) < 2: continue
                disease_name = row[0].strip()
                symptoms_in_group = [s.strip() for s in row[1:] if s.strip()]
                if disease_name: all_unique_diseases.add(disease_name)
                all_unique_symptoms.update(symptoms_in_group)
    except Exception as e: print(f"Error reading rules CSV for collection: {e}")

    # From Descriptions CSV (assuming format: Disease,Description)
    try:
        with open(csv_paths['descriptions'], mode='r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            try: next(csv_reader) # Skip header
            except StopIteration: pass
            for row in csv_reader:
                if not row or len(row) < 2: continue
                disease_name = row[0].strip()
                if disease_name: all_unique_diseases.add(disease_name)
    except Exception as e: print(f"Error reading descriptions CSV for collection: {e}")

    # From Actions CSV (assuming format: Disease,Action1,Action2,...)
    try:
        with open(csv_paths['actions'], mode='r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            try: next(csv_reader) # Skip header
            except StopIteration: pass
            for row in csv_reader:
                if not row or len(row) < 2: continue
                disease_name = row[0].strip()
                if disease_name: all_unique_diseases.add(disease_name)
    except Exception as e: print(f"Error reading actions CSV for collection: {e}")

    # From Severity CSV (assuming format: Symptom,Severity)
    try:
        with open(csv_paths['severity'], mode='r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)
            try: next(csv_reader) # Skip header
            except StopIteration: pass
            for row in csv_reader:
                if not row or len(row) < 2: continue
                symptom_name = row[0].strip()
                if symptom_name: all_unique_symptoms.add(symptom_name)
    except Exception as e: print(f"Error reading severity CSV for collection: {e}")

    print(f"Collected {len(all_unique_diseases)} unique diseases and {len(all_unique_symptoms)} unique symptoms.")


    # --- Phase 2: Add unique diseases and symptoms to DB ---
    db = HeartDiagnosisDB(db_path)
    if db.conn is None:
        print("Failed to connect to the database. Aborting import.")
        return

    try:
        print("\nAdding unique diseases to database...")
        for disease_name in all_unique_diseases:
            db.add_disease(disease_name) # add_disease handles existence check

        print("Adding unique symptoms to database...")
        for symptom_description in all_unique_symptoms:
            # Add symptoms without severity first, severity will be updated later
            db.add_symptom(symptom_description) # add_symptom handles existence check

        # --- Phase 3: Import Descriptions ---
        print("\nImporting disease descriptions...")
        try:
            with open(csv_paths['descriptions'], mode='r', encoding='utf-8') as csvfile:
                csv_reader = csv.reader(csvfile)
                try: next(csv_reader) # Skip header
                except StopIteration: pass
                for row in csv_reader:
                    if not row or len(row) < 2: continue
                    disease_name = row[0].strip()
                    description = row[1].strip() if len(row) > 1 else '' # Handle potentially empty description column
                    if disease_name:
                        db.update_disease_description(disease_name, description)
        except Exception as e: print(f"Error importing descriptions CSV: {e}")


        # --- Phase 4: Import Actions ---
        print("\nImporting disease actions...")
        try:
            with open(csv_paths['actions'], mode='r', encoding='utf-8') as csvfile:
                csv_reader = csv.reader(csvfile)
                try: next(csv_reader) # Skip header
                except StopIteration: pass
                for row in csv_reader:
                    if not row or len(row) < 2: continue
                    disease_name = row[0].strip()
                    actions = [a.strip() for a in row[1:] if a.strip()] # Get all action columns
                    if disease_name and actions:
                        for action_text in actions:
                            db.add_disease_action(disease_name, action_text)
        except Exception as e: print(f"Error importing actions CSV: {e}")


        # --- Phase 5: Import Severity ---
        print("\nImporting symptom severity...")
        try:
            with open(csv_paths['severity'], mode='r', encoding='utf-8') as csvfile:
                csv_reader = csv.reader(csvfile)
                try: next(csv_reader) # Skip header
                except StopIteration: pass
                for row in csv_reader:
                    if not row or len(row) < 2: continue
                    symptom_name = row[0].strip()
                    severity_str = row[1].strip() if len(row) > 1 else None
                    if symptom_name and severity_str is not None:
                         try:
                             severity = int(severity_str)
                             db.update_symptom_severity(symptom_name, severity)
                         except ValueError:
                             print(f"Warning: Could not parse severity '{severity_str}' for symptom '{symptom_name}'. Skipping severity update.")
        except Exception as e: print(f"Error importing severity CSV: {e}")


        # --- Phase 6: Import Rules (with deduplication) ---
        print("\nImporting rules and checking for duplicates...")
        disease_rules_map = {} # { 'Disease Name': [['SymptomA', 'SymptomB'], ['SymptomC']], ... }

        try:
            with open(csv_paths['rules'], mode='r', encoding='utf-8') as csvfile:
                csv_reader = csv.reader(csvfile)
                # Optional: Skip header row
                # try: next(csv_reader) except StopIteration: pass
                for row in csv_reader:
                    if not row or len(row) < 2: continue
                    disease_name = row[0].strip()
                    symptoms_in_group = [s.strip() for s in row[1:] if s.strip()] # Strip whitespace & filter empty symptom strings

                    if not disease_name or not symptoms_in_group: continue # Skip invalid rows

                    if disease_name not in disease_rules_map:
                        disease_rules_map[disease_name] = []
                    disease_rules_map[disease_name].append(symptoms_in_group)

        except Exception as e:
            print(f"An error occurred while reading the rules CSV for import: {e}")
            # Decide if you want to abort or continue with other data if rules import fails
            # For now, we'll continue but print the error.

        # Process to remove duplicate condition groups per disease
        cleaned_disease_rules_map = {}
        total_duplicates_removed = 0

        for disease_name, list_of_symptom_lists in disease_rules_map.items():
            seen_groups_fingerprints = set()
            unique_groups_for_disease = []

            for symptom_list in list_of_symptom_lists:
                group_fingerprint = tuple(sorted(symptom_list))
                if group_fingerprint not in seen_groups_fingerprints:
                    unique_groups_for_disease.append(symptom_list)
                    seen_groups_fingerprints.add(group_fingerprint)
                else:
                    total_duplicates_removed += 1
                    # print(f"  Removed duplicate group for '{disease_name}': {symptom_list}")

            cleaned_disease_rules_map[disease_name] = unique_groups_for_disease

        print(f"Rule deduplication complete. Total duplicates removed: {total_duplicates_removed}")

        # Add rules to DB
        for disease_name, rule_structure in cleaned_disease_rules_map.items():
             if rule_structure:
                # print(f"Adding rule for '{disease_name}' with {len(rule_structure)} unique condition groups.")
                db.add_rule(disease_name, rule_structure)
             # else: print(f"Disease '{disease_name}' had no valid condition groups after cleaning. Skipping rule.")


        print("\nFull import process complete.")

    except Exception as e:
        print(f"An unexpected error occurred during the import process: {e}")
    finally:
        db.close() # Ensure the connection is closed

def import_associations_from_csv(db_path, csv_filepath):
    """
    Reads disease-symptom associations from a CSV file and imports them
    as rules into the database, removing duplicate condition groups per disease.

    CSV format expected:
    Header Row: Disease,SymptomA,SymptomB,SymptomC,...
    Data Rows:  DiseaseX,1,0,1,... (1 or TRUE means symptom is present for this group)

    Each data row becomes one condition group (AND set) for the disease.
    Multiple rows for the same disease are ORed together.

    Args:
        db_path (str): Path to the SQLite database file.
        csv_filepath (str): Path to the CSV file containing the associations.
    """
    csv_file_path = Path(csv_filepath)

    if not csv_file_path.exists():
        print(f"Error: CSV file not found at {csv_file_path}")
        return

    print(f"Reading associations from {csv_file_path}...")

    # Use a dictionary to group symptom lists by disease name
    # { 'Disease Name': [['SymptomA', 'SymptomB'], ['SymptomC']], ... }
    disease_rules_map = {}
    unique_symptoms = set()
    unique_diseases = set()
    symptom_headers = [] # To store symptom names from the header

    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as csvfile:
            csv_reader = csv.reader(csvfile)

            # Read the header row
            try:
                header = next(csv_reader)
                if not header:
                    print("Error: CSV header is empty.")
                    return
                if header[0].strip().lower() != 'disease':
                    print(f"Warning: Expected 'Disease' in the first column header, found '{header[0]}'. Proceeding assuming first column is disease name.")

                # The rest of the headers are symptom names
                symptom_headers = [h.strip() for h in header[1:] if h.strip()]
                if not symptom_headers:
                    print("Error: No symptom columns found in the CSV header.")
                    return
                unique_symptoms.update(symptom_headers)

            except StopIteration:
               print("Error: CSV file is empty or contains only a header.")
               return
            except Exception as e:
                print(f"An error occurred while reading the CSV header: {e}")
                return


            # Read data rows
            for row in csv_reader:
                # Skip empty rows or rows without enough columns (must have disease + at least one symptom column)
                if not row or len(row) < len(header):
                    # print(f"Skipping invalid row (column count mismatch): {row}")
                    continue

                disease_name = row[0].strip()
                if not disease_name:
                    # print(f"Skipping invalid row (empty disease name): {row}")
                    continue

                unique_diseases.add(disease_name)

                # Build the list of symptoms for this condition group (this row)
                symptoms_in_group = []
                # Iterate through columns starting from the second one (index 1)
                for i in range(1, len(row)):
                    # Ensure index is within bounds of symptom_headers
                    if i - 1 < len(symptom_headers):
                        cell_value = row[i].strip().lower()
                        # Check for '1' or 'true' (case-insensitive)
                        if cell_value == '1' or cell_value == 'true':
                            symptom_name = symptom_headers[i - 1]
                            symptoms_in_group.append(symptom_name)
                            # Add symptom to unique list just in case it wasn't in header (less likely with this format)
                            unique_symptoms.add(symptom_name)
                    else:
                        # This should not happen if row length check passes, but good practice
                        print(f"Warning: Row has more columns than header. Skipping extra data in row: {row}")


                if not symptoms_in_group:
                     # print(f"Skipping row for '{disease_name}' with no symptoms marked as present: {row}")
                     continue

                if disease_name not in disease_rules_map:
                    disease_rules_map[disease_name] = []

                # Add this group of symptoms (the AND condition) to the list for this disease (the OR list)
                disease_rules_map[disease_name].append(symptoms_in_group)

        print(f"Finished reading CSV. Found {len(unique_diseases)} unique diseases and {len(unique_symptoms)} unique symptoms.")

    except FileNotFoundError:
         print(f"Error: CSV file not found at {csv_file_path}")
         return
    except Exception as e:
        print(f"An error occurred while reading the CSV: {e}")
        return

    # --- Process to remove duplicate condition groups per disease ---
    print("\nChecking for and removing duplicate condition groups...")
    cleaned_disease_rules_map = {}
    total_duplicates_removed = 0

    for disease_name, list_of_symptom_lists in disease_rules_map.items():
        seen_groups_fingerprints = set()
        unique_groups_for_disease = []

        for symptom_list in list_of_symptom_lists:
            # Create a unique 'fingerprint' for this group by sorting and converting to a tuple
            # This makes ['A', 'B'] the same as ['B', 'A']
            group_fingerprint = tuple(sorted(symptom_list))

            if group_fingerprint not in seen_groups_fingerprints:
                unique_groups_for_disease.append(symptom_list) # Add the original list (not the sorted tuple)
                seen_groups_fingerprints.add(group_fingerprint)
            else:
                total_duplicates_removed += 1
                # print(f"  Removed duplicate group for '{disease_name}': {symptom_list}")

        cleaned_disease_rules_map[disease_name] = unique_groups_for_disease

    print(f"Duplicate removal complete. Total duplicates removed: {total_duplicates_removed}")
    # --- End of duplicate removal ---


    # Now, connect to the database and add the data from the cleaned map
    db = HeartDiagnosisDB(db_path)

    if db.conn is None: # Check if database connection was successful
        print("Failed to connect to the database. Aborting import.")
        return

    try:
        print("\nAdding diseases to database...")
        # Add all unique diseases found
        for disease_name in unique_diseases:
            db.add_disease(disease_name) # add_disease handles existence check

        print("Adding symptoms to database...")
        # Add all unique symptoms found *before* adding rules
        # This includes symptoms from headers and potentially from data rows if inconsistent
        for symptom_description in unique_symptoms:
            db.add_symptom(symptom_description) # add_symptom handles existence check

        print("\nAdding rules to database...")
        # Use the cleaned map
        for disease_name, rule_structure in cleaned_disease_rules_map.items():
             # rule_structure is the list of unique AND groups (list of lists of symptom strings)
             # Only add rules for diseases that still have condition groups after cleaning
             if rule_structure:
                print(f"Adding rule for '{disease_name}' with {len(rule_structure)} unique condition groups.")
                db.add_rule(disease_name, rule_structure)
             else:
                 print(f"Disease '{disease_name}' had no valid condition groups after cleaning. Skipping rule.")


        print("\nImport complete.")

    except Exception as e:
        print(f"An error occurred during database import: {e}")
    finally:
        db.close() # Ensure the connection is closed

def dump_full_disease_data_to_json(db_path, output_json_path):
    """
    Dumps comprehensive disease data (rules, description, actions)
    from the database into a JSON file.

    Rules are deduplicated and diseases with no rules after deduplication
    are filtered out.

    JSON structure:
    {
        "Disease Name 1": {
            "rules": [
                ["Symptom A", "Symptom B"],  // Condition Group 1 (AND)
                ["Symptom C"]                // Condition Group 2 (AND)
            ], // These groups are ORed
            "description": "...",
            "actions": ["Action 1", "Action 2"]
        },
        ...
    }

    Args:
        db_path (str): Path to the SQLite database file.
        output_json_path (str): Path to the output JSON file.
    """
    db_file_path = Path(db_path)
    json_file_path = Path(output_json_path)

    if not db_file_path.exists():
        print(f"Error: Database file not found at {db_file_path}")
        return

    db = HeartDiagnosisDB(db_path)
    if db.conn is None:
        print("Failed to connect to the database. Aborting dump.")
        return

    db_data_raw = {}
    db_data_cleaned = {}
    total_duplicates_removed = 0
    diseases_with_no_rules = 0

    try:
        # Retrieve all diseases
        diseases = db.get_all_diseases() # get_all_diseases returns (id, name, description)

        print(f"Retrieving full data for {len(diseases)} diseases from database...")

        # For each disease, retrieve its rules, description, and actions
        for disease_id, disease_name, description in diseases:
            # Get rules (already handles fetching symptom names)
            rule_structure = db.get_rules_for_disease(disease_name)

            # Get actions
            actions = db.get_disease_actions(disease_name)

            # Store the raw data
            db_data_raw[disease_name] = {
                "rules": rule_structure,
                "description": description,
                "actions": actions
            }

        print("Finished retrieving raw disease data from database.")

        # --- Process to remove duplicate condition groups per disease and filter diseases with no rules ---
        print("\nChecking for and removing duplicate condition groups and filtering diseases with no rules before dumping...")

        for disease_name, data in db_data_raw.items():
            list_of_symptom_lists = data["rules"]
            seen_groups_fingerprints = set()
            unique_groups_for_disease = []

            for symptom_list in list_of_symptom_lists:
                # Create a unique 'fingerprint' for this group by sorting and converting to a tuple
                group_fingerprint = tuple(sorted(symptom_list))

                if group_fingerprint not in seen_groups_fingerprints:
                    unique_groups_for_disease.append(symptom_list) # Add the original list
                    seen_groups_fingerprints.add(group_fingerprint)
                else:
                    total_duplicates_removed += 1
                    # print(f"  Removed duplicate rule group for '{disease_name}': {symptom_list}")

            # Only add the disease to the cleaned data if it still has rules after deduplication
            if unique_groups_for_disease:
                db_data_cleaned[disease_name] = {
                    "rules": unique_groups_for_disease,
                    "description": data["description"],
                    "actions": data["actions"]
                }
            else:
                diseases_with_no_rules += 1
                print(f"  Filtering out disease '{disease_name}' as it has no rules after deduplication.")


        print(f"Duplicate condition group removal complete. Total duplicates removed across all diseases: {total_duplicates_removed}")
        print(f"Total diseases filtered out due to having no rules: {diseases_with_no_rules}")
        # --- End of processing ---


        # Convert the cleaned and filtered dictionary to a JSON string
        json_string = json.dumps(db_data_cleaned, indent=4)

        # Write the JSON string to the output file
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json_file.write(json_string)

        print(f"Cleaned and filtered full disease data successfully dumped to {json_file_path}")

    except Exception as e:
        print(f"An error occurred during the database dump: {e}")
    finally:
        db.close() # Ensure the connection is closed


def dump_symptom_severity_to_json(db_path, output_json_path):
    """
    Dumps symptom descriptions and their severity from the database into a JSON file.

    JSON structure:
    {
        "Symptom Name 1": 8,
        "Symptom Name 2": 5,
        ...
    }

    Args:
        db_path (str): Path to the SQLite database file.
        output_json_path (str): Path to the output JSON file.
    """
    db_file_path = Path(db_path)
    json_file_path = Path(output_json_path)

    if not db_file_path.exists():
        print(f"Error: Database file not found at {db_file_path}")
        return

    db = HeartDiagnosisDB(db_path)
    if db.conn is None:
        print("Failed to connect to the database. Aborting dump.")
        return

    symptom_data = {}

    try:
        # Retrieve all symptoms with their severity
        symptoms = db.get_all_symptoms() # get_all_symptoms returns (id, description, severity)

        print(f"Retrieving data for {len(symptoms)} symptoms from database...")

        # Format into the desired JSON structure
        for symptom_id, description, severity in symptoms:
            symptom_data[description] = severity if severity is not None else "N/A" # Handle None severity

        print("Finished retrieving symptom data from database.")

        # Convert the dictionary to a JSON string
        json_string = json.dumps(symptom_data, indent=4)

        # Write the JSON string to the output file
        with open(json_file_path, 'w', encoding='utf-8') as json_file:
            json_file.write(json_string)

        print(f"Symptom severity data successfully dumped to {json_file_path}")

    except Exception as e:
        print(f"An error occurred during the database dump: {e}")
    finally:
        db.close() # Ensure the connection is closed


def import_data_from_json_to_db(disease_json_path, symptom_json_path, new_db_path):
    """
    Reads disease and symptom data from JSON files and imports them into a new database.

    Args:
        disease_json_path (str): Path to the JSON file containing disease data
                                 (rules, description, actions).
        symptom_json_path (str): Path to the JSON file containing symptom severity.
        new_db_path (str): Path to the new SQLite database file to create/populate.
    """
    disease_json_file_path = Path(disease_json_path)
    symptom_json_file_path = Path(symptom_json_path)
    new_db_file_path = Path(new_db_path)

    if not disease_json_file_path.exists():
        print(f"Error: Disease JSON file not found at {disease_json_file_path}")
        return
    if not symptom_json_file_path.exists():
        print(f"Error: Symptom JSON file not found at {symptom_json_file_path}")
        return

    print(f"Starting data import into new database '{new_db_path}' from JSON files...")

    # Delete existing DB file if it exists to ensure a fresh start
    if new_db_file_path.exists():
        try:
            new_db_file_path.unlink(missing_ok=True)
            print(f"Removed existing database file: {new_db_file_path}")
        except OSError as e:
            print(f"Error removing existing database file {new_db_file_path}: {e}")
            # Decide if you want to abort or continue
            return # Abort for safety

    # Connect to the new database (this will create it)
    db = HeartDiagnosisDB(new_db_path)
    if db.conn is None:
        print("Failed to connect to the new database. Aborting import.")
        return

    try:
        # --- Phase 1: Import Symptoms ---
        print("\nImporting symptom data from JSON...")
        symptom_data = {}
        try:
            with open(symptom_json_file_path, 'r', encoding='utf-8') as f:
                symptom_data = json.load(f)

            for symptom_name, severity in symptom_data.items():
                # Add symptom using add_symptom which handles severity
                db.add_symptom(symptom_name, severity)
            print(f"Imported {len(symptom_data)} symptoms.")

        except FileNotFoundError:
             print(f"Error: Symptom JSON file not found: {symptom_json_file_path}")
             # Decide if this is a fatal error or if you can continue
             db.close()
             return
        except json.JSONDecodeError as e:
            print(f"Error decoding Symptom JSON: {e}")
            db.close()
            return
        except Exception as e:
            print(f"An error occurred during symptom import: {e}")
            db.close()
            return

        # --- Phase 2: Import Diseases, Descriptions, Actions, and Rules ---
        print("\nImporting disease data (description, actions, rules) from JSON...")
        disease_data = {}
        try:
            with open(disease_json_file_path, 'r', encoding='utf-8') as f:
                disease_data = json.load(f)

            for disease_name, data in disease_data.items():
                rules = data.get("rules", [])
                description = data.get("description", "")
                actions = data.get("actions", [])

                # Add disease (or get ID if already added by rules - though rules are added after diseases here)
                db.add_disease(disease_name) # Ensure disease exists

                # Update description
                db.update_disease_description(disease_name, description)

                # Add actions
                for action_text in actions:
                    db.add_disease_action(disease_name, action_text)

                # Add rules
                if rules:
                    db.add_rule(disease_name, rules)
                else:
                    print(f"Warning: Disease '{disease_name}' has no rules in JSON. Skipping rule import for this disease.")

            print(f"Imported data for {len(disease_data)} diseases.")

        except FileNotFoundError:
             print(f"Error: Disease JSON file not found: {disease_json_file_path}")
             # Decide if this is a fatal error or if you can continue
             db.close()
             return
        except json.JSONDecodeError as e:
            print(f"Error decoding Disease JSON: {e}")
            db.close()
            return
        except Exception as e:
            print(f"An error occurred during disease data import: {e}")
            db.close()
            return


        print("\nImport from JSONs complete.")

    except Exception as e:
        print(f"An unexpected error occurred during the JSON import process: {e}")
    finally:
        db.close() # Ensure the connection is closed



# --- New Diagnosis Function ---

def diagnose_from_symptoms(db_path, reported_symptoms):
    """
    Diagnoses potential diseases based on a list of reported symptoms and
    predicts additional relevant symptoms for the top diagnoses.

    A disease is considered a potential diagnosis if at least one of its
    condition groups (AND sets) has one or more symptoms present in the
    reported symptoms list.

    The score for a disease is the percentage of symptoms in its *best-matching*
    condition group (the one with the highest count of reported symptoms) that
    are present in the reported symptoms list.

    Predicted symptoms are those from the rules of the top 5 scoring diseases
    that were NOT in the reported symptoms list. They are scored by frequency
    across the rules of the top 5 diseases, with a boost for symptoms
    present in the rules of the highest-scoring disease.

    Args:
        db_path (str): Path to the SQLite database file.
        reported_symptoms (list[str]): A list of symptom descriptions reported by the user.

    Returns:
        tuple: A tuple containing two elements:
               - list[dict]: A list of dictionaries for potential diagnoses,
                             each containing 'name' (disease name) and 'score' (percentage),
                             sorted by score in descending order.
               - list[dict]: A list of dictionaries for predicted symptoms,
                             each containing 'symptom' (symptom name) and 'score' (boosted count),
                             sorted by score in descending order.
               Returns ([], []) if no potential diseases are found or on error.
    """

    if str(type(db_path)) == str(HeartDiagnosisDB):
        db = db_path
    else:
        db_file_path = Path(db_path)
        if not db_file_path.exists():
            print(f"Error: Database file not found at {db_file_path}")
            return None  # Return empty lists on error
        db = HeartDiagnosisDB(db_file_path)


    if db.conn is None:
        print("Failed to connect to the database. Aborting diagnosis.")
        return [], [] # Return empty lists on error
    potential_diagnoses = []
    reported_symptoms_set = set(reported_symptoms) # Use a set for faster lookups

    try: # Start try block for database operations
        diseases = db.get_all_diseases() # Get all diseases to iterate through

        print(f"\nDiagnosing based on reported symptoms: {reported_symptoms}")

        # --- Phase 1: Find Potential Diagnoses and Scores ---
        for disease_id, disease_name, description in diseases:
            rules = db.get_rules_for_disease(disease_name) # Get rules for the current disease

            if not rules:
                continue

            max_matched_symptoms_in_any_group = 0
            best_matching_group_size = 0

            for condition_group in rules:
                if not condition_group:
                    continue

                matched_count = 0
                for symptom in condition_group:
                    if symptom in reported_symptoms_set:
                        matched_count += 1

                if matched_count > max_matched_symptoms_in_any_group:
                    max_matched_symptoms_in_any_group = matched_count
                    best_matching_group_size = len(condition_group)

            # If at least one symptom matched in the best group for this disease
            if max_matched_symptoms_in_any_group > 0:
                score = (max_matched_symptoms_in_any_group / best_matching_group_size) * 100 if best_matching_group_size > 0 else 0

                potential_diagnoses.append({
                    "name": disease_name,
                    "score": round(score, 2)
                })

        # Sort potential diagnoses by score in descending order
        potential_diagnoses.sort(key=lambda x: x['score'], reverse=True)

        print(f"Found {len(potential_diagnoses)} potential diagnoses.")

        # --- Phase 2: Predict Additional Symptoms for Top 5 Diseases with Boost ---
        predicted_symptom_scores = defaultdict(float) # Use float for scores
        predicted_symptom_base_counts = defaultdict(int) # To count occurrences without boost

        top_n_diseases = potential_diagnoses[:5] # Get the top 5 diseases

        top_disease_name = top_n_diseases[0]['name'] if top_n_diseases else None
        top_disease_rules = db.get_rules_for_disease(top_disease_name) if top_disease_name else []
        top_disease_symptoms_in_rules = set()
        for group in top_disease_rules:
            top_disease_symptoms_in_rules.update(group)


        if top_n_diseases:
            print(f"\nPredicting additional symptoms for the top {min(5, len(top_n_diseases))} diseases with boost for top disease symptoms:")
            # Define a boost value - this can be tuned
            BOOST_VALUE = 10 # Example boost value

            # First, calculate base counts for symptoms in top N diseases' rules
            for diagnosis in top_n_diseases:
                disease_name = diagnosis['name']
                rules = db.get_rules_for_disease(disease_name)

                for condition_group in rules:
                    for symptom in condition_group:
                        if symptom not in reported_symptoms_set:
                            predicted_symptom_base_counts[symptom] += 1

            # Then, apply the boost to the scores based on base counts and top disease relevance
            for symptom, base_count in predicted_symptom_base_counts.items():
                 predicted_symptom_scores[symptom] = base_count # Start score with base count

                 # Add boost only once if the symptom is in the top disease's rules
                 if symptom in top_disease_symptoms_in_rules:
                     predicted_symptom_scores[symptom] += BOOST_VALUE


        else:
             print("\nNo top diseases found to predict additional symptoms.")


        # Convert predicted symptom scores to a list of dicts and sort
        predicted_symptoms_list = [{"symptom": symptom, "score": score} for symptom, score in predicted_symptom_scores.items()]
        predicted_symptoms_list.sort(key=lambda x: x['score'], reverse=True)

        print(f"Predicted {len(predicted_symptoms_list)} additional symptoms.")


        return potential_diagnoses, predicted_symptoms_list # Return both lists

    except Exception as e:
        print(f"An error occurred during the diagnosis process: {e}")
        return [], [] # Return empty lists on error
    finally:
        if db != db_path and db.conn:
            db.close()





# --- Example Usage ---

if __name__ == "__main__":
    # Define file paths
    # db_file = "heart_data_full.db"
    # rules_csv = "dataset.csv" # Using the first format for rules
    # descriptions_csv = "symptom_Description.csv"
    # actions_csv = "symptom_precaution.csv"
    # severity_csv = "Symptom-severity.csv"
    # output_json_file = 'db.json'
    # Define file paths for dummy data and output
    new_db_file = "heart_data_from_json.db" # The new database file
    diseases,symptoms = diagnose_from_symptoms(new_db_file,
         ["vomiting","yellowing_of_eyes","yellowish_skin","abdominal_pain","loss_of_appetite","nausea"])
    print(diseases)
    print(symptoms)
    # # --- Step 1: Dump data from the original DB to JSONs ---
    # print("--- Dumping data to JSON files ---")
    # if Path(original_db_file).exists():
    #     dump_full_disease_data_to_json(original_db_file, disease_json_output)
    #     dump_symptom_severity_to_json(original_db_file, symptom_json_output)
    # else:
    #     print(f"Original database file '{original_db_file}' not found. Cannot dump to JSON.")
    #     # You might want to create a dummy DB here for testing if the original doesn't exist
    #     # For this example, we'll just stop.
    #
"""
    # --- Step 2: Import data from JSONs into a new DB ---
    print("\n--- Importing data from JSON files into a new DB ---")
    if Path(disease_json_output).exists() and Path(symptom_json_output).exists():
         import_data_from_json_to_db(disease_json_output, symptom_json_output, new_db_file)
    else:
         print("Required JSON files not found. Cannot import to new DB.")


    # --- Verify the imported data in the new DB (optional) ---
    print("\n--- Verifying Imported Data in New DB ---")
    verify_db = HeartDiagnosisDB(new_db_file)
    if verify_db.conn:
        print("\nDiseases in NEW DB (with descriptions):")
        for d_id, name, desc in verify_db.get_all_diseases():
            print(f"ID: {d_id}, Name: {name}, Description: {desc}")

        print("\nSymptoms in NEW DB (with severity):")
        for s_id, desc, severity in verify_db.get_all_symptoms():
            print(f"ID: {s_id}, Description: {desc}, Severity: {severity}")

        print("\nActions for Angina (from NEW DB):")
        print(verify_db.get_disease_actions("Angina"))

        print("\nRules for Myocardial Infarction (from NEW DB):")
        mi_rules = verify_db.get_rules_for_disease("Myocardial Infarction")
        if mi_rules:
             print("Myocardial Infarction rules imported:")
             for i, condition_group in enumerate(mi_rules):
                 if i > 0:
                     print("OR")
                 print(f"  (ALL of: {', '.join(condition_group)})")
        else:
            print("No rules found for Myocardial Infarction in NEW DB.")


        verify_db.close()
    else:
        print("Could not connect to NEW DB for verification.")
"""
"""
    # --- Perform the full import ---
    import_all_data_from_csvs(db_file, rules_csv, descriptions_csv, actions_csv, severity_csv)
    import_associations_from_csv(db_file,"clean.data.csv")
    # import_associations_from_csv(db_file,"improved_disease_dataset.csv")

    # --- Verify the imported data (optional) ---
    print("\n--- Verifying Full Imported Data ---")
    verify_db = HeartDiagnosisDB(db_file)
    if verify_db.conn:
        print("\nDiseases in DB (with descriptions):")
        for d_id, name, desc in verify_db.get_all_diseases():
            print(f"ID: {d_id}, Name: {name}, Description: {desc}")

        print("\nSymptoms in DB (with severity):")
        for s_id, desc, severity in verify_db.get_all_symptoms():
            print(f"ID: {s_id}, Description: {desc}, Severity: {severity}")

        print("\nActions for Angina:")
        print(verify_db.get_disease_actions("Angina"))

        print("\nRules for Myocardial Infarction:")
        mi_rules = verify_db.get_rules_for_disease("Myocardial Infarction")
        if mi_rules:
             print("Myocardial Infarction rules imported:")
             for i, condition_group in enumerate(mi_rules):
                 if i > 0:
                     print("OR")
                 print(f"  (ALL of: {', '.join(condition_group)})")
             print(f"(Expected 2 unique condition groups, got {len(mi_rules)})")

        verify_db.close()
    else:
        print("Could not connect to DB for verification.")
"""


