"""
==========================================================
UNISCHED AI - UNIVERSAL PDF TIMETABLE IMPORTER
==========================================================

Universal timetable PDF importer.

Extracts:

    teacher
    day
    slot
    slot_time
    subject
    room
    class_name
    group_name
    type
    length
    lessons_per_week
    available_classrooms
    cycle

IMPORTANT
---------
This importer does NOT hardcode:

    - teacher names
    - college names
    - university names
    - subjects
    - classes
    - rooms

Teacher detection is based ONLY on a structural
"Teacher" label in the PDF.

Merged timetable cells are handled:

    ""    -> genuinely FREE
    None  -> merged continuation of previous event

==========================================================
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber


class PDFImporter:

    # ======================================================
    # DAY MAP
    # ======================================================

    DAY_MAP = {

        "mo": "Monday",
        "mon": "Monday",
        "monday": "Monday",

        "tu": "Tuesday",
        "tue": "Tuesday",
        "tues": "Tuesday",
        "tuesday": "Tuesday",

        "we": "Wednesday",
        "wed": "Wednesday",
        "wednesday": "Wednesday",

        "th": "Thursday",
        "thu": "Thursday",
        "thur": "Thursday",
        "thurs": "Thursday",
        "thursday": "Thursday",

        "fr": "Friday",
        "fri": "Friday",
        "friday": "Friday",

        "sa": "Saturday",
        "sat": "Saturday",
        "saturday": "Saturday",

        "su": "Sunday",
        "sun": "Sunday",
        "sunday": "Sunday",
    }

    # ======================================================
    # VALIDATE FILE
    # ======================================================

    @staticmethod
    def validate_file(
        file_path: str | Path
    ) -> Dict[str, Any]:

        path = Path(file_path)

        if not path.exists():

            return {
                "valid": False,
                "reason": "PDF file does not exist."
            }

        if not path.is_file():

            return {
                "valid": False,
                "reason": "Provided path is not a file."
            }

        if path.suffix.lower() != ".pdf":

            return {
                "valid": False,
                "reason": "File is not a PDF."
            }

        size_bytes = path.stat().st_size

        if size_bytes <= 0:

            return {
                "valid": False,
                "reason": "PDF file is empty."
            }

        try:

            with pdfplumber.open(path) as pdf:

                pages = len(pdf.pages)

        except Exception as e:

            return {
                "valid": False,
                "reason": f"Unable to open PDF: {e}"
            }

        return {

            "valid": True,

            "filename":
                path.name,

            "size_bytes":
                size_bytes,

            "size_mb":
                round(
                    size_bytes / (1024 * 1024),
                    2
                ),

            "pages":
                pages,
        }

    # ======================================================
    # CLEAN TEXT
    # ======================================================

    @staticmethod
    def clean_text(
        value: Any
    ) -> str:

        if value is None:
            return ""

        text = str(value)

        text = text.replace(
            "\xa0",
            " "
        )

        text = text.replace(
            "\r",
            " "
        )

        text = text.replace(
            "\n",
            " "
        )

        text = " ".join(
            text.split()
        )

        return text.strip()

    # ======================================================
    # EXTRACT WORDS
    # ======================================================

    @staticmethod
    def extract_words(
        page
    ) -> List[Dict[str, Any]]:

        try:

            return page.extract_words(
                keep_blank_chars=False
            )

        except Exception:

            return []

    # ======================================================
    # TITLE DETECTION
    # ======================================================

    @staticmethod
    def is_title_token(
        text: str
    ) -> bool:

        if not text:
            return False

        return bool(
            re.match(
                r"^(?:Dr|Mr|Ms|Mrs|Miss|Prof|Professor)\.?(?:$|[A-Z])",
                text,
                flags=re.IGNORECASE
            )
        )

    # ======================================================
    # CODE TOKEN DETECTION
    # ======================================================

    @staticmethod
    def is_short_code(
        text: str
    ) -> bool:

        if not text:
            return False

        text = text.strip()

        # Examples:
        #
        # AS
        # NM
        # PD
        # SC
        # NG
        # X7
        # SK

        return bool(
            re.fullmatch(
                r"[A-Z]{1,4}\d?",
                text
            )
        )

    # ======================================================
    # DETECT TEACHER
    # ======================================================

    @classmethod
    def detect_teacher(
        cls,
        page
    ) -> str:

        """
        Detect teacher ONLY from an explicit Teacher label.

        Examples:

            Teacher Dr. Aakriti Sharma
                -> Dr. Aakriti Sharma

            Teacher Mr. Ashish Pant
                -> Mr. Ashish Pant

            Teacher AS 1
                -> AS

            Teacher MnB
                -> MnB

            Teacher X7
                -> X7

        IMPORTANT:

        Text appearing BEFORE "Teacher" is ignored.

        Therefore something like:

            Swami Keshvanand Institute
            Teacher X7

        returns:

            X7

        and NEVER:

            Swami Keshvanand Institute
        """

        words = cls.extract_words(
            page
        )

        if not words:
            return ""

        # --------------------------------------------------
        # Reading order
        # --------------------------------------------------

        words = sorted(

            words,

            key=lambda word: (

                round(
                    word.get(
                        "top",
                        0
                    ),
                    1
                ),

                word.get(
                    "x0",
                    0
                )
            )
        )

        # --------------------------------------------------
        # Find explicit Teacher label
        # --------------------------------------------------

        for index, word in enumerate(words):

            current = cls.clean_text(
                word.get(
                    "text",
                    ""
                )
            )

            if current.lower() != "teacher":
                continue

            teacher_top = word.get(
                "top",
                0
            )

            same_line = []

            # --------------------------------------------------
            # Collect only words on the same visual line
            # --------------------------------------------------

            for next_word in words[
                index + 1:
            ]:

                next_top = next_word.get(
                    "top",
                    0
                )

                if abs(
                    next_top - teacher_top
                ) > 8:

                    break

                text = cls.clean_text(
                    next_word.get(
                        "text",
                        ""
                    )
                )

                if text:

                    same_line.append(
                        text
                    )

            if not same_line:
                continue

            # --------------------------------------------------
            # Build candidate line
            # --------------------------------------------------

            candidate = " ".join(
                same_line
            ).strip()

            # --------------------------------------------------
            # Remove anything after a SECOND faculty title.
            #
            # Example:
            #
            # Ms. Kiran Aahuja NM Ms. Neha Mathur
            #
            # becomes:
            #
            # Ms. Kiran Aahuja NM
            #
            # Then short-code logic removes NM.
            # --------------------------------------------------

            title_pattern = re.compile(

                r"(?:Dr|Mr|Ms|Mrs|Miss|Prof|Professor)\.?",

                flags=re.IGNORECASE
            )

            title_matches = list(
                title_pattern.finditer(
                    candidate
                )
            )

            if len(title_matches) >= 2:

                candidate = candidate[
                    :title_matches[1].start()
                ].strip()

            # --------------------------------------------------
            # Split candidate into tokens
            # --------------------------------------------------

            tokens = candidate.split()

            if not tokens:
                continue

            # --------------------------------------------------
            # Remove trailing numeric markers
            #
            # Example:
            #
            # Teacher AS 1
            #
            # -> AS
            # --------------------------------------------------

            while (

                len(tokens) > 1
                and
                re.fullmatch(
                    r"\d+",
                    tokens[-1]
                )

            ):

                tokens.pop()

            # --------------------------------------------------
            # Remove short faculty-code appearing AFTER
            # a real multi-word teacher name.
            #
            # Example:
            #
            # Ms. Kiran Aahuja NM
            #
            # -> Ms. Kiran Aahuja
            #
            # But:
            #
            # Ms. XE
            #
            # remains valid.
            # --------------------------------------------------

            cut_index = None

            for position in range(
                1,
                len(tokens)
            ):

                token = tokens[position]

                if not cls.is_short_code(
                    token
                ):
                    continue

                # Allow one short token after title.
                #
                # Example:
                # Ms. XE
                #
                if (
                    position == 1
                    and cls.is_title_token(
                        tokens[0]
                    )
                ):
                    continue

                # If there is already a proper name,
                # this is likely an attached faculty code.
                if position >= 2:

                    cut_index = position
                    break

            if cut_index is not None:

                tokens = tokens[
                    :cut_index
                ]

            teacher = " ".join(
                tokens
            ).strip()

            if teacher:

                return teacher

        # --------------------------------------------------
        # NO EXPLICIT TEACHER LABEL
        #
        # Do NOT guess.
        #
        # This is important for:
        #
        # classwise PDFs
        # location-wise PDFs
        # institution headers
        # room names
        # class names
        # --------------------------------------------------

        return ""

    # ======================================================
    # DETECT DAY
    # ======================================================

    @classmethod
    def detect_day(
        cls,
        value: Any
    ) -> Optional[str]:

        text = cls.clean_text(
            value
        )

        if not text:
            return None

        return cls.DAY_MAP.get(
            text.lower()
        )

    # ======================================================
    # DETECT SLOT NUMBER
    # ======================================================

    @classmethod
    def parse_slot_header(
        cls,
        value: Any
    ) -> Optional[int]:

        text = cls.clean_text(
            value
        )

        if not text:
            return None

        match = re.match(
            r"^(\d+)",
            text
        )

        if not match:
            return None

        try:

            slot = int(
                match.group(1)
            )

        except ValueError:

            return None

        if 1 <= slot <= 20:

            return slot

        return None

    # ======================================================
    # DETECT SLOT TIME
    # ======================================================

    @classmethod
    def parse_time(
        cls,
        value: Any
    ) -> str:

        text = cls.clean_text(
            value
        )

        if not text:
            return ""

        match = re.search(

            r"(\d{1,2}:\d{2})"
            r"\s*-\s*"
            r"(\d{1,2}:\d{2})",

            text
        )

        if not match:
            return ""

        return (
            f"{match.group(1)} - "
            f"{match.group(2)}"
        )

    # ======================================================
    # DETECT CLASS
    # ======================================================

    @staticmethod
    def detect_class(
        text: str
    ) -> str:

        if not text:
            return ""

        patterns = [

            # ----------------------------------------------
            # 3-CS-IOT
            # 5-CS-A
            # 3-CS-DS-A
            # ----------------------------------------------

            r"\b\d+\s*-\s*[A-Za-z]{2,}"
            r"(?:-[A-Za-z0-9]+)*\b",

            # ----------------------------------------------
            # 3CS
            # 5CSC
            # 3CSAI
            # ----------------------------------------------

            r"\b\d+[A-Za-z]{2,}"
            r"(?:-[A-Za-z0-9]+)*\b",

            # ----------------------------------------------
            # 3CS A
            # 3CS D
            # ----------------------------------------------

            r"\b\d+[A-Za-z]{2,}"
            r"\s+[A-Za-z0-9-]+\b",
        ]

        candidates = []

        for pattern in patterns:

            matches = re.findall(

                pattern,

                text,

                flags=re.IGNORECASE
            )

            candidates.extend(
                matches
            )

        if not candidates:

            return ""

        candidates = list(
            dict.fromkeys(
                candidate.strip()
                for candidate in candidates
            )
        )

        # Prefer hyphenated class formats

        for candidate in candidates:

            if "-" in candidate:

                return candidate

        # Otherwise longest candidate

        return max(
            candidates,
            key=len
        )

    # ======================================================
    # DETECT ROOM
    # ======================================================

    @classmethod
    def detect_room(
        cls,
        text: str
    ) -> str:

        """
        Detect classroom/laboratory room.

        Examples:

            303
            304
            CL-15
            ECL-08
            7F:EE-Lab13
            5F::CP5

        A subject such as:

            Spoken-Latex

        is NOT a room because it contains no digit.
        """

        if not text:
            return ""

        candidates = []

        # --------------------------------------------------
        # Numeric rooms
        # --------------------------------------------------

        numeric_rooms = re.findall(

            r"\b\d{2,4}\b",

            text
        )

        candidates.extend(
            numeric_rooms
        )

        # --------------------------------------------------
        # Standard room codes
        # --------------------------------------------------

        standard_rooms = re.findall(

            r"\b[A-Z]{1,8}"
            r"-"
            r"[A-Za-z]*"
            r"\d+"
            r"[A-Za-z0-9-]*\b",

            text,

            flags=re.IGNORECASE
        )

        candidates.extend(
            standard_rooms
        )

        # --------------------------------------------------
        # Complex laboratory rooms
        # --------------------------------------------------

        lab_rooms = re.findall(

            r"\b[A-Z0-9]{1,8}"
            r":+"
            r"[A-Za-z0-9-]*"
            r"\d+"
            r"[A-Za-z0-9-]*\b",

            text,

            flags=re.IGNORECASE
        )

        candidates.extend(
            lab_rooms
        )

        if not candidates:

            return ""

        candidates = list(
            dict.fromkeys(
                candidates
            )
        )

        # --------------------------------------------------
        # Don't return class as room
        # --------------------------------------------------

        class_name = cls.detect_class(
            text
        )

        candidates = [

            candidate

            for candidate in candidates

            if candidate.lower()
            != class_name.lower()
        ]

        if not candidates:

            return ""

        # --------------------------------------------------
        # Prefer structured room codes
        # --------------------------------------------------

        structured = [

            candidate

            for candidate in candidates

            if (
                "-"
                in candidate
                or
                ":"
                in candidate
            )
        ]

        if structured:

            return structured[-1].strip()

        return candidates[-1].strip()

    # ======================================================
    # DETECT GROUP
    # ======================================================

    @staticmethod
    def detect_group(
        text: str
    ) -> str:

        if not text:
            return ""

        match = re.search(

            r"\bGroup\s*([A-Za-z0-9]+)\b",

            text,

            flags=re.IGNORECASE
        )

        if not match:

            return ""

        return (
            f"Group {match.group(1)}"
        )

    # ======================================================
    # DETECT TYPE
    # ======================================================

    @staticmethod
    def detect_type(
        subject: str
    ) -> str:

        if not subject:

            return ""

        text = subject.lower()

        if "lab" in text:

            return "Lab"

        if "seminar" in text:

            return "Seminar"

        if "tutorial" in text:

            return "Tutorial"

        return "Theory"

    # ======================================================
    # CLEAN SUBJECT
    # ======================================================

    @classmethod
    def clean_subject(
        cls,
        text: str,
        class_name: str,
        room: str
    ) -> str:

        subject = cls.clean_text(
            text
        )

        if not subject:

            return ""

        # --------------------------------------------------
        # Remove class
        # --------------------------------------------------

        if class_name:

            subject = re.sub(

                re.escape(
                    class_name
                ),

                "",

                subject,

                flags=re.IGNORECASE
            )

        # --------------------------------------------------
        # Remove room
        # --------------------------------------------------

        if room:

            subject = re.sub(

                re.escape(
                    room
                ),

                "",

                subject,

                flags=re.IGNORECASE
            )

        # --------------------------------------------------
        # Remove Group
        # --------------------------------------------------

        subject = re.sub(

            r"\bGroup\s*[A-Za-z0-9]+\b",

            "",

            subject,

            flags=re.IGNORECASE
        )

        # --------------------------------------------------
        # Remove extra spaces
        # --------------------------------------------------

        subject = " ".join(
            subject.split()
        )

        return subject.strip()

    # ======================================================
    # EXTRACT TABLES
    # ======================================================

    @staticmethod
    def extract_tables_from_page(
        page
    ) -> List[List[List[Any]]]:

        try:

            tables = page.extract_tables()

            if not tables:

                return []

            return tables

        except Exception:

            return []

    # ======================================================
    # DETECT SLOT HEADERS
    # ======================================================

    @classmethod
    def detect_slot_headers(
        cls,
        row: List[Any]
    ) -> Dict[int, Dict[str, Any]]:

        slots = {}

        for index, cell in enumerate(
            row
        ):

            slot = cls.parse_slot_header(
                cell
            )

            if slot is None:

                continue

            slots[index] = {

                "slot":
                    slot,

                "time":
                    cls.parse_time(
                        cell
                    ),
            }

        return slots

    # ======================================================
    # CREATE EMPTY RECORD
    # ======================================================

    @staticmethod
    def empty_record(
        teacher: str,
        day: str,
        slot: Optional[int],
        slot_time: str,
        source_file: str,
        source_page: int
    ) -> Dict[str, Any]:

        return {

            "teacher":
                teacher,

            "day":
                day,

            "slot":
                slot,

            "slot_time":
                slot_time,

            "subject":
                "",

            "room":
                "",

            "class_name":
                "",

            "group_name":
                "",

            "type":
                "",

            "length":
                "",

            "lessons_per_week":
                "",

            "available_classrooms":
                "",

            "cycle":
                "",

            "source_file":
                source_file,

            "source_type":
                "pdf",

            "source_page":
                source_page,

            "raw_text":
                "",
        }

    # ======================================================
    # CREATE RECORD
    # ======================================================

    @classmethod
    def create_record(
        cls,
        teacher: str,
        day: str,
        slot: Optional[int],
        slot_time: str,
        cell_text: str,
        source_file: str,
        source_page: int
    ) -> Dict[str, Any]:

        cell_text = cls.clean_text(
            cell_text
        )

        # --------------------------------------------------
        # FREE SLOT
        # --------------------------------------------------

        if not cell_text:

            return cls.empty_record(

                teacher=
                    teacher,

                day=
                    day,

                slot=
                    slot,

                slot_time=
                    slot_time,

                source_file=
                    source_file,

                source_page=
                    source_page,
            )

        # --------------------------------------------------
        # CLASS
        # --------------------------------------------------

        class_name = cls.detect_class(
            cell_text
        )

        # --------------------------------------------------
        # ROOM
        # --------------------------------------------------

        room = cls.detect_room(
            cell_text
        )

        # --------------------------------------------------
        # GROUP
        # --------------------------------------------------

        group_name = cls.detect_group(
            cell_text
        )

        # --------------------------------------------------
        # SUBJECT
        # --------------------------------------------------

        subject = cls.clean_subject(

            cell_text,

            class_name,

            room
        )

        # --------------------------------------------------
        # TYPE
        # --------------------------------------------------

        record_type = cls.detect_type(
            subject
        )

        return {

            "teacher":
                teacher,

            "day":
                day,

            "slot":
                slot,

            "slot_time":
                slot_time,

            "subject":
                subject,

            "room":
                room,

            "class_name":
                class_name,

            "group_name":
                group_name,

            "type":
                record_type,

            "length":
                "",

            "lessons_per_week":
                "",

            "available_classrooms":
                "",

            "cycle":
                "",

            "source_file":
                source_file,

            "source_type":
                "pdf",

            "source_page":
                source_page,

            "raw_text":
                cell_text,
        }

    # ======================================================
    # PROCESS ONE PAGE
    # ======================================================

    @classmethod
    def process_page(
        cls,
        page,
        page_number: int,
        source_file: str
    ) -> List[Dict[str, Any]]:

        records = []

        # --------------------------------------------------
        # IMPORTANT:
        #
        # Teacher is detected ONLY through explicit
        # Teacher label.
        # --------------------------------------------------

        teacher = cls.detect_teacher(
            page
        )

        # --------------------------------------------------
        # Extract tables
        # --------------------------------------------------

        tables = cls.extract_tables_from_page(
            page
        )

        for table in tables:

            if not table:

                continue

            slot_headers = {}

            header_index = None

            # --------------------------------------------------
            # Find slot header row
            # --------------------------------------------------

            for row_index, row in enumerate(
                table
            ):

                if not row:

                    continue

                detected = cls.detect_slot_headers(
                    row
                )

                if detected:

                    slot_headers = detected

                    header_index = row_index

                    break

            if not slot_headers:

                continue

            # --------------------------------------------------
            # Process timetable rows
            # --------------------------------------------------

            for row in table[
                header_index + 1:
            ]:

                if not row:

                    continue

                if len(row) == 0:

                    continue

                # --------------------------------------------------
                # Day
                # --------------------------------------------------

                day = cls.detect_day(
                    row[0]
                )

                if not day:

                    continue

                # ==================================================
                # MERGED CELL HANDLING
                # ==================================================
                #
                # pdfplumber:
                #
                # ""    = actual empty/free cell
                #
                # None  = continuation of merged cell
                #
                # Example:
                #
                # Slot 5 = DE Lab
                # Slot 6 = None
                # Slot 7 = None
                # Slot 8 = ""
                #
                # Result:
                #
                # Slot 5 = BUSY
                # Slot 6 = BUSY
                # Slot 7 = BUSY
                # Slot 8 = FREE
                #
                # ==================================================

                previous_cell_text = None

                for column_index, slot_info in (
                    slot_headers.items()
                ):

                    # --------------------------------------------------
                    # Missing column
                    # --------------------------------------------------

                    if column_index >= len(
                        row
                    ):

                        cell = ""

                        raw_cell = ""

                    else:

                        raw_cell = row[
                            column_index
                        ]

                        # --------------------------------------------------
                        # MERGED CELL
                        # --------------------------------------------------

                        if raw_cell is None:

                            if previous_cell_text:

                                cell = (
                                    previous_cell_text
                                )

                            else:

                                cell = ""

                        # --------------------------------------------------
                        # NORMAL CELL
                        # --------------------------------------------------

                        else:

                            cell = cls.clean_text(
                                raw_cell
                            )

                    # --------------------------------------------------
                    # Create record
                    # --------------------------------------------------

                    record = cls.create_record(

                        teacher=
                            teacher,

                        day=
                            day,

                        slot=
                            slot_info["slot"],

                        slot_time=
                            slot_info["time"],

                        cell_text=
                            cell,

                        source_file=
                            source_file,

                        source_page=
                            page_number,
                    )

                    records.append(
                        record
                    )

                    # --------------------------------------------------
                    # Update merged-cell state
                    #
                    # None does NOT update previous event.
                    # --------------------------------------------------

                    if raw_cell is not None:

                        if cell:

                            previous_cell_text = (
                                cell
                            )

                        else:

                            # Genuine empty cell
                            # breaks merge.

                            previous_cell_text = None

        return records

    # ======================================================
    # IMPORT PDF
    # ======================================================

    @classmethod
    def import_file(
        cls,
        file_path: str | Path
    ) -> List[Dict[str, Any]]:

        validation = cls.validate_file(
            file_path
        )

        if not validation["valid"]:

            raise ValueError(
                validation["reason"]
            )

        path = Path(
            file_path
        )

        records = []

        with pdfplumber.open(
            path
        ) as pdf:

            for page_number, page in enumerate(
                pdf.pages,
                start=1
            ):

                page_records = cls.process_page(

                    page,

                    page_number,

                    path.name
                )

                records.extend(
                    page_records
                )

        return records

    # ======================================================
    # INSPECT PDF
    # ======================================================

    @classmethod
    def inspect_file(
        cls,
        file_path: str | Path
    ) -> Dict[str, Any]:

        validation = cls.validate_file(
            file_path
        )

        if not validation["valid"]:

            return validation

        path = Path(
            file_path
        )

        output = {

            "file":
                path.name,

            "size_bytes":
                validation.get(
                    "size_bytes",
                    0
                ),

            "size_mb":
                validation.get(
                    "size_mb",
                    0
                ),

            "pages":
                validation.get(
                    "pages",
                    0
                ),

            "records":
                0,

            "teachers":
                [],

            "days":
                [],

            "pages_with_teacher":
                0,

            "pages_with_tables":
                0,

            "pages_with_slot_headers":
                0,

            "pages_with_day_rows":
                0,
        }

        try:

            records = cls.import_file(
                path
            )

            output["records"] = len(
                records
            )

            teachers = set()

            days = set()

            for record in records:

                teacher = str(
                    record.get(
                        "teacher",
                        ""
                    )
                ).strip()

                day = str(
                    record.get(
                        "day",
                        ""
                    )
                ).strip()

                if teacher:

                    teachers.add(
                        teacher
                    )

                if day:

                    days.add(
                        day
                    )

            output["teachers"] = sorted(
                teachers
            )

            output["days"] = sorted(
                days
            )

            # --------------------------------------------------
            # Page-level inspection
            # --------------------------------------------------

            with pdfplumber.open(
                path
            ) as pdf:

                for page in pdf.pages:

                    teacher = cls.detect_teacher(
                        page
                    )

                    if teacher:

                        output[
                            "pages_with_teacher"
                        ] += 1

                    tables = (
                        cls.extract_tables_from_page(
                            page
                        )
                    )

                    if not tables:

                        continue

                    output[
                        "pages_with_tables"
                    ] += 1

                    page_has_slot = False

                    page_has_day = False

                    for table in tables:

                        for row in table:

                            if not row:

                                continue

                            if cls.detect_slot_headers(
                                row
                            ):

                                page_has_slot = True

                            if (
                                row
                                and
                                cls.detect_day(
                                    row[0]
                                )
                            ):

                                page_has_day = True

                    if page_has_slot:

                        output[
                            "pages_with_slot_headers"
                        ] += 1

                    if page_has_day:

                        output[
                            "pages_with_day_rows"
                        ] += 1

            return output

        except Exception as e:

            output["error"] = str(e)

            return output


# ==========================================================
# DIRECT MODULE TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 80)

    print(
        "UNISCHED AI - UNIVERSAL PDF IMPORTER"
    )

    print("=" * 80)

    print()

    print(
        "PDF importer loaded successfully."
    )

    print(
        "Teacher detection: structural Teacher label"
    )

    print(
        "Institution detection: never used as teacher"
    )

    print(
        "Timetable extraction: extract_tables()"
    )

    print(
        "Day detection: enabled"
    )

    print(
        "Slot detection: enabled"
    )

    print(
        "Slot time detection: enabled"
    )

    print(
        "Class detection: enabled"
    )

    print(
        "Room detection: enabled"
    )

    print(
        "Group detection: enabled"
    )

    print(
        "Merged-cell handling: enabled"
    )

    print(
        "Free-slot preservation: enabled"
    )

    print()

    print(
        "Ready for timetable PDFs."
    )

    print("=" * 80)