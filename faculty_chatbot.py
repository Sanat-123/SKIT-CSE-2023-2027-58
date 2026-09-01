import re
from datetime import datetime

from engine.query_tokenizer import QueryTokenizer
from engine.stopword_filter import StopWordFilter
from engine.day_slot_extractor import DaySlotExtractor
from engine.entity_extractor import EntityExtractor
from engine.intent_detector import IntentDetector
from engine.query_planner import QueryPlanner
from engine.response_generator import ResponseGenerator

from import_engine.import_manager import ImportManager
from data_engine.canonical_event_matcher import CanonicalEventMatcher
from scheduling.workload_engine import FacultyWorkloadEngine
from scheduling.absence_engine import FacultyAbsenceEngine
from scheduling.assignment_engine import FacultyAssignmentEngine
from query_engine import QueryEngine
from query_engine.natural_language_query import NaturalLanguageQuery



class FacultyAIChatbot:

    def __init__(self, files=None):

        print("\n" + "=" * 70)
        print("LOADING FACULTY AI KNOWLEDGE BASE")
        print("=" * 70)

        # --------------------------------------------------
        # FILES
        # --------------------------------------------------

        if files is None:
            files = [
                "data/Facultywise TT 20 sep.pdf",
                "data/classwise TT 27 sep.pdf",
                "data/Location wise TT 27 sep 2025.pdf",
                "data/timetable.xlsx",
                "data/test_timetable.csv"
            ]

        self.files = files

        # --------------------------------------------------
        # IMPORT DATA
        # --------------------------------------------------

        manager = ImportManager()

        all_records = []

        print("\nImporting timetable files...")

        for file_path in files:

            try:

                print(f"\nLoading: {file_path}")

                result = manager.import_file(file_path)

                if isinstance(result, dict):
                    records = result.get("records", [])
                else:
                    records = result

                print(
                    f"Imported: {len(records)} records"
                )

                all_records.extend(records)

            except Exception as e:

                print(
                    f"Warning: Could not import {file_path}"
                )

                print(e)

        print("\n" + "-" * 70)

        print(
            f"Total imported records: {len(all_records)}"
        )

        # --------------------------------------------------
        # CANONICAL MATCHING
        # --------------------------------------------------

        print("\nBuilding canonical timetable...")

        self.matcher = CanonicalEventMatcher(
            all_records
        )

        self.matcher.match()

        summary = self.matcher.summary()

        print(
            f"Canonical events: "
            f"{summary.get('canonical_events', len(self.matcher.events))}"
        )

        # --------------------------------------------------
        # QUERY ENGINE
        # --------------------------------------------------

        print("\nCreating Query Engine...")

        self.query_engine = QueryEngine(
            self.matcher
        )

        print("Query Engine ready.")

        # --------------------------------------------------
        # ENTITY EXTRACTOR
        #
        # Built AFTER the QueryEngine, from
        # query_engine.entity_knowledge() - the faculty/
        # subject/room/class/group names actually present in
        # the CURRENTLY loaded canonical timetable. This
        # replaces the previous dependency on a separate,
        # independently-built database/faculty.db snapshot,
        # which could silently drift out of sync with the
        # real data (confirmed: it was already missing real
        # entries such as "Dr. Nilam", "3CS", and "5CS").
        # If the timetable source files are replaced, entity
        # recognition now automatically reflects the new
        # data on the next FacultyAIChatbot() construction -
        # no separate database rebuild step required.
        # --------------------------------------------------

        self.extractor = EntityExtractor(
            knowledge=self.query_engine.entity_knowledge()
        )

        print("Entity Extractor ready.")

                # --------------------------------------------------
        # SCHEDULING ENGINES
        # --------------------------------------------------

        print("Creating Workload Engine...")

        self.workload_engine = FacultyWorkloadEngine(
            self.query_engine
        )

        print("Workload Engine ready.")

        print("Creating Absence Engine...")

        self.absence_engine = FacultyAbsenceEngine(
            self.query_engine
        )

        print("Absence Engine ready.")

        print("Creating Assignment Engine...")

        self.assignment_engine = FacultyAssignmentEngine(
            self.query_engine,
            self.absence_engine
        )

        print("Assignment Engine ready.")
        self.workload_engine = FacultyWorkloadEngine(
            self.query_engine
        )

        print("Workload Engine ready.")

        self.absence_engine = FacultyAbsenceEngine(
            self.query_engine
        )

        print("Absence Engine ready.")

        self.nl_query = NaturalLanguageQuery(
            self.query_engine
        )

        print("Natural Language Query Engine ready.")

        print("\n" + "=" * 70)
        print("KNOWLEDGE BASE LOADED SUCCESSFULLY")
        print("=" * 70)

    # ======================================================
    # TIME UTILITIES
    # ======================================================

    @staticmethod
    def _normalize_time(value):

        """
        Convert different time formats into HH:MM.

        Supported examples:

            9:15
            09:15
            9.15
            09.15
            9:15 AM
            11:15 PM
            9 AM
            11 PM

        No faculty names or timetable values are hard-coded.
        """

        if not value:
            return None

        value = str(value).strip().lower()

        value = value.replace(".", ":")

        # Remove unnecessary spaces
        value = re.sub(r"\s+", " ", value)

        # --------------------------------------------------
        # HH:MM AM/PM
        # --------------------------------------------------

        match = re.fullmatch(
            r"(\d{1,2}):(\d{2})\s*(am|pm)?",
            value
        )

        if not match:
            # ----------------------------------------------
            # HH AM/PM
            # ----------------------------------------------

            match = re.fullmatch(
                r"(\d{1,2})\s*(am|pm)",
                value
            )

            if not match:
                # ------------------------------------------
                # Plain hour: HH
                # Example: 9 -> 09:00
                #          11 -> 11:00
                # ------------------------------------------

                match = re.fullmatch(
                    r"(\d{1,2})",
                    value
                )

                if not match:
                    return None

                hour = int(match.group(1))
                minute = 0
                meridiem = None
            else:
                hour = int(match.group(1))
                minute = 0
                meridiem = match.group(2)
        else:
            hour = int(match.group(1))
            minute = int(match.group(2))
            meridiem = match.group(3)

        if hour > 23 or minute > 59:
            return None

        if meridiem:

            if meridiem == "am":

                if hour == 12:
                    hour = 0

            elif meridiem == "pm":

                if hour != 12:
                    hour += 12

        return f"{hour:02d}:{minute:02d}"

    # ======================================================
    # EXTRACT TIME RANGE
    # ======================================================

    @classmethod
    def _extract_time_range(cls, query):

        """
        Extract a start/end time from natural language.

        Examples:

            between 9:15 and 11:15
            from 9:15 to 11:15
            9:15 - 11:15
            09:15–11:15
            between 9.15 and 11.15

        Returns:

            (start_time, end_time)

        or:

            (None, None)
        """

        if not query:
            return None, None

        text = str(query).lower()

        # Normalize dash characters
        text = text.replace("–", "-")
        text = text.replace("—", "-")
        text = text.replace("−", "-")

        # Normalize decimal time
        # Example: 9.15 -> 9:15
        text = re.sub(
            r"(?<!\d)(\d{1,2})\.(\d{2})(?!\d)",
            r"\1:\2",
            text
        )

        # --------------------------------------------------
        # Pattern 1
        #
        # between 9:15 and 11:15
        # --------------------------------------------------

        match = re.search(
            r"\bbetween\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\s+and\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
            text
        )

        if match:

            start = cls._normalize_time(
                match.group(1)
            )

            end = cls._normalize_time(
                match.group(2)
            )

            if start and end:
                return start, end

        # --------------------------------------------------
        # Pattern 2
        #
        # from 9:15 to 11:15
        # --------------------------------------------------

        match = re.search(
            r"\bfrom\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\s+to\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
            text
        )

        if match:

            start = cls._normalize_time(
                match.group(1)
            )

            end = cls._normalize_time(
                match.group(2)
            )

            if start and end:
                return start, end

        # --------------------------------------------------
        # Pattern 3
        #
        # 9:15 - 11:15
        # --------------------------------------------------

        match = re.search(
            r"\b"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\s*-\s*"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\b",
            text
        )

        if match:

            start = cls._normalize_time(
                match.group(1)
            )

            end = cls._normalize_time(
                match.group(2)
            )

            if start and end:
                return start, end
                    # --------------------------------------------------
        # Pattern 4
        #
        # 13:30 to 15:30
        # --------------------------------------------------

        match = re.search(
            r"\b"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\s+to\s+"
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
            r"\b",
            text
        )

        if match:

            start = cls._normalize_time(
                match.group(1)
            )

            end = cls._normalize_time(
                match.group(2)
            )

            if start and end:
                return start, end

        return None, None
    

    # ======================================================
    # EXTRACT DAY
    # ======================================================

    @staticmethod
    def _extract_day(query):

        """
        Universal weekday extraction.

        Returns the canonical day name.
        """

        text = str(query).lower()

        days = {
            "monday": "Monday",
            "mon": "Monday",

            "tuesday": "Tuesday",
            "tue": "Tuesday",
            "tues": "Tuesday",

            "wednesday": "Wednesday",
            "wed": "Wednesday",

            "thursday": "Thursday",
            "thu": "Thursday",
            "thur": "Thursday",
            "thurs": "Thursday",

            "friday": "Friday",
            "fri": "Friday",

            "saturday": "Saturday",
            "sat": "Saturday",

            "sunday": "Sunday",
            "sun": "Sunday",
        }

        # Longest first prevents partial matching
        for word in sorted(
            days,
            key=len,
            reverse=True
        ):

            if re.search(
                rf"\b{re.escape(word)}\b",
                text
            ):

                return days[word]

        return None

    # ======================================================
    # EXTRACT SEMESTER NUMBER
    # ======================================================

    @staticmethod
    def _extract_semester_number(query):
        """
        Extract a semester number (1-10) from phrasing such as
        "7th semester", "seventh semester", "semester 7", or
        "sem 7".

        This is a purely linguistic ordinal/number parser - it
        does not reference any specific semester, class, or
        faculty member from the timetable data, and returns
        None when no semester phrase is present.
        """

        text = str(query).lower()

        ordinal_words = {
            "first": 1, "1st": 1,
            "second": 2, "2nd": 2,
            "third": 3, "3rd": 3,
            "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5,
            "sixth": 6, "6th": 6,
            "seventh": 7, "7th": 7,
            "eighth": 8, "8th": 8,
            "ninth": 9, "9th": 9,
            "tenth": 10, "10th": 10,
        }

        for word, value in ordinal_words.items():

            if re.search(
                rf"\b{re.escape(word)}\s+sem",
                text
            ):
                return value

        match = re.search(
            r"\bsem(?:ester)?\s*(\d{1,2})\b",
            text
        )

        if match:
            value = int(match.group(1))
            if 1 <= value <= 10:
                return value

        match = re.search(
            r"\b(\d{1,2})\s*(?:th|st|nd|rd)?\s+sem",
            text
        )

        if match:
            value = int(match.group(1))
            if 1 <= value <= 10:
                return value

        return None

    # ======================================================
    # ORDINAL FORMATTING (generic linguistic helper - e.g.
    # 1 -> "1st", 7 -> "7th". Not tied to any specific
    # semester, class, or faculty data.)
    # ======================================================

    @staticmethod
    def _ordinal(number):

        try:
            number = int(number)
        except (TypeError, ValueError):
            return str(number)

        if 10 <= (number % 100) <= 20:
            suffix = "th"
        else:
            suffix = {
                1: "st",
                2: "nd",
                3: "rd"
            }.get(number % 10, "th")

        return f"{number}{suffix}"

    def _extract_period_teacher(self, query):
        """Resolve a specific faculty name from a period query."""

        text = str(query).lower()

        # Get canonical faculty names from the existing
        # NaturalLanguageQuery object.
        try:
            names = self.nl_query._known_teachers()
        except Exception:
            names = []

        # Remove common faculty titles from the query.
        query_key = re.sub(
            r"\b(?:dr|mr|mrs|ms|prof|professor)\.?\s*",
            "",
            text,
            flags=re.IGNORECASE
        )

        query_key = re.sub(
            r"\s+",
            " ",
            query_key
        ).strip()

        # Check longest names first.
        # This prevents "Dinesh Kumar" from matching
        # before "Dinesh Kumar Sharma".
        for name in sorted(
            names,
            key=lambda x: len(str(x)),
            reverse=True
        ):

            name_key = re.sub(
                r"\b(?:dr|mr|mrs|ms|prof|professor)\.?\s*",
                "",
                str(name),
                flags=re.IGNORECASE
            )

            name_key = re.sub(
                r"\s+",
                " ",
                name_key
            ).strip()

            if not name_key:
                continue

            # Match the complete faculty name.
            if re.search(
                r"(?<![a-z])"
                + re.escape(name_key)
                + r"(?![a-z])",
                query_key,
                re.IGNORECASE
            ):
                return name

        return None

    # ======================================================
    # PERIOD QUERY DETECTION
    # ======================================================

    def _is_faculty_period_query(self, query):
        """
        Detect whether the user is asking about faculty
        availability/status over a time interval.
        """

        text = str(query).lower()

        faculty_words = (
    "faculty",
    "faculties",
    "teacher",
    "teachers",
    "professor",
    "professors",
    "staff",
    "sir",
    "ma'am",
    "madam",

    "who is free",
    "who is available",
    "who should be assigned",
    "who should take",
    "who can take",

    "available faculty",
    "free faculty",
)

        status_words = (
            "free",
            "available",
            "availability",
            "busy",
            "occupied",
            "unavailable",
            "take duty",
            "exam duty",
            "can take",
            "can handle",
        )

        has_faculty_reference = any(
            word in text
            for word in faculty_words
        )

        has_status_reference = any(
            word in text
            for word in status_words
        )

        has_time_range = bool(
            self._extract_time_range(query)[0]
            and self._extract_time_range(query)[1]
        )

        has_specific_teacher = (
            self._extract_period_teacher(query) is not None
        )

        return (
            has_status_reference
            and has_time_range
            and (
                has_faculty_reference
                or has_specific_teacher
            )
        )

    # ======================================================
    # PERIOD QUERY
    # ======================================================

    def _process_faculty_period_query(self, query):

        """
        Handle natural-language faculty availability
        queries containing a start and end time.
        """

        day = self._extract_day(query)

        start_time, end_time = (
            self._extract_time_range(query)
        )

    # --------------------------------------------------
        # Extract specific faculty, if mentioned
        # --------------------------------------------------

        teacher = self._extract_period_teacher(query)

        # --------------------------------------------------
        # Missing day
        # --------------------------------------------------

        if not day:

            return (
                "Please specify a day, for example "
                "Monday, Tuesday, Wednesday, etc."
            )

        # --------------------------------------------------
        # Missing time range
        # --------------------------------------------------

        if not start_time or not end_time:

            return (
                "Please specify a complete time range, "
                "for example 09:15 to 11:15."
            )

        # --------------------------------------------------
        # Validate time ordering
        # --------------------------------------------------

        try:

            start = datetime.strptime(
                start_time,
                "%H:%M"
            )

            end = datetime.strptime(
                end_time,
                "%H:%M"
            )

            if end <= start:

                return (
                    "The ending time must be later than "
                    "the starting time."
                )

        except ValueError:

            return (
                "I could not understand the requested "
                "time range."
            )

        # --------------------------------------------------
        # SPECIFIC FACULTY PERIOD STATUS
        # --------------------------------------------------
        if teacher:
            result = self.query_engine.faculty_status_for_period(
                teacher, day, start_time, end_time
            )

            status = result.get("status")
            if status == "free":
                slots = result.get("slots", [])
                slot_text = ", ".join(str(x) for x in slots)
                return (
                    f"{teacher} is FREE on {day} from "
                    f"{start_time} to {end_time}."
                    + (f"\nOverlapping slots: {slot_text}" if slot_text else "")
                )

            if status == "busy":
                busy_slots = [
                    self.query_engine._slot(x.get("slot"))
                    for x in result.get("events", [])
                    if self.query_engine._slot(x.get("slot")) is not None
                ]
                slot_text = ", ".join(str(x) for x in busy_slots)
                return (
                    f"{teacher} is BUSY on {day} from "
                    f"{start_time} to {end_time}."
                    + (f"\nBusy slots: {slot_text}" if slot_text else "")
                )

            return (
                f"I could not determine the availability of {teacher} "
                f"on {day} from {start_time} to {end_time}."
            )
                  # --------------------------------------------------
        # BUSY/FREE FACULTY LOGIC
        # --------------------------------------------------

        


        # --------------------------------------------------
        # EXAM DUTY RECOMMENDATION
        # --------------------------------------------------

        text = str(query).lower()

        exam_duty_words = (
            "exam duty",
            "exam duties",
            "exam invigilation",
            "invigilation",
            "assign duty",
            "assigned duty",
            "take duty",
            "can take duty",
            "who should be assigned",
            "who should take",
        )

        is_exam_duty_intent = any(
            phrase in text
            for phrase in exam_duty_words
        )

        if is_exam_duty_intent:

            try:

                duty_result = (
                    self.workload_engine.exam_duty_candidates(
                        day,
                        start_time,
                        end_time
                    )
                )

            except Exception as e:

                return (
                    "Unable to calculate exam-duty candidates.\n"
                    f"Error: {e}"
                )

            if not isinstance(duty_result, dict):

                return (
                    "Unable to retrieve exam-duty candidates."
                )

            candidates = duty_result.get(
                "results",
                []
            )

            if not candidates:

                return (
                    f"No suitable faculty members were found "
                    f"for exam duty on {day} from "
                    f"{start_time} to {end_time}."
                )

            lines = []

            lines.append(
                f"Recommended faculty for exam duty on "
                f"{day} from {start_time} to {end_time}:"
            )

            lines.append("")

            for index, candidate in enumerate(
                candidates,
                start=1
            ):

                teacher = str(
                    candidate.get(
                        "teacher",
                        ""
                    )
                ).strip()

                daily_periods = candidate.get(
                    "daily_periods",
                    0
                )

                priority = candidate.get(
                    "priority",
                    ""
                )

                if not teacher:
                    continue

                lines.append(
                    f"{index}. {teacher} — "
                    f"{daily_periods} periods — "
                    f"{priority} priority"
                )

            lines.append("")
            lines.append(
                f"Total candidates: {len(candidates)}"
            )

            return "\n".join(lines)


        # --------------------------------------------------
        # USE EXISTING VALIDATED QUERY ENGINE
        # --------------------------------------------------

        
        # --------------------------------------------------
        # USE EXISTING VALIDATED QUERY ENGINE
        # --------------------------------------------------
                # --------------------------------------------------
        # EXAM DUTY RECOMMENDATION
        # --------------------------------------------------

        text = str(query).lower()

        exam_duty_words = (
            "exam duty",
            "exam duties",
            "exam invigilation",
            "invigilation",
            "assign duty",
            "assigned duty",
            "take duty",
            "can take duty",
            "who should be assigned",
            "who should take",
        )

        is_exam_duty_intent = any(
            phrase in text
            for phrase in exam_duty_words
        )

        if is_exam_duty_intent:

            try:

                duty_result = (
                    self.workload_engine.exam_duty_candidates(
                        day,
                        start_time,
                        end_time
                    )
                )

            except Exception as e:

                return (
                    "Unable to calculate exam-duty candidates.\n"
                    f"Error: {e}"
                )

            if not isinstance(duty_result, dict):

                return (
                    "Unable to retrieve exam-duty candidates."
                )

            candidates = duty_result.get(
                "results",
                []
            )

            if not candidates:

                return (
                    f"No suitable faculty members were found "
                    f"for exam duty on {day} from "
                    f"{start_time} to {end_time}."
                )

            lines = []

            lines.append(
                f"Recommended faculty for exam duty on "
                f"{day} from {start_time} to {end_time}:"
            )

            lines.append("")

            for index, candidate in enumerate(
                candidates,
                start=1
            ):

                teacher = str(
                    candidate.get(
                        "teacher",
                        ""
                    )
                ).strip()

                daily_periods = candidate.get(
                    "daily_periods",
                    0
                )

                priority = candidate.get(
                    "priority",
                    ""
                )

                if not teacher:
                    continue

                lines.append(
                    f"{index}. {teacher} "
                    f"— {daily_periods} periods "
                    f"— {priority} priority"
                )

            lines.append("")

            lines.append(
                f"Total candidates: {len(candidates)}"
            )

            return "\n".join(lines)
                # --------------------------------------------------
        # DETECT BUSY / OCCUPIED / UNAVAILABLE INTENT
        # --------------------------------------------------

        text = str(query).lower()

        busy_words = (
            "busy",
            "occupied",
            "unavailable",
            "not available",
        )

        is_busy_intent = any(
            word in text
            for word in busy_words
        )

        if is_busy_intent:

            # Get the complete faculty roster from the existing faculty records.
            all_records = self.query_engine._faculty_records()
            all_names = []

            for item in all_records:
                if not isinstance(item, dict):
                    continue

                name = str(item.get("teacher", "")).strip()
                if name:
                    all_names.append(name)

            all_names = list(dict.fromkeys(all_names))
            busy_faculty = []

            for name in all_names:
                status_result = self.query_engine.faculty_status_for_period(
                    name,
                    day,
                    start_time,
                    end_time
                )

                if (
                    isinstance(status_result, dict)
                    and status_result.get("status") == "busy"
                ):
                    busy_faculty.append(name)

            busy_faculty = list(dict.fromkeys(busy_faculty))
            busy_faculty.sort(key=lambda x: x.lower())

            if not busy_faculty:
                return (
                    "No faculty members are busy on "
                    f"{day} from {start_time} to {end_time}."
                )

            lines = [
                f"Faculty members busy on {day} "
                f"from {start_time} to {end_time}:",
                ""
            ]

            for index, teacher in enumerate(busy_faculty, start=1):
                lines.append(f"{index}. {teacher}")

            lines.extend(("", f"Total faculty: {len(busy_faculty)}"))
            return "\n".join(lines)

        # --------------------------------------------------
        # EXISTING FREE-FACULTY LOGIC
        # --------------------------------------------------

        

        result = (
            self.query_engine.faculty_free_for_period(
                day,
                start_time,
                end_time
            )
        )

        if not isinstance(result, dict):

            return (
                "Unable to retrieve faculty availability "
                "for the requested period."
            )

        results = result.get(
            "results",
            []
        )

        # --------------------------------------------------
        # Extract valid faculty names
        # --------------------------------------------------

        teachers = []

        for item in results:

            if not isinstance(item, dict):
                continue

            teacher = str(
                item.get("teacher", "")
            ).strip()

            if not teacher:
                continue

            teachers.append(teacher)

        # --------------------------------------------------
        # Remove duplicate names
        # --------------------------------------------------

        teachers = list(
            dict.fromkeys(teachers)
        )

        teachers.sort(
            key=lambda x: x.lower()
        )

        # --------------------------------------------------
        # No faculty
        # --------------------------------------------------

        if not teachers:

            return (
                "No faculty members are free for "
                f"{day} from {start_time} to {end_time}."
            )

        # --------------------------------------------------
        # Response
        # --------------------------------------------------

        lines = []

        lines.append(
            f"Faculty members free on {day} "
            f"from {start_time} to {end_time}:"
        )

        lines.append("")

        for index, teacher in enumerate(
            teachers,
            start=1
        ):

            lines.append(
                f"{index}. {teacher}"
            )

        lines.append("")

        lines.append(
            f"Total faculty: {len(teachers)}"
        )

        return "\n".join(lines)

    # ======================================================
    # PROCESS QUERY
    # ======================================================

        # ======================================================
    # WORKLOAD RANK EXTRACTION
    # ======================================================

    def _extract_workload_rank(self, query):

        text = str(query).lower().strip()

        # Explicit ordinal words
        rank_words = {
            "first": 1,
            "1st": 1,
            "second": 2,
            "2nd": 2,
            "third": 3,
            "3rd": 3,
            "fourth": 4,
            "4th": 4,
            "fifth": 5,
            "5th": 5,
            "sixth": 6,
            "6th": 6,
            "seventh": 7,
            "7th": 7,
            "eighth": 8,
            "8th": 8,
            "ninth": 9,
            "9th": 9,
            "tenth": 10,
            "10th": 10,
        }

        for word, rank in rank_words.items():

            if re.search(
                rf"\b{re.escape(word)}\b",
                text
            ):
                return rank

        # If no explicit rank is mentioned,
        # treat the query as first/highest/lowest.
        return 1


    # ======================================================
    # PROCESS QUERY
    # ======================================================

    

    def process_query(self, query):

        query = str(query).strip()

        if not query:
            return "Please enter a query."
       

        # --------------------------------------------------
        # EXAM DUTY / INVIGILATION
        # --------------------------------------------------

        text = str(query).lower()

        exam_duty_words = (
            "exam duty",
            "exam duties",
            "exam invigilation",
            "invigilation",
            "invigilator",
            "invigilators",
            "assign duty",
            "assigned duty",
            "take duty",
            "can take duty",
            "who should be assigned",
            "who should take",
        )

        is_exam_duty_intent = any(
            phrase in text
            for phrase in exam_duty_words
        )

        if is_exam_duty_intent:

            day = self._extract_day(query)

            start_time, end_time = (
                self._extract_time_range(query)
            )

            if not day:
                return (
                    "Please specify a day for the exam duty, "
                    "for example Monday."
                )

            if not start_time or not end_time:
                return (
                    "Please specify a complete time range for "
                    "the exam duty, for example 09:00 to 11:00."
                )

            # --------------------------------------------------
            # EXTRACT REQUESTED FACULTY COUNT
            # --------------------------------------------------

            count_patterns = (
                r"\bassign\s+(\d+)\s+"
                r"(?:faculty|faculties|teachers|professors|"
                r"staff|invigilators?)\b",

                r"\bneed\s+(\d+)\s+"
                r"(?:faculty|faculties|teachers|professors|"
                r"staff|invigilators?)\b",

                r"\b(\d+)\s+"
                r"(?:faculty|faculties|teachers|professors|"
                r"staff|invigilators?)\b",

                r"\bassign\s+(\d+)\b",

                r"\bneed\s+(\d+)\b",
            )

            required_count = None

            for pattern in count_patterns:

                match = re.search(pattern, text)

                if match:
                    try:
                        required_count = int(match.group(1))
                    except ValueError:
                        required_count = None
                    break

            # --------------------------------------------------
            # ACTUAL ASSIGNMENT
            # --------------------------------------------------

            if required_count is not None:

                if required_count <= 0:
                    return (
                        "The number of faculty to assign "
                        "must be greater than zero."
                    )

                try:
                    duty_result = (
                        self.workload_engine.assign_exam_duty(
                            day,
                            start_time,
                            end_time,
                            required_count
                        )
                    )
                except Exception as e:
                    return (
                        "Unable to assign exam duty.\n"
                        f"Error: {e}"
                    )

                if not isinstance(duty_result, dict):
                    return (
                        "Unable to retrieve the exam-duty "
                        "assignment result."
                    )

                assigned = duty_result.get("results", [])
                success = duty_result.get("success", False)

                if not assigned:
                    return (
                        f"No suitable faculty members were found "
                        f"for exam duty on {day} from "
                        f"{start_time} to {end_time}."
                    )

                lines = []

                if success:
                    lines.append(
                        f"Exam duty assigned successfully on "
                        f"{day} from {start_time} to {end_time}."
                    )
                else:
                    lines.append(
                        f"Exam-duty assignment result for "
                        f"{day} from {start_time} to {end_time}:"
                    )

                lines.append("")

                for index, candidate in enumerate(assigned, start=1):

                    teacher = str(
                        candidate.get("teacher", "")
                    ).strip()

                    daily_periods = candidate.get(
                        "daily_periods", 0
                    )

                    priority = candidate.get(
                        "priority", ""
                    )

                    if not teacher:
                        continue

                    lines.append(
                        f"{index}. {teacher} — "
                        f"{daily_periods} periods — "
                        f"{priority} priority"
                    )

                lines.append("")
                lines.append(
                    f"Assigned: {len(assigned)} / {required_count}"
                )

                return "\n".join(lines)

            # --------------------------------------------------
            # RECOMMENDATION ONLY
            # --------------------------------------------------

            try:
                duty_result = (
                    self.workload_engine.exam_duty_candidates(
                        day,
                        start_time,
                        end_time
                    )
                )
            except Exception as e:
                return (
                    "Unable to calculate exam-duty candidates.\n"
                    f"Error: {e}"
                )

            if not isinstance(duty_result, dict):
                return (
                    "Unable to retrieve exam-duty candidates."
                )

            candidates = duty_result.get("results", [])

            if not candidates:
                return (
                    f"No suitable faculty members were found "
                    f"for exam duty on {day} from "
                    f"{start_time} to {end_time}."
                )

            lines = []

            lines.append(
                f"Recommended faculty for exam duty on "
                f"{day} from {start_time} to {end_time}:"
            )

            lines.append("")

            for index, candidate in enumerate(candidates, start=1):

                teacher = str(
                    candidate.get("teacher", "")
                ).strip()

                daily_periods = candidate.get(
                    "daily_periods", 0
                )

                priority = candidate.get(
                    "priority", ""
                )

                if not teacher:
                    continue

                lines.append(
                    f"{index}. {teacher} — "
                    f"{daily_periods} periods — "
                    f"{priority} priority"
                )

                return "\n".join(lines)

        # --------------------------------------------------
        # SEMESTER-WIDE FACULTY LOAD
        #
        # Example:
        # Who is taking 7th semester workload?
        # Who is taking 7th semester load?
        # Who teaches 7th semester?
        # Who is teaching 7th semester?
        # Which faculty are teaching 7th semester?
        # Which faculty have workload in 7th semester?
        # Show 7th semester faculty workload
        # Who has load in 7th semester?
        #
        # This is checked BEFORE the absence/workload keyword
        # checks below, because words like "classes" and "load"
        # in these phrasings would otherwise be misread as an
        # absence or per-teacher workload query.
        #
        # The semester number is parsed purely from the query
        # text (see _extract_semester_number - a linguistic
        # ordinal/number parser). Which classes belong to that
        # semester, which faculty teach them, and their period
        # counts are derived entirely from
        # workload_engine.semester_workload(), which reuses the
        # EXISTING workload engine's "one canonical event = one
        # period" definition (the same definition used by
        # daily_workload()/weekly_workload() for a single
        # teacher) and query_engine's own leading-digit semester
        # derivation (_semester_from_class_name), so multi-slot
        # labs are counted the same way everywhere and nothing
        # here hard-codes a semester number, class name, faculty
        # name, or period count.
        # --------------------------------------------------

        has_semester_word = bool(
            re.search(r"\bsem(?:ester)?\b", text)
        )

        if has_semester_word:

            semester_number = self._extract_semester_number(
                query
            )

            if semester_number is not None:

                day = self._extract_day(query)

                workload_result = (
                    self.workload_engine.semester_workload(
                        semester_number,
                        day=day
                    )
                )

                results = workload_result.get(
                    "results",
                    []
                )

                if not results:

                    return (
                        f"No faculty found teaching "
                        f"semester {semester_number}"
                        + (f" on {day}" if day else "")
                        + "."
                    )

                header = (
                    f"{self._ordinal(semester_number)} "
                    f"Semester Faculty Workload"
                )

                if day:
                    header += f" on {day}"

                return (
                    ResponseGenerator
                    .format_teacher_workload_list(
                        header,
                        results
                    )
                )

        # ==================================================
        # ABSENT FACULTY / REPLACEMENT QUERY
        # ==================================================

        absence_words = (
            "absent",
            "absence",
            "substitute",
            "substitution",
            "replacement",
            "replace",
            "cover the class",
            "cover class",
            "cover for",
        )

        is_absence_intent = any(
            phrase in text
            for phrase in absence_words
        )

        if is_absence_intent:

            day = self._extract_day(query)

            if not day:
                return (
                    "Please specify a day, for example Monday."
                )

            teacher = self._extract_period_teacher(query)

            if not teacher:
                return (
                    "Please specify the absent faculty member, "
                    "for example Mr. Rajesh Rajaan."
                )

            # --------------------------------------------------
            # FIND CLASSES OF ABSENT FACULTY
            # --------------------------------------------------

            if any(
                phrase in text
                for phrase in (
                    "what classes",
                    "which classes",
                    "classes affected",
                    "affected classes",
                    "classes will be affected",
                    "classes are affected",
                    "what periods",
                    "which periods",
                    "periods affected",
                )
            ):

                try:

                    result = (
                        self.absence_engine.absent_faculty_classes(
                            teacher,
                            day
                        )
                    )

                except Exception as e:

                    return (
                        "Unable to retrieve the classes of the "
                        "absent faculty.\n"
                        f"Error: {e}"
                    )

                classes = result.get(
                    "classes",
                    []
                )

                if not classes:

                    return (
                        f"{teacher} has no scheduled classes "
                        f"on {day}."
                    )

                lines = [
                    f"Classes affected by the absence of "
                    f"{teacher} on {day}:",
                    ""
                ]

                for index, cls in enumerate(
                    classes,
                    start=1
                ):

                    slot = cls.get(
                        "slot",
                        ""
                    )

                    slot_time = str(
                        cls.get(
                            "slot_time",
                            ""
                        )
                    ).strip()

                    subject = str(
                        cls.get(
                            "subject",
                            ""
                        )
                    ).strip()

                    class_name = str(
                        cls.get(
                            "class_name",
                            ""
                        )
                    ).strip()

                    group_name = str(
                        cls.get(
                            "group_name",
                            ""
                        )
                    ).strip()

                    room = str(
                        cls.get(
                            "room",
                            ""
                        )
                    ).strip()

                    details = []

                    if class_name:
                        details.append(
                            class_name
                        )

                    if group_name:
                        details.append(
                            group_name
                        )

                    if subject:
                        details.append(
                            subject
                        )

                    class_details = " | ".join(
                        details
                    )

                    if slot:
                        slot_text = (
                            f"Slot {slot}"
                        )
                    else:
                        slot_text = "Slot"

                    if slot_time:
                        slot_text += (
                            f" ({slot_time})"
                        )

                    line = (
                        f"{index}. {slot_text}"
                    )

                    if class_details:
                        line += (
                            f" — {class_details}"
                        )

                    if room:
                        line += (
                            f" — Room: {room}"
                        )

                    lines.append(line)

                lines.append("")

                lines.append(
                    f"Total affected classes: "
                    f"{len(classes)}"
                )

                return "\n".join(lines)

            # --------------------------------------------------
            # FIND REPLACEMENT FACULTY
            # --------------------------------------------------

            if any(
                phrase in text
                for phrase in (
                    "substitute",
                    "substitution",
                    "replacement",
                    "replace",
                    "who can cover",
                    "who can take",
                    "who should take",
                    "cover the class",
                    "cover class",
                )
            ):

                try:

                    result = (
                        self.absence_engine.replacement_candidates(
                            teacher,
                            day
                        )
                    )

                except Exception as e:

                    return (
                        "Unable to calculate replacement "
                        "faculty.\n"
                        f"Error: {e}"
                    )

                candidates = result.get(
                    "results",
                    []
                )

                if not candidates:

                    return (
                        f"No suitable replacement faculty "
                        f"were found for {teacher} on {day}."
                    )

                lines = [
                    f"Replacement faculty for {teacher} "
                    f"on {day}:",
                    ""
                ]

                for index, candidate in enumerate(
                    candidates,
                    start=1
                ):

                    replacement = str(
                        candidate.get(
                            "replacement_teacher",
                            ""
                        )
                    ).strip()

                    slot = candidate.get(
                        "slot",
                        ""
                    )

                    slot_time = str(
                        candidate.get(
                            "slot_time",
                            ""
                        )
                    ).strip()

                    subject = str(
                        candidate.get(
                            "subject",
                            ""
                        )
                    ).strip()

                    class_name = str(
                        candidate.get(
                            "class_name",
                            ""
                        )
                    ).strip()

                    group_name = str(
                        candidate.get(
                            "group_name",
                            ""
                        )
                    ).strip()

                    if not replacement:
                        continue

                    details = []

                    if class_name:
                        details.append(
                            class_name
                        )

                    if group_name:
                        details.append(
                            group_name
                        )

                    if subject:
                        details.append(
                            subject
                        )

                    class_details = " | ".join(
                        details
                    )

                    line = (
                        f"{index}. {replacement}"
                    )

                    if slot:
                        line += (
                            f" — Slot {slot}"
                        )

                    if slot_time:
                        line += (
                            f" ({slot_time})"
                        )

                    if class_details:
                        line += (
                            f" — {class_details}"
                        )

                    lines.append(line)

                lines.append("")

                lines.append(
                    f"Total replacement options: "
                    f"{len(candidates)}"
                )

                return "\n".join(lines)

            # --------------------------------------------------
            # GENERAL ABSENCE QUERY
            # --------------------------------------------------

            try:

                result = (
                    self.absence_engine.absent_faculty_classes(
                        teacher,
                        day
                    )
                )

            except Exception as e:

                return (
                    "Unable to process the absence query.\n"
                    f"Error: {e}"
                )

            classes = result.get(
                "classes",
                []
            )

            if not classes:

                return (
                    f"{teacher} has no scheduled classes "
                    f"on {day}."
                )

            lines = [
                f"{teacher} has {len(classes)} scheduled "
                f"class(es) on {day}.",
                "",
                "Affected classes:"
            ]

            for index, cls in enumerate(
                classes,
                start=1
            ):

                subject = str(
                    cls.get(
                        "subject",
                        ""
                    )
                ).strip()

                class_name = str(
                    cls.get(
                        "class_name",
                        ""
                    )
                ).strip()

                slot = cls.get(
                    "slot",
                    ""
                )

                details = []

                if class_name:
                    details.append(
                        class_name
                    )

                if subject:
                    details.append(
                        subject
                    )

                details_text = " | ".join(
                    details
                )

                if details_text:
                    lines.append(
                        f"{index}. Slot {slot} — "
                        f"{details_text}"
                    )
                else:
                    lines.append(
                        f"{index}. Slot {slot}"
                    )

            return "\n".join(lines)
                    # ==================================================
        # FACULTY WORKLOAD QUERY
        # ==================================================

        text = str(query).lower()

        workload_words = (
            "workload",
            "work load",
            "periods",
            "teaching load",
            "classes",
            "class",
        )

        is_workload_intent = any(
            phrase in text
            for phrase in workload_words
        )

        if is_workload_intent:

            day = self._extract_day(query)
                                   # --------------------------------------------------
            # WEEKLY WORKLOAD
            # --------------------------------------------------

            weekly_words = (
                "weekly",
                "this week",
                "for the week",
                "week's",
                "week workload",
                "weekly workload",
            )

            is_weekly_workload = any(
                phrase in text
                for phrase in weekly_words
            )

            if is_weekly_workload:

                teacher = self._extract_period_teacher(query)

                if not teacher:
                    return (
                        "Please specify a faculty member, "
                        "for example Mr. Rajesh Rajaan."
                    )

                result = (
                    self.workload_engine.weekly_workload(
                        teacher
                    )
                )

                total_periods = result.get(
                    "total_periods",
                    0
                )

                by_day = result.get(
                    "by_day",
                    {}
                )

                lines = [
                    f"Weekly workload of {teacher}:",
                    ""
                ]

                day_order = (
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                )

                for current_day in day_order:

                    if current_day in by_day:

                        periods = by_day[current_day]

                        lines.append(
                            f"{current_day.capitalize()}: "
                            f"{periods} periods"
                        )

                lines.append("")
                lines.append(
                    f"Total weekly periods: {total_periods}"
                )

                return "\n".join(lines)

                        # --------------------------------------------------
            # LOWEST WORKLOAD / RANKED LOWEST WORKLOAD
            # --------------------------------------------------

            if any(
                phrase in text
                for phrase in (
                    "lowest workload",
                    "least workload",
                    "minimum workload",
                    "lowest load",
                    "least load",
                    "fewest periods",
                    "minimum periods",
                    "fewest classes",
                    "least classes",
                )
            ):

                if not day:
                    return (
                        "Please specify a day, for example Monday."
                    )

                results = (
                    self.workload_engine.lowest_workload(
                        day,
                        limit=1000
                    )
                )

                if not results:
                    return (
                        f"No workload data found for {day}."
                    )

                rank = self._extract_workload_rank(query)

                results = sorted(
                    results,
                    key=lambda x: (
                        x["periods"],
                        x["teacher"].lower()
                    )
                )

                ranked_periods = sorted(
                    set(
                        item["periods"]
                        for item in results
                    )
                )

                if rank > len(ranked_periods):
                    return (
                        f"There are only "
                        f"{len(ranked_periods)} workload levels "
                        f"on {day}."
                    )

                target_periods = ranked_periods[rank - 1]

                ranked_faculty = [
                    item
                    for item in results
                    if item["periods"] == target_periods
                ]

                rank_names = {
                    1: "lowest",
                    2: "second lowest",
                    3: "third lowest",
                    4: "fourth lowest",
                    5: "fifth lowest",
                }

                rank_text = rank_names.get(
                    rank,
                    f"{rank}th lowest"
                )

                lines = [
                    f"Faculty with the {rank_text} "
                    f"workload on {day}:",
                    ""
                ]

                for index, item in enumerate(
                    ranked_faculty,
                    start=1
                ):
                    lines.append(
                        f"{index}. {item['teacher']} — "
                        f"{item['periods']} periods"
                    )

                return "\n".join(lines)

                        # --------------------------------------------------
            # HIGHEST WORKLOAD / RANKED HIGHEST WORKLOAD
            # --------------------------------------------------

            if any(
                phrase in text
                for phrase in (
                    "highest workload",
                    "maximum workload",
                    "highest load",
                    "maximum load",
                    "most periods",
                    "maximum periods",
                    "most classes",
                    "maximum classes",
                )
            ):

                if not day:
                    return (
                        "Please specify a day, for example Monday."
                    )

                results = (
                    self.workload_engine.highest_workload(
                        day,
                        limit=1000
                    )
                )

                if not results:
                    return (
                        f"No workload data found for {day}."
                    )

                rank = self._extract_workload_rank(query)

                # Sort by workload descending
                results = sorted(
                    results,
                    key=lambda x: (
                        -x["periods"],
                        x["teacher"].lower()
                    )
                )

                if rank > len(results):
                    return (
                        f"There is no {rank}th highest "
                        f"workload faculty on {day}."
                    )

                ranked_periods = sorted(
                    set(
                        item["periods"]
                        for item in results
                    ),
                    reverse=True
                )

                if rank > len(ranked_periods):
                    return (
                        f"There are only "
                        f"{len(ranked_periods)} workload levels "
                        f"on {day}."
                    )

                target_periods = ranked_periods[rank - 1]

                ranked_faculty = [
                    item
                    for item in results
                    if item["periods"] == target_periods
                ]

                rank_names = {
                    1: "highest",
                    2: "second highest",
                    3: "third highest",
                    4: "fourth highest",
                    5: "fifth highest",
                }

                rank_text = rank_names.get(
                    rank,
                    f"{rank}th highest"
                )

                lines = [
                    f"Faculty with the {rank_text} "
                    f"workload on {day}:",
                    ""
                ]

                for index, item in enumerate(
                    ranked_faculty,
                    start=1
                ):
                    lines.append(
                        f"{index}. {item['teacher']} — "
                        f"{item['periods']} periods"
                    )

                return "\n".join(lines)

            # --------------------------------------------------
            # SPECIFIC FACULTY WORKLOAD
            # --------------------------------------------------

            teacher = self._extract_period_teacher(query)

            if teacher and day:

                result = (
                    self.workload_engine.faculty_daily_workload(
                        teacher,
                        day
                    )
                )

                periods = result.get("periods", 0)

                return (
                    f"{teacher} has {periods} periods on {day}."
                )

            # --------------------------------------------------
            # WORKLOAD SUMMARY
            # --------------------------------------------------

            if day:

                result = (
                    self.workload_engine.workload_summary(day)
                )

                return (
                    f"Workload summary for {day}:\n"
                    f"Faculty count: {result['faculty_count']}\n"
                    f"Total periods: {result['total_periods']}\n"
                    f"Average periods: {result['average_periods']}\n"
                    f"Minimum periods: {result['minimum_periods']}\n"
                    f"Maximum periods: {result['maximum_periods']}"
                )

            return (
                "Please specify a day for the workload query, "
                "for example Monday."
            )


        


        # ==================================================
        # FACULTY PERIOD QUERY
        # ==================================================

        if self._is_faculty_period_query(query):

            start_time, end_time = (
                self._extract_time_range(query)
            )

            day = self._extract_day(query)

            if day and start_time and end_time:

                return self._process_faculty_period_query(
                    query
                )


        # --------------------------------------------------
        # EXISTING QUERY PIPELINE
        # --------------------------------------------------
        


        # --------------------------------------------------
        # EXISTING QUERY PIPELINE
        # --------------------------------------------------

        # STEP 1 - TOKENIZATION

        tokens = QueryTokenizer.tokenize(
            query
        )

        # STEP 2 - STOPWORD REMOVAL

        filtered_tokens = StopWordFilter.filter(
            tokens
        )

        # STEP 3 - DAY & SLOT EXTRACTION

        day_slot = DaySlotExtractor.extract(
            filtered_tokens
        )

        # STEP 4 - ENTITY EXTRACTION

        entities = self.extractor.extract(
            day_slot["remaining_tokens"]
        )

        # STEP 5 - INTENT DETECTION

        intent = IntentDetector.detect(
            tokens,
            entities,
            day_slot
        )

        # STEP 6 - QUERY PLANNING

        result = QueryPlanner.plan(
            intent,
            entities,
            day_slot,
            self.query_engine
        )

        # STEP 7 - RESPONSE GENERATION

        response = ResponseGenerator.generate(
            intent,
            result
        )

        return response


# ==========================================================
# COMMAND LINE CHATBOT
# ==========================================================

def main():

    print("=" * 70)
    print("        FACULTY FREE SLOT AI ASSISTANT")
    print("=" * 70)

    print("\nExamples:")

    print("• Who teaches Python?")
    print("• Show timetable of 3CS-D")
    print("• Where is OS III?")
    print("• Available faculty Monday Slot 3")
    print("• Who is free on Monday between 09:15 and 11:15?")
    print("• Which faculty are available Wednesday from 09:15 to 11:15?")
    print("• Subject of Dr Mehul Mahrishi")

    print("\nType 'exit' to quit.")

    chatbot = FacultyAIChatbot()

    while True:

        try:

            query = input(
                "\nYou : "
            ).strip()

            if not query:
                continue

            if query.lower() in {
                "exit",
                "quit",
                "bye"
            }:

                print(
                    "\nAssistant : Goodbye! Have a nice day."
                )

                break

            response = chatbot.process_query(
                query
            )

            print("\nAssistant:\n")
            print(response)

        except KeyboardInterrupt:

            print(
                "\n\nAssistant : Session terminated."
            )

            break

        except Exception as e:

            print(
                "\nAssistant : Something went wrong."
            )

            print(
                f"Error: {e}"
            )


if __name__ == "__main__":
    main()