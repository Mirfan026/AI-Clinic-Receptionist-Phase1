# Streamlit UI — AI Clinic Receptionist

## Run

```bash
pip install -r requirements-ui.txt
python -m streamlit run streamlit_app.py
```

Windows shortcut:

```text
run_demo.bat
```

The UI is intentionally presentation-only. It calls the existing `ClinicReceptionistAgent`; the agent owns routing, RAG, safety and tool orchestration, while the existing tools own database operations.

## Demo workflow

- Clinic-branded landing/header
- Multilingual chat: English, Urdu, Roman Urdu and mixed language
- Loading spinner during agent execution
- Workflow trace showing RAG vs controlled tools
- Retrieved source/grounding details
- Quick demo prompts
- Reset conversation
- Front-desk appointment/admin table using synthetic data
- Safety limitation messaging

## Layer boundary

```text
Streamlit UI
    -> ClinicReceptionistAgent
        -> RAG / controlled tools
            -> database/services
```

The Streamlit layer contains no SQL, prompt construction, retrieval logic, booking rules, or direct ORM manipulation for operational actions. The admin display reads the existing read-only data model for hackathon demonstration; production staff access must add authentication, authorization, audit logging, and tenant scoping.
