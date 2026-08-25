


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
from query_engine import QueryEngine


class FacultyAIChatbot:

    def __init__(self, files=None):

        print("\n" + "=" * 70)
        print("LOADING FACULTY AI KNOWLEDGE BASE")
        print("=" * 70)

        self.extractor = EntityExtractor()

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
                return None

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

    def _extract_period_teacher(self, query):
        """Resolve a specific faculty name from a period query to the canonical stored name."""
        text = str(query).lower()
        try:
            names = self.query_engine._all_faculty_names()
        except Exception:
            names = []

        for name in sorted(names, key=len, reverse=True):
            key = self.query_engine._teacher_key(name)
            if not key:
                continue
            # Compare the title-insensitive name against the query.
            query_key = re.sub(r"\b(?:dr|mr|mrs|ms|prof|professor)\.?\s*", "", text)
            query_key = re.sub(r"\s+", " ", query_key).strip()
            if re.search(r"(?<![a-z])" + re.escape(key) + r"(?![a-z])", query_key):
                return name
        return None

    # ======================================================
    # PERIOD QUERY DETECTION
    # ======================================================

    
    def _is_faculty_period_query(self,query):

        """
        Detect whether the user is asking for faculty
        availability over a time interval.
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
            "available faculty",
            "free faculty"
        )

        availability_words = (
            "free",
            "available",
            "availability"
        )

        has_faculty_reference = any(
            word in text
            for word in faculty_words
        )

        has_availability = any(
            word in text
            for word in availability_words
        )

        has_time_range = bool(
            self._extract_time_range(query)[0]
            and self._extract_time_range(query)[1]
        )

        has_specific_teacher = self._extract_period_teacher(query) is not None

        return (
            has_availability
            and has_time_range
            and (has_faculty_reference or has_specific_teacher)
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
        # USE EXISTING VALIDATED QUERY ENGINE
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

    def process_query(self, query):

        query = str(query).strip()

        if not query:
            return "Please enter a query."

        # ==================================================
        # IMPORTANT:
        #
        # Handle natural-language faculty PERIOD queries
        # before the old pipeline.
        #
        # This fixes:
        #
        # "Who is free on Monday between 9:15 and 11:15?"
        #
        # "Which faculty are available Monday from 9:15
        #  to 11:15?"
        #
        # without hard-coding faculty names.
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