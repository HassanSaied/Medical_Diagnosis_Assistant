# Medical Diagnosis Assistant

A Streamlit-based web application that assists in medical diagnosis by analyzing reported symptoms and predicting potential heart-related conditions. The application uses a rule-based expert system to match symptoms with potential diseases and suggests relevant symptoms to help narrow down the diagnosis.

## Features

- **Interactive Symptom Checker**: Users can select symptoms from a comprehensive list
- **Intelligent Diagnosis**: System predicts potential heart conditions based on reported symptoms
- **Symptom Severity Analysis**: Symptoms are weighted by severity for more accurate diagnosis
- **User-friendly Interface**: Clean, intuitive web interface built with Streamlit
- **Data-driven**: Backed by a SQLite database containing medical knowledge base

## Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Medical_Diagnosis_Assistant
   ```

2. **Create and activate a virtual environment (recommended)**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install the required packages**:
   ```bash
   pip install -r requirements.txt
   ```
   
   If requirements.txt doesn't exist, install the following packages:
   ```bash
   pip install streamlit pandas numpy
   ```

## Database Setup

The application uses a SQLite database (`heart_data_from_json.db`) that should be included in the project. If you need to recreate or update the database:

1. Ensure you have the required JSON data files:
   - Disease data (rules, descriptions, actions)
   - Symptom severity data

2. Run the database initialization script (if available) or start the application to create the database schema.

## Running the Application

1. **Start the Streamlit app**:
   ```bash
   streamlit run gui.py
   ```

2. The application will start and automatically open in your default web browser. If it doesn't, navigate to:
   ```
   http://localhost:8501
   ```

## How to Use

1. **Select Symptoms**:
   - Choose symptoms from the dropdown menu
   - Selected symptoms will appear in the "Selected Symptoms" section
   - Remove symptoms by clicking the '×' button next to them

2. **Get Diagnosis**:
   - Click the "Diagnose" button to analyze the selected symptoms
   - The system will display potential conditions based on your symptoms

3. **Review Results**:
   - View the list of potential conditions with confidence scores
   - See additional symptoms that might help narrow down the diagnosis
   - Each symptom shows its severity level (color-coded)

## Project Structure

- `gui.py`: Main Streamlit application interface
- `database.py`: Database operations and diagnosis logic
- `heart_data_from_json.db`: SQLite database containing medical knowledge
- `requirements.txt`: Python package dependencies

## Data Model

The application uses a relational database with the following key tables:

- **diseases**: Stores information about different medical conditions
- **symptoms**: Contains symptom definitions and severity levels
- **disease_rules**: Defines the relationship between diseases and symptoms
- **condition_groups**: Groups of symptoms that together indicate a condition
- **disease_actions**: Recommended actions for each disease

## Customization

To customize the application:

1. **Update the knowledge base**:
   - Modify the database directly or through the provided import functions
   - Use `import_data_from_json_to_db()` to update disease and symptom data

2. **Modify the interface**:
   - Edit `gui.py` to change the layout and functionality
   - Update the color scheme and styling in the Streamlit components

## Troubleshooting

- If the application fails to start, ensure all dependencies are installed
- Check that the database file exists and is accessible
- Verify that the database schema matches what's expected by the application
- Check the console for any error messages

## License

[Specify your license here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This application is for educational and informational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions you may have regarding a medical condition.
