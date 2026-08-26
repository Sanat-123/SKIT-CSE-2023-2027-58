"""
============================================================
UNISCHED AI - UNIVERSAL FREE SLOT CHATBOT
============================================================

User uploads:
    PDF
    XLSX
    XLS
    CSV

The application:
    1. Imports the file
    2. Detects the timetable structure
    3. Creates canonical records
    4. Builds the availability engine
    5. Accepts natural-language questions
    6. Returns timetable/free-slot answers

============================================================
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st


# ============================================================
# PROJECT ROOT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT)
    )


# ============================================================
# PROJECT IMPORTS
# ============================================================

from import_engine.import_manager import ImportManager

from data_engine.canonical_event_matcher import (
    CanonicalEventMatcher
)

from query_engine import (
    QueryEngine,
    NaturalLanguageQuery
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="UniSched AI",
    page_icon="🎓",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("🎓 UniSched AI")

st.subheader(
    "AI-Based Faculty & Classroom Free Slot Detection System"
)

st.write(
    "Upload a timetable PDF, Excel or CSV file and ask "
    "questions in natural language."
)


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_TYPES = [
    "pdf",
    "xlsx",
    "xls",
    "csv"
]


# ============================================================
# SESSION STATE
# ============================================================

if "records" not in st.session_state:
    st.session_state.records = []

if "matcher" not in st.session_state:
    st.session_state.matcher = None

if "engine" not in st.session_state:
    st.session_state.engine = None

if "nlp" not in st.session_state:
    st.session_state.nlp = None

if "file_name" not in st.session_state:
    st.session_state.file_name = ""

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📁 Timetable Upload")

    uploaded_file = st.file_uploader(
        "Upload timetable",
        type=SUPPORTED_TYPES
    )

    st.markdown("---")

    st.markdown(
        """
### Supported files

- PDF
- Excel (.xlsx)
- Excel (.xls)
- CSV

### Example questions

- Who is free on Monday slot 2?
- Which faculty is free on Monday slot 3?
- Is Dr. Mehul Mahrishi free on Monday slot 3?
- What is Dr. Mehul Mahrishi teaching on Monday?
- Who teaches OS III?
- What is the timetable of 3CS-D on Monday?
- Which room is free on Monday slot 4?
        """
    )


# ============================================================
# FILE PROCESSING FUNCTION
# ============================================================

def process_uploaded_file(uploaded_file):

    """
    Save uploaded Streamlit file temporarily and process it
    through the existing ImportManager.
    """

    suffix = Path(
        uploaded_file.name
    ).suffix

    temp_path = None

    try:

        # ----------------------------------------------------
        # Create temporary file
        # ----------------------------------------------------

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_file:

            temp_file.write(
                uploaded_file.getbuffer()
            )

            temp_path = temp_file.name


        # ----------------------------------------------------
        # Import
        # ----------------------------------------------------

        manager = ImportManager()

        result = manager.import_file(
            temp_path
        )


        # ----------------------------------------------------
        # Handle ImportManager result
        # ----------------------------------------------------

        if isinstance(result, dict):

            if not result.get(
                "success",
                False
            ):

                return {
                    "success": False,
                    "message": result.get(
                        "error",
                        "File import failed."
                    ),
                    "records": []
                }

            records = result.get(
                "records",
                []
            )

            warnings = result.get(
                "warnings",
                []
            )

        else:

            records = result

            warnings = []


        # ----------------------------------------------------
        # Validate records
        # ----------------------------------------------------

        if not records:

            return {
                "success": False,
                "message": (
                    "The file was imported but "
                    "no timetable records were found."
                ),
                "records": []
            }


        # ----------------------------------------------------
        # Canonical matching
        # ----------------------------------------------------

        matcher = CanonicalEventMatcher(
            records
        )

        matcher.match()


        # ----------------------------------------------------
        # Query engine
        # ----------------------------------------------------

        engine = QueryEngine(
            matcher
        )

        nlp = NaturalLanguageQuery(
            engine
        )


        return {
            "success": True,
            "records": records,
            "matcher": matcher,
            "engine": engine,
            "nlp": nlp,
            "warnings": warnings
        }


    except Exception as e:

        return {
            "success": False,
            "message": str(e),
            "records": []
        }


    finally:

        # ----------------------------------------------------
        # Remove temporary file
        # ----------------------------------------------------

        if temp_path:

            try:
                os.remove(
                    temp_path
                )
            except Exception:
                pass


# ============================================================
# PROCESS UPLOAD
# ============================================================

if uploaded_file:

    if (
        st.session_state.file_name
        != uploaded_file.name
    ):

        with st.spinner(
            "Processing timetable..."
        ):

            result = process_uploaded_file(
                uploaded_file
            )


        if result["success"]:

            st.session_state.records = (
                result["records"]
            )

            st.session_state.matcher = (
                result["matcher"]
            )

            st.session_state.engine = (
                result["engine"]
            )

            st.session_state.nlp = (
                result["nlp"]
            )

            st.session_state.file_name = (
                uploaded_file.name
            )

            st.session_state.messages = []


            st.success(
                f"Successfully loaded: "
                f"{uploaded_file.name}"
            )


            # ------------------------------------------------
            # Statistics
            # ------------------------------------------------

            matcher = (
                st.session_state.matcher
            )

            col1, col2, col3, col4 = st.columns(4)


            with col1:

                st.metric(
                    "Imported Records",
                    len(
                        st.session_state.records
                    )
                )


            with col2:

                st.metric(
                    "Canonical Events",
                    len(
                        matcher.events
                    )
                )


            with col3:

                st.metric(
                    "Faculty Free Slots",
                    len(
                        matcher.faculty_free_slots
                    )
                )


            with col4:

                st.metric(
                    "Room Free Slots",
                    len(
                        matcher.room_free_slots
                    )
                )


            # ------------------------------------------------
            # Warnings
            # ------------------------------------------------

            warnings = result.get(
                "warnings",
                []
            )

            if warnings:

                with st.expander(
                    "⚠️ Import warnings"
                ):

                    for warning in warnings:

                        st.warning(
                            warning
                        )


        else:

            st.error(
                "❌ File processing failed"
            )

            st.error(
                result.get(
                    "message",
                    "Unknown error"
                )
            )


# ============================================================
# DATASET STATUS
# ============================================================

if st.session_state.nlp:

    st.markdown("---")

    st.subheader(
        "📊 Dataset Information"
    )

    records = (
        st.session_state.records
    )

    matcher = (
        st.session_state.matcher
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        st.write(
            "**File:**"
        )

        st.write(
            st.session_state.file_name
        )

    with col2:

        st.write(
            "**Records:**"
        )

        st.write(
            len(records)
        )

    with col3:

        st.write(
            "**Scheduled Events:**"
        )

        st.write(
            len(matcher.events)
        )


# ============================================================
# CHATBOT
# ============================================================

if st.session_state.nlp:

    st.markdown("---")

    st.header(
        "💬 Ask UniSched AI"
    )


    # --------------------------------------------------------
    # Display previous messages
    # --------------------------------------------------------

    for message in st.session_state.messages:

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )


    # --------------------------------------------------------
    # Chat input
    # --------------------------------------------------------

    prompt = st.chat_input(
        "Ask a timetable question..."
    )


    if prompt:

        # ----------------------------------------------------
        # Display user message
        # ----------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )


        with st.chat_message(
            "user"
        ):

            st.markdown(
                prompt
            )


        # ----------------------------------------------------
        # Generate answer
        # ----------------------------------------------------

        with st.chat_message(
            "assistant"
        ):

            with st.spinner(
                "Analyzing timetable..."
            ):

                try:

                    answer = (
                        st.session_state
                        .nlp
                        .answer(prompt)
                    )

                except Exception as e:

                    answer = (
                        "I could not process "
                        "that question.\n\n"
                        f"Error: `{e}`"
                    )


            st.markdown(
                answer
            )


        # ----------------------------------------------------
        # Save answer
        # ----------------------------------------------------

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer
            }
        )


# ============================================================
# NO FILE MESSAGE
# ============================================================

else:

    st.info(
        "👈 Upload a timetable file from the sidebar "
        "to start chatting."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "UniSched AI | AI-Based Faculty & Classroom "
    "Free Slot Detection System"
)