"""
UNISCHED AI - Universal Excel/CSV Schedule Parser

Purpose
-------
Convert many different Excel/CSV timetable layouts into the
canonical timetable record structure used by the project.

Supported layouts include:

1. Row-based timetable
   Teacher | Day | Slot | Subject | Room | Class

2. Row-based timetable with time
   Teacher | Day | Time | Subject | Room | Class

3. Day-column timetable
   Teacher | Monday | Tuesday | Wednesday | Thursday | Friday

4. Period-column timetable
   Teacher | P1 | P2 | P3 | P4 | P5

5. Matrix timetable
   Time | Monday | Tuesday | Wednesday | Thursday | Friday

6. Variations in column names
   Faculty / Teacher
   Course / Subject
   Section / Class
   Classroom / Room
   Period / Slot
   Time / Timing

The parser does NOT assume one university's format.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class UniversalScheduleParser:
    """
    Semantic parser for timetable data coming from Excel/CSV.

    Input:
        List[dict]

    Output:
        List[dict] in the project's canonical timetable format.
    """

    DAY_ALIASES = {
        "mon": "monday",
        "monday": "monday",

        "tue": "tuesday",
        "tues": "tuesday",
        "tuesday": "tuesday",

        "wed": "wednesday",
        "weds": "wednesday",
        "wednesday": "wednesday",

        "thu": "thursday",
        "thur": "thursday",
        "thurs": "thursday",
        "thursday": "thursday",

        "fri": "friday",
        "friday": "friday",

        "sat": "saturday",
        "saturday": "saturday",

        "sun": "sunday",
        "sunday": "sunday",
    }

    DAY_NAMES = {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }

    EMPTY_VALUES = {
        "",
        "-",
        "--",
        "_",
        "—",
        "na",
        "n/a",
        "nan",
        "none",
        "null",
        "nil",
        "free",
        "f",
    }

    TEACHER_COLUMNS = {
        "teacher",
        "teachers",
        "faculty",
        "facultyname",
        "faculty_name",
        "faculty member",
        "faculty_member",
        "instructor",
        "professor",
        "lecturer",
        "staff",
        "teachername",
        "teacher_name",
    }

    DAY_COLUMNS = {
        "day",
        "weekday",
        "week day",
        "week_day",
        "dayname",
        "day_name",
    }

    SLOT_COLUMNS = {
        "slot",
        "period",
        "periodno",
        "period_no",
        "periodnumber",
        "period_number",
        "slotno",
        "slot_no",
        "slotnumber",
        "slot_number",
        "p",
    }

    TIME_COLUMNS = {
        "time",
        "timing",
        "time slot",
        "timeslot",
        "time_slot",
        "slot time",
        "slot_time",
        "period time",
        "period_time",
    }

    SUBJECT_COLUMNS = {
        "subject",
        "course",
        "course name",
        "course_name",
        "paper",
        "paper name",
        "paper_name",
        "subject name",
        "subject_name",
        "course title",
        "course_title",
    }

    ROOM_COLUMNS = {
        "room",
        "classroom",
        "class room",
        "class_room",
        "room no",
        "room_no",
        "room number",
        "room_number",
        "location",
        "venue",
    }

    CLASS_COLUMNS = {
        "class",
        "class name",
        "class_name",
        "section",
        "section name",
        "section_name",
        "batch",
        "batch name",
        "batch_name",
        "programme",
        "program",
    }

    GROUP_COLUMNS = {
        "group",
        "group name",
        "group_name",
        "lab group",
        "lab_group",
        "student group",
        "student_group",
    }

    def __init__(self) -> None:
        self.last_report: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # BASIC UTILITIES
    # ------------------------------------------------------------------

    @staticmethod
    def clean(value: Any) -> str:
        if value is None:
            return ""

        text = str(value).strip()

        if not text:
            return ""

        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @classmethod
    def normalize_key(cls, value: Any) -> str:
        text = cls.clean(value).lower()

        text = text.replace("&", "and")

        text = re.sub(r"[_\-./]+", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @classmethod
    def normalize_day(cls, value: Any) -> str:
        text = cls.clean(value)

        if not text:
            return ""

        key = re.sub(r"[^a-z]", "", text.lower())

        return cls.DAY_ALIASES.get(key, text.lower())

    @classmethod
    def normalize_slot(cls, value: Any) -> Optional[int]:
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            if value.is_integer():
                return int(value)

        text = cls.clean(value)

        if not text:
            return None

        match = re.fullmatch(r"(\d+)(?:\.0+)?", text)

        if match:
            return int(match.group(1))

        match = re.fullmatch(
            r"(?:slot|period|p)"
            r"\s*[-:_]?\s*(\d+)",
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

        match = re.search(
            r"(?:slot|period)"
            r"\s*(?:no\.?|number)?"
            r"\s*[-:#.]?\s*(\d+)",
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

        return None

    @classmethod
    def normalize_time(cls, value: Any) -> str:
        text = cls.clean(value)

        if not text:
            return ""

        text = text.replace("–", "-")
        text = text.replace("—", "-")

        text = re.sub(
            r"\s+to\s+",
            " - ",
            text,
            flags=re.IGNORECASE,
        )

        match = re.fullmatch(
            r"(\d{1,2})[:.](\d{2})\s*-\s*"
            r"(\d{1,2})[:.](\d{2})",
            text,
        )

        if match:
            h1, m1, h2, m2 = match.groups()

            return (
                f"{int(h1):02d}:{m1} - "
                f"{int(h2):02d}:{m2}"
            )

        return text

    @classmethod
    def is_empty(cls, value: Any) -> bool:
        text = cls.clean(value).lower()

        return text in cls.EMPTY_VALUES

    @classmethod
    def is_day(cls, value: Any) -> bool:
        normalized = cls.normalize_day(value)

        return normalized in cls.DAY_NAMES

    @classmethod
    def is_time(cls, value: Any) -> bool:
        text = cls.clean(value)

        if not text:
            return False

        patterns = [
            r"\d{1,2}[:.]\d{2}\s*[-–—]\s*\d{1,2}[:.]\d{2}",
            r"\d{1,2}\s*(?:AM|PM)\s*[-–—]\s*"
            r"\d{1,2}\s*(?:AM|PM)",
        ]

        return any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in patterns
        )

    # ------------------------------------------------------------------
    # COLUMN DETECTION
    # ------------------------------------------------------------------

    @classmethod
    def find_column(
        cls,
        columns: List[str],
        candidates: set,
    ) -> Optional[str]:

        normalized = {
            cls.normalize_key(column): column
            for column in columns
        }

        for candidate in candidates:

            key = cls.normalize_key(candidate)

            if key in normalized:
                return normalized[key]

        return None

    @classmethod
    def detect_columns(
        cls,
        records: List[Dict[str, Any]],
    ) -> Dict[str, Optional[str]]:

        if not records:
            return {
                "teacher": None,
                "day": None,
                "slot": None,
                "time": None,
                "subject": None,
                "room": None,
                "class_name": None,
                "group_name": None,
            }

        columns = list(records[0].keys())

        return {
            "teacher": cls.find_column(
                columns,
                cls.TEACHER_COLUMNS,
            ),
            "day": cls.find_column(
                columns,
                cls.DAY_COLUMNS,
            ),
            "slot": cls.find_column(
                columns,
                cls.SLOT_COLUMNS,
            ),
            "time": cls.find_column(
                columns,
                cls.TIME_COLUMNS,
            ),
            "subject": cls.find_column(
                columns,
                cls.SUBJECT_COLUMNS,
            ),
            "room": cls.find_column(
                columns,
                cls.ROOM_COLUMNS,
            ),
            "class_name": cls.find_column(
                columns,
                cls.CLASS_COLUMNS,
            ),
            "group_name": cls.find_column(
                columns,
                cls.GROUP_COLUMNS,
            ),
        }

    # ------------------------------------------------------------------
    # DAY / PERIOD COLUMN DETECTION
    # ------------------------------------------------------------------

    @classmethod
    def detect_day_columns(
        cls,
        records: List[Dict[str, Any]],
    ) -> Dict[str, str]:

        if not records:
            return {}

        result = {}

        for column in records[0].keys():

            day = cls.normalize_day(column)

            if day in cls.DAY_NAMES:
                result[column] = day

        return result

    @classmethod
    def detect_period_columns(
        cls,
        records: List[Dict[str, Any]],
    ) -> Dict[str, int]:

        if not records:
            return {}

        result = {}

        for column in records[0].keys():

            slot = cls.normalize_slot(column)

            if slot is not None:
                result[column] = slot

        return result

    # ------------------------------------------------------------------
    # FORMAT DETECTION
    # ------------------------------------------------------------------

    @classmethod
    def detect_layout(
        cls,
        records: List[Dict[str, Any]],
    ) -> str:

        if not records:
            return "EMPTY"

        columns = cls.detect_columns(records)

        day_columns = cls.detect_day_columns(records)

        period_columns = cls.detect_period_columns(records)

        has_teacher = columns["teacher"] is not None

        has_day = columns["day"] is not None

        has_slot = columns["slot"] is not None

        has_time = columns["time"] is not None

        has_subject = columns["subject"] is not None

        if has_day and (has_slot or has_time):
            return "ROW_BASED"

        if has_day and has_subject:
            return "ROW_BASED"

        if day_columns and has_teacher:
            return "DAY_COLUMNS"

        if period_columns and has_teacher:
            return "PERIOD_COLUMNS"

        # Matrix format:
        # Time | Monday | Tuesday | Wednesday
        if day_columns and (
            "time" in {
                cls.normalize_key(c)
                for c in records[0].keys()
            }
        ):
            return "MATRIX"

        # Another common matrix format:
        # first column contains time while other columns are days.
        first_column = list(records[0].keys())[0]

        if cls.is_time(records[0].get(first_column)):
            if day_columns:
                return "MATRIX"

        return "UNKNOWN"

    # ------------------------------------------------------------------
    # CANONICAL RECORD
    # ------------------------------------------------------------------

    @classmethod
    def canonical_record(
        cls,
        teacher: Any = "",
        day: Any = "",
        slot: Any = None,
        slot_time: Any = "",
        subject: Any = "",
        room: Any = "",
        class_name: Any = "",
        group_name: Any = "",
        source_file: str = "",
        source_type: str = "",
        raw_text: str = "",
    ) -> Dict[str, Any]:

        normalized_slot = cls.normalize_slot(slot)

        record = {
            "teacher": cls.clean(teacher),
            "day": cls.normalize_day(day),
            "slot": normalized_slot,
            "slot_time": cls.normalize_time(slot_time),
            "subject": cls.clean(subject),
            "room": cls.clean(room),
            "class_name": cls.clean(class_name),
            "group_name": cls.clean(group_name),
            "type": "",
            "length": "",
            "lessons_per_week": "",
            "available_classrooms": "",
            "cycle": "",
            "source_file": source_file,
            "source_type": source_type,
        }

        if raw_text:
            record["raw_text"] = raw_text

        return record

    # ------------------------------------------------------------------
    # FREE / EMPTY CELL
    # ------------------------------------------------------------------

    @classmethod
    def is_free_value(cls, value: Any) -> bool:

        text = cls.clean(value).lower()

        free_values = {
            "",
            "-",
            "--",
            "free",
            "f",
            "vacant",
            "available",
            "off",
            "none",
            "null",
            "na",
            "n/a",
            "break",
        }

        return text in free_values

    # ------------------------------------------------------------------
    # ROW BASED FORMAT
    # ------------------------------------------------------------------

    @classmethod
    def parse_row_based(
        cls,
        records: List[Dict[str, Any]],
        source_file: str = "",
        source_type: str = "",
    ) -> List[Dict[str, Any]]:

        if not records:
            return []

        columns = cls.detect_columns(records)

        result = []

        for row in records:

            teacher = row.get(
                columns["teacher"],
                "",
            ) if columns["teacher"] else ""

            day = row.get(
                columns["day"],
                "",
            ) if columns["day"] else ""

            slot = row.get(
                columns["slot"],
                None,
            ) if columns["slot"] else None

            slot_time = row.get(
                columns["time"],
                "",
            ) if columns["time"] else ""

            subject = row.get(
                columns["subject"],
                "",
            ) if columns["subject"] else ""

            room = row.get(
                columns["room"],
                "",
            ) if columns["room"] else ""

            class_name = row.get(
                columns["class_name"],
                "",
            ) if columns["class_name"] else ""

            group_name = row.get(
                columns["group_name"],
                "",
            ) if columns["group_name"] else ""

            # Preserve all other information where possible.
            output = cls.canonical_record(
                teacher=teacher,
                day=day,
                slot=slot,
                slot_time=slot_time,
                subject=subject,
                room=room,
                class_name=class_name,
                group_name=group_name,
                source_file=source_file,
                source_type=source_type,
            )

            # Preserve extra source information.
            for key, value in row.items():

                if key not in output:
                    output[key] = value

            # Don't generate records that contain no schedule information.
            if (
                not output["teacher"]
                and not output["subject"]
                and not output["class_name"]
            ):
                continue

            result.append(output)

        return result

    # ------------------------------------------------------------------
    # DAY-COLUMN FORMAT
    # ------------------------------------------------------------------

    @classmethod
    def parse_day_columns(
        cls,
        records: List[Dict[str, Any]],
        source_file: str = "",
        source_type: str = "",
    ) -> List[Dict[str, Any]]:

        if not records:
            return []

        columns = cls.detect_columns(records)
        day_columns = cls.detect_day_columns(records)

        result = []

        for row in records:

            teacher = ""

            if columns["teacher"]:
                teacher = row.get(
                    columns["teacher"],
                    "",
                )

            class_name = ""

            if columns["class_name"]:
                class_name = row.get(
                    columns["class_name"],
                    "",
                )

            group_name = ""

            if columns["group_name"]:
                group_name = row.get(
                    columns["group_name"],
                    "",
                )

            for column, day in day_columns.items():

                value = row.get(column)

                if cls.is_free_value(value):
                    subject = ""
                else:
                    subject = cls.clean(value)

                result.append(
                    cls.canonical_record(
                        teacher=teacher,
                        day=day,
                        subject=subject,
                        class_name=class_name,
                        group_name=group_name,
                        source_file=source_file,
                        source_type=source_type,
                        raw_text=cls.clean(value),
                    )
                )

        return [
            record
            for record in result
            if record["teacher"]
            or record["subject"]
            or record["class_name"]
        ]

    # ------------------------------------------------------------------
    # PERIOD-COLUMN FORMAT
    # ------------------------------------------------------------------

    @classmethod
    def parse_period_columns(
        cls,
        records: List[Dict[str, Any]],
        source_file: str = "",
        source_type: str = "",
    ) -> List[Dict[str, Any]]:

        if not records:
            return []

        columns = cls.detect_columns(records)
        period_columns = cls.detect_period_columns(records)

        result = []

        for row in records:

            teacher = (
                row.get(columns["teacher"], "")
                if columns["teacher"]
                else ""
            )

            class_name = (
                row.get(columns["class_name"], "")
                if columns["class_name"]
                else ""
            )

            group_name = (
                row.get(columns["group_name"], "")
                if columns["group_name"]
                else ""
            )

            day = (
                row.get(columns["day"], "")
                if columns["day"]
                else ""
            )

            for column, slot in period_columns.items():

                value = row.get(column)

                if cls.is_free_value(value):
                    subject = ""
                else:
                    subject = cls.clean(value)

                result.append(
                    cls.canonical_record(
                        teacher=teacher,
                        day=day,
                        slot=slot,
                        subject=subject,
                        class_name=class_name,
                        group_name=group_name,
                        source_file=source_file,
                        source_type=source_type,
                        raw_text=cls.clean(value),
                    )
                )

        return [
            record
            for record in result
            if record["teacher"]
            or record["subject"]
            or record["class_name"]
        ]

    # ------------------------------------------------------------------
    # MATRIX FORMAT
    # ------------------------------------------------------------------

    @classmethod
    def parse_matrix(
        cls,
        records: List[Dict[str, Any]],
        source_file: str = "",
        source_type: str = "",
    ) -> List[Dict[str, Any]]:

        if not records:
            return []

        day_columns = cls.detect_day_columns(records)

        if not day_columns:
            return []

        columns = list(records[0].keys())

        first_column = columns[0]

        result = []

        slot_counter = 1

        for row in records:

            time_value = row.get(first_column, "")

            slot_time = ""

            if cls.is_time(time_value):
                slot_time = cls.normalize_time(time_value)

            slot = slot_counter

            # If first column itself contains a period number,
            # use that instead.
            parsed_slot = cls.normalize_slot(time_value)

            if parsed_slot is not None:
                slot = parsed_slot

            for column, day in day_columns.items():

                value = row.get(column)

                if cls.is_free_value(value):
                    subject = ""
                else:
                    subject = cls.clean(value)

                result.append(
                    cls.canonical_record(
                        teacher="",
                        day=day,
                        slot=slot,
                        slot_time=slot_time,
                        subject=subject,
                        source_file=source_file,
                        source_type=source_type,
                        raw_text=cls.clean(value),
                    )
                )

            slot_counter += 1

        return [
            record
            for record in result
            if record["subject"]
        ]

    # ------------------------------------------------------------------
    # MAIN PARSER
    # ------------------------------------------------------------------

    def parse(
        self,
        records: List[Dict[str, Any]],
        source_file: str = "",
        source_type: str = "",
    ) -> List[Dict[str, Any]]:

        if not records:
            self.last_report = {
                "layout": "EMPTY",
                "input_records": 0,
                "output_records": 0,
            }

            return []

        layout = self.detect_layout(records)

        if layout == "ROW_BASED":
            parsed = self.parse_row_based(
                records,
                source_file,
                source_type,
            )

        elif layout == "DAY_COLUMNS":
            parsed = self.parse_day_columns(
                records,
                source_file,
                source_type,
            )

        elif layout == "PERIOD_COLUMNS":
            parsed = self.parse_period_columns(
                records,
                source_file,
                source_type,
            )

        elif layout == "MATRIX":
            parsed = self.parse_matrix(
                records,
                source_file,
                source_type,
            )

        else:
            parsed = []

        self.last_report = {
            "layout": layout,
            "input_records": len(records),
            "output_records": len(parsed),
            "day_records": sum(
                1
                for record in parsed
                if record.get("day")
            ),
            "slot_records": sum(
                1
                for record in parsed
                if record.get("slot") is not None
            ),
            "subject_records": sum(
                1
                for record in parsed
                if record.get("subject")
            ),
            "teacher_records": sum(
                1
                for record in parsed
                if record.get("teacher")
            ),
        }

        return parsed

    def report(self) -> Dict[str, Any]:
        return dict(self.last_report)

    @classmethod
    def print_report(
        cls,
        records: List[Dict[str, Any]],
        parsed: Optional[List[Dict[str, Any]]] = None,
    ) -> None:

        parser = cls()

        layout = parser.detect_layout(records)

        if parsed is None:
            parsed = parser.parse(records)

        report = parser.report()

        print("=" * 80)
        print("UNISCHED AI - UNIVERSAL SCHEDULE PARSER")
        print("=" * 80)

        print(f"Detected layout : {layout}")
        print(f"Input records   : {len(records)}")
        print(f"Output records  : {len(parsed)}")

        print()
        print("CANONICAL COVERAGE")
        print("-" * 80)

        print(
            "Day records     :",
            report.get("day_records", 0),
        )

        print(
            "Slot records    :",
            report.get("slot_records", 0),
        )

        print(
            "Subject records :",
            report.get("subject_records", 0),
        )

        print(
            "Teacher records :",
            report.get("teacher_records", 0),
        )

        print("=" * 80)