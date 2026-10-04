from __future__ import annotations

import hashlib
import os
import sys
import textwrap
import uuid

from html import escape
from pathlib import Path

import streamlit as st
from sqlalchemy import select


# ============================================================
# PROJECT ROOT
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(
    0,
    str(ROOT),
)

os.chdir(ROOT)


# ============================================================
# PROJECT IMPORTS
# ============================================================

from app.agent.agent import ClinicReceptionistAgent
from app.llm import GroqLLMService
from app.voice import GroqVoiceService

from app.database.connection import (
    get_engine,
    get_session_factory,
    initialize_database,
)

from app.database.models import Clinic
from app.rag.pipeline import RAGPipeline
from app.tools import TOOL_REGISTRY


# ============================================================
# CONFIGURATION
# ============================================================

CLINIC_ID = os.getenv(
    "DEFAULT_CLINIC_ID",
    "CLINIC-001",
)


st.set_page_config(
    page_title="Maple Crescent | AI Receptionist",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# HTML HELPER
# ============================================================

def render_html(
    content: str,
) -> None:

    cleaned = textwrap.dedent(
        content
    ).strip()

    st.html(cleaned)


# ============================================================
# CSS
# ============================================================

def css() -> None:

    render_html(
        """
        <style>

        .stApp {
            background:
                linear-gradient(
                    180deg,
                    #f6fbfa,
                    #ffffff 42%
                );
        }

        [data-testid="stSidebar"] {
            background: #f6fbfa;
            border-right: 1px solid #dce9e7;
        }

        .brand {
            padding: 6px 0 18px 0;
        }

        .mark {
            width: 48px;
            height: 48px;

            border-radius: 14px;

            background: #0f766e;
            color: white;

            display: flex;
            align-items: center;
            justify-content: center;

            font-size: 25px;
            font-weight: 800;

            box-shadow:
                0 5px 15px
                rgba(15, 118, 110, 0.15);
        }

        .title {
            font-size: 1.35rem;
            font-weight: 800;

            color: #16302f;

            margin-top: 10px;
        }

        .sub {
            color: #64748b;

            font-size: 0.82rem;

            margin-top: 2px;
        }

        .hero {
            background:
                linear-gradient(
                    135deg,
                    #ecfdf5,
                    #f0fdfa,
                    #ffffff
                );

            border: 1px solid #d7efeb;

            border-radius: 22px;

            padding: 25px 28px;

            margin-bottom: 20px;
        }

        .hero h1 {
            margin: 12px 0 0 0;

            color: #16302f;

            font-size: 2rem;
        }

        .hero p {
            margin: 0.5rem 0 0 0;

            color: #526766;

            max-width: 900px;

            line-height: 1.6;
        }

        .pill {
            display: inline-block;

            padding: 5px 10px;

            border-radius: 999px;

            background: #dff7f2;

            color: #0f766e;

            font-size: 0.75rem;
            font-weight: 700;

            margin-right: 5px;
            margin-bottom: 5px;
        }

        .workflow {
            border: 1px solid #e2eceb;

            border-radius: 14px;

            padding: 10px 13px;

            margin: 8px 0;

            background: #ffffff;

            color: #48615f;

            font-size: 0.80rem;
        }

        .source {
            background: #f8fafc;

            border: 1px solid #e8eef2;

            border-radius: 9px;

            padding: 7px 9px;

            margin: 4px 0;

            font-size: 0.76rem;
        }

        .status-ok {
            background: #ecfdf5;

            border: 1px solid #a7f3d0;

            border-radius: 10px;

            color: #047857;

            padding: 8px 10px;

            margin-bottom: 7px;

            font-size: 0.78rem;
            font-weight: 600;
        }

        .status-off {
            background: #fff7ed;

            border: 1px solid #fed7aa;

            border-radius: 10px;

            color: #9a3412;

            padding: 8px 10px;

            margin-bottom: 7px;

            font-size: 0.78rem;
            font-weight: 600;
        }

        .voice-box {
            background: #f8fafc;

            border: 1px solid #dbe7e5;

            border-radius: 16px;

            padding: 12px 15px;

            margin-top: 12px;
            margin-bottom: 8px;
        }

        .voice-title {
            color: #16302f;

            font-size: 0.95rem;

            font-weight: 700;
        }

        .voice-help {
            color: #64748b;

            font-size: 0.76rem;

            margin-top: 4px;
        }

        .footer {
            color: #94a3b8;

            text-align: center;

            font-size: 0.74rem;

            padding: 30px 20px 15px 20px;
        }

        </style>
        """
    )


# ============================================================
# RAG
# ============================================================

@st.cache_resource(
    show_spinner=False
)
def rag():

    pipeline = RAGPipeline()

    pipeline.ensure_index(
        ROOT
        / "data"
        / "production"
        / "knowledge"
        / "documents",
        CLINIC_ID,
    )

    return pipeline


# ============================================================
# GROQ LLM
# ============================================================

def llm_enabled() -> bool:

    value = os.getenv(
        "ENABLE_LLM",
        "true",
    )

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@st.cache_resource(
    show_spinner=False
)
def groq_llm():

    if not llm_enabled():
        return None

    if not os.getenv(
        "GROQ_API_KEY"
    ):
        return None

    try:

        return GroqLLMService()

    except Exception:

        return None


# ============================================================
# GROQ VOICE
# ============================================================

def voice_enabled() -> bool:

    value = os.getenv(
        "ENABLE_VOICE",
        "true",
    )

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@st.cache_resource(
    show_spinner=False
)
def voice_service():

    if not voice_enabled():
        return None

    if not os.getenv(
        "GROQ_API_KEY"
    ):
        return None

    try:

        return GroqVoiceService()

    except Exception:

        return None


# ============================================================
# CLINIC AGENT
# ============================================================

@st.cache_resource(
    show_spinner=False
)
def agent():

    llm = groq_llm()

    response_generator = None

    if llm is not None:

        response_generator = (
            llm.polish_grounded_response
        )

    return ClinicReceptionistAgent(
        clinic_id=CLINIC_ID,
        rag=rag(),
        tools=TOOL_REGISTRY,
        response_generator=response_generator,
    )


# ============================================================
# DATABASE
# ============================================================

def ensure_db():

    initialize_database(
        get_engine()
    )

    Session = get_session_factory()

    with Session() as session:

        exists = session.scalar(
            select(
                Clinic
            ).where(
                Clinic.clinic_id
                == CLINIC_ID
            )
        )

    if not exists:

        from scripts.seed_database import seed

        seed()


def clinic():

    Session = get_session_factory()

    with Session() as session:

        return session.scalar(
            select(
                Clinic
            ).where(
                Clinic.clinic_id
                == CLINIC_ID
            )
        )


# ============================================================
# RESET CONVERSATION
# ============================================================

def reset():

    session_id = st.session_state.get(
        "sid"
    )

    receptionist = agent()

    if session_id:

        receptionist.sessions.pop(
            session_id,
            None,
        )

    st.session_state.sid = str(
        uuid.uuid4()
    )

    st.session_state.messages = []

    st.session_state.pending = None

    st.session_state.pending_source = None

    st.session_state.last_audio_hash = None

    st.session_state.voice_error = None

    # Remove old recorded audio from the widget if present.
    st.session_state.pop(
        "clinic_voice_input",
        None,
    )


# ============================================================
# SIDEBAR
# ============================================================

def sidebar(
    clinic_record,
):

    with st.sidebar:

        render_html(
            """
            <div class="brand">

                <div class="mark">
                    ✚
                </div>

                <div class="title">
                    Maple Crescent
                </div>

                <div class="sub">
                    AI Clinic Receptionist
                </div>

            </div>
            """
        )

        if clinic_record:

            st.caption(
                clinic_record.address
            )

            st.caption(
                f"☎ {clinic_record.phone}"
            )

            st.caption(
                f"✉ {clinic_record.email}"
            )

        st.divider()

        # ----------------------------------------------------
        # AI STATUS
        # ----------------------------------------------------

        st.markdown(
            "**AI status**"
        )

        if groq_llm() is not None:

            render_html(
                """
                <div class="status-ok">
                    ● Groq LLM connected
                </div>
                """
            )

        else:

            render_html(
                """
                <div class="status-off">
                    ● Groq LLM unavailable
                </div>
                """
            )

        if voice_service() is not None:

            render_html(
                """
                <div class="status-ok">
                    ● Voice transcription connected
                </div>
                """
            )

        else:

            render_html(
                """
                <div class="status-off">
                    ● Voice transcription unavailable
                </div>
                """
            )

        st.caption(
            "Voice converts speech to text. "
            "Your existing clinic agent still controls "
            "safety, RAG, availability and booking."
        )

        st.divider()

        # ----------------------------------------------------
        # CONVERSATION
        # ----------------------------------------------------

        st.markdown(
            "**Conversation**"
        )

        if st.button(
            "↻ Reset conversation",
            use_container_width=True,
        ):

            reset()

            st.rerun()

        # ----------------------------------------------------
        # DEMO PROMPTS
        # ----------------------------------------------------

        st.markdown(
            "**Try a demo prompt**"
        )

        prompts = [
            "What are your Saturday timings?",
            "Mujhe available doctors ke naam bata dein.",
            "What payment methods do you accept?",
            "Dr. Bilal ke liye cardiology appointment chahiye.",
        ]

        for index, demo_prompt in enumerate(
            prompts
        ):

            if st.button(
                demo_prompt,
                key=f"demo_prompt_{index}",
                use_container_width=True,
            ):

                st.session_state.pending = (
                    demo_prompt
                )

                st.session_state.pending_source = (
                    "demo"
                )

                st.rerun()

        st.divider()

        # ----------------------------------------------------
        # SAFETY
        # ----------------------------------------------------

        st.markdown(
            "**Safety**"
        )

        st.caption(
            "Administrative healthcare assistant — not a doctor."
        )

        st.caption(
            "Live appointment availability is checked "
            "from controlled database tools."
        )

        st.caption(
            "Voice does not have direct database access."
        )

        st.caption(
            "Voice recordings are sent to Groq "
            "for speech transcription."
        )


# ============================================================
# WORKFLOW TRACE
# ============================================================

def trace(
    response,
):

    # --------------------------------------------------------
    # TOOL WORKFLOW
    # --------------------------------------------------------

    if response.tool_calls:

        tool_names = " → ".join(
            escape(
                str(
                    call.get(
                        "tool",
                        "tool",
                    )
                )
            )
            for call
            in response.tool_calls
        )

        render_html(
            f"""
            <div class="workflow">

                <b>Workflow:</b>

                User
                →
                Agent
                →
                <b>{tool_names}</b>
                →
                Database
                →
                Response

            </div>
            """
        )

    # --------------------------------------------------------
    # RAG WORKFLOW
    # --------------------------------------------------------

    elif response.sources:

        if groq_llm() is not None:

            render_html(
                """
                <div class="workflow">

                    <b>Workflow:</b>

                    User
                    →
                    Agent
                    →
                    <b>RAG</b>
                    →
                    Knowledge Base
                    →
                    Groq wording layer
                    →
                    Response

                </div>
                """
            )

        else:

            render_html(
                """
                <div class="workflow">

                    <b>Workflow:</b>

                    User
                    →
                    Agent
                    →
                    <b>RAG</b>
                    →
                    Knowledge Base
                    →
                    Response

                </div>
                """
            )

    # --------------------------------------------------------
    # SOURCES
    # --------------------------------------------------------

    if response.sources:

        with st.expander(
            f"Sources & grounding ({len(response.sources)})"
        ):

            seen = set()

            for source in response.sources:

                key = (
                    source.get(
                        "source"
                    ),
                    source.get(
                        "document_type"
                    ),
                    source.get(
                        "language"
                    ),
                )

                if key in seen:
                    continue

                seen.add(
                    key
                )

                score = source.get(
                    "score"
                )

                score_text = ""

                if isinstance(
                    score,
                    (
                        int,
                        float,
                    ),
                ):

                    score_text = (
                        f" · score {score:.2f}"
                    )

                source_name = escape(
                    str(
                        source.get(
                            "source"
                        )
                        or "Clinic knowledge"
                    )
                )

                document_type = escape(
                    str(
                        source.get(
                            "document_type"
                        )
                        or "document"
                    )
                )

                source_language = escape(
                    str(
                        source.get(
                            "language"
                        )
                        or "unknown"
                    )
                )

                render_html(
                    f"""
                    <div class="source">

                        <b>{source_name}</b>

                        · {document_type}

                        · {source_language}

                        {score_text}

                    </div>
                    """
                )


# ============================================================
# VOICE INPUT
# ============================================================

def voice_input():

    render_html(
        """
        <div class="voice-box">

            <div class="voice-title">
                🎙️ Voice message
            </div>

            <div class="voice-help">
                Click the microphone and speak in
                English, Urdu, Roman Urdu, or mixed language.
            </div>

        </div>
        """
    )

    service = voice_service()

    if service is None:

        st.warning(
            "Voice input is currently unavailable. "
            "Check GROQ_API_KEY and ENABLE_VOICE."
        )

        return

    recorded_audio = st.audio_input(
        "Record your voice",
        sample_rate=16000,
        key="clinic_voice_input",
        help=(
            "Record your clinic question and stop "
            "the recording when you are finished."
        ),
    )

    if recorded_audio is None:

        return

    audio_bytes = (
        recorded_audio.getvalue()
    )

    if not audio_bytes:

        return

    # --------------------------------------------------------
    # PREVENT DUPLICATE PROCESSING
    # --------------------------------------------------------

    audio_hash = hashlib.sha256(
        audio_bytes
    ).hexdigest()

    if (
        audio_hash
        == st.session_state.get(
            "last_audio_hash"
        )
    ):

        return

    # Mark before calling the API.
    st.session_state.last_audio_hash = (
        audio_hash
    )

    try:

        with st.spinner(
            "Listening and transcribing your voice..."
        ):

            transcript = service.transcribe(
                audio_bytes,
                filename="clinic_voice.wav",
            )

        st.session_state.voice_error = None

        st.session_state.pending = (
            transcript
        )

        st.session_state.pending_source = (
            "voice"
        )

        # Rerun so the transcription enters the normal
        # chat processing flow.
        st.rerun()

    except Exception as exc:

        st.session_state.voice_error = (
            str(exc)
        )


# ============================================================
# MAIN USER APP
# ============================================================

def main():

    css()

    ensure_db()

    # --------------------------------------------------------
    # SESSION STATE
    # --------------------------------------------------------

    st.session_state.setdefault(
        "sid",
        str(
            uuid.uuid4()
        ),
    )

    st.session_state.setdefault(
        "messages",
        [],
    )

    st.session_state.setdefault(
        "pending",
        None,
    )

    st.session_state.setdefault(
        "pending_source",
        None,
    )

    st.session_state.setdefault(
        "last_audio_hash",
        None,
    )

    st.session_state.setdefault(
        "voice_error",
        None,
    )

    clinic_record = clinic()

    sidebar(
        clinic_record
    )

    # --------------------------------------------------------
    # HERO
    # --------------------------------------------------------

    render_html(
        """
        <div class="hero">

            <span class="pill">
                Multilingual
            </span>

            <span class="pill">
                Voice
            </span>

            <span class="pill">
                RAG + Tools
            </span>

            <span class="pill">
                Groq LLM
            </span>

            <span class="pill">
                Safe by design
            </span>

            <h1>
                AI Clinic Receptionist & Appointment Assistant
            </h1>

            <p>
                Type or speak your question about clinic timings,
                doctors, services, fees, appointment availability,
                or booking — in English, Urdu, Roman Urdu,
                or mixed language.
            </p>

        </div>
        """
    )

    # --------------------------------------------------------
    # CENTERED USER CHAT
    # --------------------------------------------------------

    left_space, chat_column, right_space = (
        st.columns(
            [
                0.12,
                0.76,
                0.12,
            ]
        )
    )

    with chat_column:

        if not st.session_state.messages:

            st.info(
                "👋 Welcome! Type a message or use "
                "the microphone to speak with the receptionist."
            )

        # ----------------------------------------------------
        # CHAT HISTORY
        # ----------------------------------------------------

        for message in st.session_state.messages:

            avatar = (
                "🏥"
                if message[
                    "role"
                ]
                == "assistant"
                else "🙂"
            )

            with st.chat_message(
                message[
                    "role"
                ],
                avatar=avatar,
            ):

                st.markdown(
                    message[
                        "content"
                    ]
                )

                if (
                    message.get(
                        "input_mode"
                    )
                    == "voice"
                ):

                    st.caption(
                        "🎙️ Transcribed from voice"
                    )

                response = message.get(
                    "response"
                )

                if response:

                    trace(
                        response
                    )

        # ----------------------------------------------------
        # MICROPHONE
        # ----------------------------------------------------

        voice_input()

        # ----------------------------------------------------
        # VOICE ERROR
        # ----------------------------------------------------

        if st.session_state.voice_error:

            st.error(
                "Voice transcription failed: "
                + st.session_state.voice_error
            )

        # ----------------------------------------------------
        # TEXT INPUT
        # ----------------------------------------------------

        typed_prompt = st.chat_input(
            "Type your message… English / اردو / Roman Urdu"
        )

        prompt = typed_prompt

        input_mode = "text"

        # ----------------------------------------------------
        # VOICE OR DEMO INPUT
        # ----------------------------------------------------

        if st.session_state.pending:

            prompt = (
                st.session_state.pending
            )

            source = (
                st.session_state.pending_source
            )

            if source == "voice":

                input_mode = "voice"

            elif source == "demo":

                input_mode = "demo"

            st.session_state.pending = None

            st.session_state.pending_source = None

        # ----------------------------------------------------
        # PROCESS MESSAGE THROUGH EXISTING SAFE AGENT
        # ----------------------------------------------------

        if prompt:

            prompt = str(
                prompt
            ).strip()

            if prompt:

                st.session_state.messages.append(
                    {
                        "role":
                            "user",

                        "content":
                            prompt,

                        "input_mode":
                            input_mode,
                    }
                )

                with st.spinner(
                    "Checking clinic information "
                    "and appointment data..."
                ):

                    response = agent().handle(
                        prompt,
                        st.session_state.sid,
                    )

                st.session_state.messages.append(
                    {
                        "role":
                            "assistant",

                        "content":
                            response.text,

                        "response":
                            response,
                    }
                )

                st.rerun()

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    render_html(
        """
        <div class="footer">

            Maple Crescent Family Clinic
            · AI Receptionist
            · Voice + Text
            · Administrative support only

        </div>
        """
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()