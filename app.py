"""
============================================================
UNISCHED AI - UNIVERSAL FREE SLOT CHATBOT
============================================================

User uploads one or more timetable files:
    PDF
    XLSX
    XLS
    CSV

The application:
    1. Imports every uploaded file
    2. Detects each file's timetable structure
    3. Combines all imported records into one dataset
    4. Creates canonical records from the combined dataset
    5. Builds ONE availability engine over that dataset
    6. Hands that SAME canonical dataset to a FacultyAIChatbot
       instance (scheduling/workload/absence/lab-shift/
       what-if/exam-duty), without importing the uploaded
       files a second time
    7. Accepts natural-language questions
    8. Returns timetable/free-slot answers, or, once the
       richer engine is ready, absence/replacement,
       multi-absence, lab-shifting, what-if, and exam-duty
       answers too - proposals always wait for an explicit
       follow-up "confirm" before anything is persisted.

============================================================
"""

from __future__ import annotations

import os
import sys
import shutil
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

from faculty_chatbot import FacultyAIChatbot


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
    "Upload one or more timetable PDF, Excel or CSV files "
    "and ask questions in natural language."
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

if "chatbot" not in st.session_state:
    # The richer FacultyAIChatbot instance (workload, absence,
    # multi-absence, lab-shifting, what-if, exam duty), built
    # from the SAME canonical matcher as st.session_state.matcher
    # above - see build_combined_dataset(). None until a
    # dataset has been loaded and the engine has finished
    # constructing successfully.
    st.session_state.chatbot = None

if "chatbot_error" not in st.session_state:
    # Set if FacultyAIChatbot construction fails, so the UI can
    # explain why only read-only timetable queries are available
    # (via st.session_state.nlp) instead of the full engine.
    st.session_state.chatbot_error = None

if "file_names" not in st.session_state:
    st.session_state.file_names = []

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("📁 Timetable Upload")

    uploaded_files = st.file_uploader(
        "Upload timetable(s)",
        type=SUPPORTED_TYPES,
        accept_multiple_files=True
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

### Once the full engine is ready

- What is the workload of \\<faculty\\> on Monday?
- \\<Faculty\\> is absent on Monday, who can replace them?
- What if \\<faculty\\> is absent on Thursday?
- Shift the lab in room \\<room\\> to another room on \\<day\\>
- Suggest 2 faculty for exam duty on \\<date\\> from
  \\<time\\> to \\<time\\>

Any of these that produce a proposal will ask you to reply
"confirm" before anything is actually saved.
        """
    )


# ============================================================
# FILE PROCESSING FUNCTION
# ============================================================

def import_single_file(uploaded_file):

    """
    Save ONE uploaded Streamlit file temporarily and import it
    through the existing ImportManager.

    This function only performs the IMPORT step for a single
    file. It deliberately does NOT build a CanonicalEventMatcher
    or QueryEngine -- that happens once, after every uploaded
    file's records have been combined (see
    build_combined_dataset() below).

    IMPORTANT: the temporary file is written using the file's
    ORIGINAL name, not a randomly generated one. CanonicalEvent-
    Matcher.identify_source() classifies a record's source
    (facultywise / classwise / location-wise) by looking for
    those words in the "source_file" field, which is derived
    directly from this path's filename. A randomized temp name
    would make every uploaded PDF look like an unclassified
    generic "PDF" source, which silently breaks faculty/class/
    room free-slot detection even though the file imports
    "successfully".
    """

    temp_dir = None

    temp_path = None

    try:

        # ----------------------------------------------------
        # Create a fresh temp directory and write the file
        # there under its ORIGINAL name.
        # ----------------------------------------------------

        temp_dir = tempfile.mkdtemp()

        temp_path = str(
            Path(
                temp_dir
            ) / uploaded_file.name
        )

        with open(
            temp_path,
            "wb"
        ) as temp_file:

            temp_file.write(
                uploaded_file.getbuffer()
            )


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
                    "records": [],
                    "warnings": []
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
                "records": [],
                "warnings": warnings
            }

        return {
            "success": True,
            "records": records,
            "warnings": warnings
        }


    except Exception as e:

        return {
            "success": False,
            "message": str(e),
            "records": [],
            "warnings": []
        }


    finally:

        # ----------------------------------------------------
        # Remove temporary directory (and the file in it)
        # ----------------------------------------------------

        if temp_dir:

            try:
                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True
                )
            except Exception:
                pass


# ============================================================
# COMBINE MULTIPLE UPLOADED FILES INTO ONE DATASET
# ============================================================

def build_combined_dataset(uploaded_files):

    """
    Import EVERY uploaded file, combine all of their records
    into a single list, and build exactly ONE
    CanonicalEventMatcher / QueryEngine / NaturalLanguageQuery
    over that combined list.

    A single uploaded file is simply the special case of this
    same code path with one file in the list -- there is no
    separate single-file pipeline.
    """

    all_records = []

    all_warnings = []

    file_reports = []

    for uploaded_file in uploaded_files:

        file_result = import_single_file(
            uploaded_file
        )

        if file_result["success"]:

            all_records.extend(
                file_result["records"]
            )

            file_reports.append(
                {
                    "name": uploaded_file.name,
                    "success": True,
                    "record_count": len(
                        file_result["records"]
                    ),
                }
            )

            for warning in file_result.get(
                "warnings",
                []
            ):

                all_warnings.append(
                    f"{uploaded_file.name}: {warning}"
                )

        else:

            file_reports.append(
                {
                    "name": uploaded_file.name,
                    "success": False,
                    "message": file_result.get(
                        "message",
                        "Unknown error"
                    ),
                }
            )


        # ------------------------------------------------
        # No records from ANY uploaded file.
        # ------------------------------------------------

    if not all_records:

        return {
            "success": False,
            "message": (
                "None of the uploaded files produced any "
                "timetable records."
            ),
            "records": [],
            "file_reports": file_reports,
        }


    # ----------------------------------------------------
    # Canonical matching -- ONE matcher over ALL combined
    # records from every uploaded file.
    # ----------------------------------------------------

    matcher = CanonicalEventMatcher(
        all_records
    )

    matcher.match()


    # ----------------------------------------------------
    # Query engine -- ONE engine / ONE NLP layer over the
    # combined dataset.
    # ----------------------------------------------------

    engine = QueryEngine(
        matcher
    )

    nlp = NaturalLanguageQuery(
        engine
    )


    return {
        "success": True,
        "records": all_records,
        "matcher": matcher,
        "engine": engine,
        "nlp": nlp,
        "warnings": all_warnings,
        "file_reports": file_reports,
    }


# ============================================================
# PROPOSAL / CONFIRMATION RESPONSE STYLING
#
# FacultyAIChatbot.process_query() already follows PLAN ->
# VALIDATE -> CONFIRM internally (see scheduling/*_planner.py /
# *_coordinator.py) and returns a plain-text answer either way -
# it never persists anything on a plan/proposal request, only on
# an explicit follow-up "confirm". These two small helpers only
# affect how that same text is DISPLAYED, so a proposal awaiting
# confirmation and an already-confirmed/persisted change are
# visually easy to tell apart. They never change what gets
# persisted.
# ============================================================

def _classify_chatbot_response(text):

    if not text:
        return "info"

    first_line = text.strip().splitlines()[0].strip().lower()

    if first_line.startswith("confirmed"):
        return "confirmed"

    if (
        first_line.startswith("proposed")
        or '"confirm"' in text.lower()
    ):
        return "proposal"

    return "info"


def _render_assistant_message(text):

    kind = _classify_chatbot_response(text)

    if kind == "confirmed":

        st.success(text)

    elif kind == "proposal":

        st.info(text)

        st.caption(
            "⏳ This is a proposal only - nothing has been "
            "saved yet. Reply \"confirm\" to apply it."
        )

    else:

        st.markdown(text)


# ============================================================
# PROCESS UPLOAD
# ============================================================

if uploaded_files:

    current_file_names = [
        uploaded_file.name
        for uploaded_file in uploaded_files
    ]

    if (
        st.session_state.file_names
        != current_file_names
    ):

        with st.spinner(
            f"Processing {len(uploaded_files)} "
            f"timetable file(s)..."
        ):

            result = build_combined_dataset(
                uploaded_files
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

            st.session_state.file_names = (
                current_file_names
            )

            st.session_state.messages = []


            # ------------------------------------------------
            # FULL UNISCHED AI ENGINE
            #
            # Reuses the SAME CanonicalEventMatcher just built
            # above from the uploaded files - FacultyAIChatbot
            # is never given the raw uploaded files itself, so
            # ImportManager never runs a second time over them.
            # This is what exposes workload / absence /
            # multi-absence / lab-shifting / what-if / exam-duty
            # in the web UI, on top of the same canonical
            # dataset the read-only timetable queries already
            # use.
            # ------------------------------------------------

            try:

                st.session_state.chatbot = FacultyAIChatbot(
                    matcher=st.session_state.matcher
                )

                st.session_state.chatbot_error = None

            except Exception as e:

                # Read-only timetable queries
                # (st.session_state.nlp) still work even if the
                # richer engine fails to build - see the
                # DATASET STATUS / chat sections below.
                st.session_state.chatbot = None

                st.session_state.chatbot_error = str(e)


            st.success(
                f"Successfully loaded "
                f"{len(current_file_names)} file(s): "
                + ", ".join(current_file_names)
            )


            # ------------------------------------------------
            # Per-file import report
            # ------------------------------------------------

            file_reports = result.get(
                "file_reports",
                []
            )

            failed_reports = [
                report
                for report in file_reports
                if not report["success"]
            ]

            with st.expander(
                f"📄 File details "
                f"({len(file_reports)} uploaded)"
            ):

                for report in file_reports:

                    if report["success"]:

                        st.write(
                            f"✅ **{report['name']}** — "
                            f"{report['record_count']} "
                            f"record(s) imported"
                        )

                    else:

                        st.write(
                            f"❌ **{report['name']}** — "
                            f"{report['message']}"
                        )

            if failed_reports:

                st.warning(
                    f"{len(failed_reports)} of "
                    f"{len(file_reports)} file(s) could "
                    f"not be imported. See file details "
                    f"above."
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

            file_reports = result.get(
                "file_reports",
                []
            )

            if file_reports:

                with st.expander(
                    "📄 File details"
                ):

                    for report in file_reports:

                        if report["success"]:

                            st.write(
                                f"✅ **{report['name']}** — "
                                f"{report['record_count']} "
                                f"record(s) imported"
                            )

                        else:

                            st.write(
                                f"❌ **{report['name']}** — "
                                f"{report['message']}"
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
            f"**Files ({len(st.session_state.file_names)}):**"
        )

        for file_name in st.session_state.file_names:

            st.write(
                f"- {file_name}"
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
# ENGINE STATUS
#
# Small, simple status area (no dashboard/redesign) showing
# whether the full UNISCHED AI engine (FacultyAIChatbot -
# workload, absence, multi-absence, lab-shifting, what-if,
# exam duty) is ready, in addition to the always-available
# read-only timetable queries above.
# ============================================================

if st.session_state.nlp:

    st.markdown("---")

    st.subheader(
        "🧠 UniSched AI Engine Status"
    )

    if st.session_state.chatbot is not None:

        st.success(
            "Full engine ready - workload, absence/"
            "replacement, multi-absence, lab-shifting, "
            "what-if, and exam-duty requests are all "
            "available in the chat below, in addition to "
            "read-only timetable questions."
        )

    elif st.session_state.chatbot_error:

        st.warning(
            "The full scheduling engine could not be "
            "started, so only read-only timetable questions "
            "are available below.\n\n"
            f"Error: `{st.session_state.chatbot_error}`"
        )

    else:

        st.info(
            "Only read-only timetable questions are "
            "available below."
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

            if message["role"] == "assistant":

                _render_assistant_message(
                    message["content"]
                )

            else:

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
        #
        # Prefer the full FacultyAIChatbot (workload, absence,
        # multi-absence, lab-shifting, what-if, exam duty, and
        # read-only timetable queries all in one place) when it
        # is ready. Fall back to the read-only
        # NaturalLanguageQuery layer only if the full engine
        # could not be built for this dataset, so read-only
        # timetable questions keep working either way.
        # ----------------------------------------------------

        with st.chat_message(
            "assistant"
        ):

            with st.spinner(
                "Analyzing timetable..."
            ):

                try:

                    if st.session_state.chatbot is not None:

                        answer = (
                            st.session_state
                            .chatbot
                            .process_query(prompt)
                        )

                    else:

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


            _render_assistant_message(
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
        "👈 Upload one or more timetable files from the "
        "sidebar to start chatting."
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "UniSched AI | AI-Based Faculty & Classroom "
    "Free Slot Detection System"
)