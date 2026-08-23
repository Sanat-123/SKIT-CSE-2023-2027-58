"""
==============================================================
UNISCHED AI - UNIVERSAL PDF TIMETABLE IMPORTER
==============================================================

IMPORTANT:
- Preserves EMPTY timetable cells.
- Empty faculty cell = FREE.
- Non-empty faculty cell = BUSY.
- Automatically extracts teacher name.
- Automatically extracts day, slot and slot time.
- Does NOT hard-code teacher names.
- Does NOT hard-code college names.
- Designed for facultywise/classwise/locationwise timetable PDFs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import re

import pdfplumber


class PDFImporter:

    # ==========================================================
    # CONSTANTS
    # ==========================================================

    DAY_MAP = {
        "mo": "monday",
        "mon": "monday",
        "monday": "monday",

        "tu": "tuesday",
        "tue": "tuesday",
        "tues": "tuesday",
        "tuesday": "tuesday",

        "we": "wednesday",
        "wed": "wednesday",
        "weds": "wednesday",
        "wednesday": "wednesday",

        "th": "thursday",
        "thu": "thursday",
        "thur": "thursday",
        "thurs": "thursday",
        "thursday": "thursday",

        "fr": "friday",
        "fri": "friday",
        "friday": "friday",

        "sa": "saturday",
        "sat": "saturday",
        "saturday": "saturday",

        "su": "sunday",
        "sun": "sunday",
        "sunday": "sunday",
    }

    SLOT_TIMES = {
        1: "08:15 - 09:15",
        2: "09:15 - 10:15",
        3: "10:15 - 11:15",
        4: "11:15 - 12:15",
        5: "12:00 - 13:00",
        6: "13:00 - 14:00",
        7: "14:00 - 15:00",
        8: "15:00 - 15:30",
    }

    # ==========================================================
    # BASIC CLEANING
    # ==========================================================

    @staticmethod
    def clean_text(value: Any) -> str:

        if value is None:
            return ""

        text = str(value)

        text = text.replace("\xa0", " ")

        text = text.replace("\r", "\n")

        return " ".join(
            text.strip().split()
        )

    # ==========================================================
    # FILE VALIDATION
    # ==========================================================

    @classmethod
    def validate_file(
        cls,
        file_path: str | Path
    ) -> Dict[str, Any]:

        path = Path(file_path)

        if not path.exists():

            return {
                "valid": False,
                "reason": "PDF file does not exist.",
            }

        if path.suffix.lower() != ".pdf":

            return {
                "valid": False,
                "reason": "File is not a PDF.",
            }

        size = path.stat().st_size

        if size == 0:

            return {
                "valid": False,
                "reason": "PDF file is empty.",
            }

        return {
            "valid": True,
            "reason": "",
            "size_bytes": size,
            "size_mb": round(
                size / (1024 * 1024),
                2
            ),
        }

    # ==========================================================
    # TEACHER EXTRACTION
    # ==========================================================

    @classmethod
    def detect_teacher_from_text(
        cls,
        text: str
    ) -> str:

        if not text:
            return ""

        # ------------------------------------------------------
        # Normal case:
        #
        # Teacher Ms.Archika Jain
        # Teacher Dr. Aakriti Sharma
        # ------------------------------------------------------

        patterns = [

            r"Teacher\s+(.+?)(?=\n|$)",

            r"TEACHER\s+(.+?)(?=\n|$)",

            r"Teacher:\s*(.+?)(?=\n|$)",

            r"Faculty\s+(.+?)(?=\n|$)",

            r"Faculty:\s*(.+?)(?=\n|$)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            if match:

                teacher = cls.clean_text(
                    match.group(1)
                )

                # Remove accidental timetable information
                teacher = re.sub(
                    r"\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s+8.*$",
                    "",
                    teacher
                ).strip()

                if teacher:
                    return teacher

        return ""

    # ==========================================================
    # TEACHER EXTRACTION FROM PAGE
    # ==========================================================

    @classmethod
    def detect_teacher(
        cls,
        page
    ) -> str:

        # ------------------------------------------------------
        # First use normal text extraction.
        # ------------------------------------------------------

        try:

            text = page.extract_text() or ""

            teacher = cls.detect_teacher_from_text(
                text
            )

            if teacher:
                return teacher

        except Exception:
            pass

        # ------------------------------------------------------
        # Fallback: extract words.
        # ------------------------------------------------------

        try:

            words = page.extract_words(
                x_tolerance=2,
                y_tolerance=2
            )

        except Exception:
            words = []

        if not words:
            return ""

        words = sorted(
            words,
            key=lambda x: (
                round(x.get("top", 0), 1),
                x.get("x0", 0)
            )
        )

        for index, word in enumerate(words):

            value = cls.clean_text(
                word.get("text", "")
            )

            if value.lower() != "teacher":
                continue

            teacher_parts = []

            current_top = word.get(
                "top",
                0
            )

            for next_word in words[index + 1:]:

                next_top = next_word.get(
                    "top",
                    0
                )

                if abs(
                    next_top - current_top
                ) > 5:

                    break

                value = cls.clean_text(
                    next_word.get(
                        "text",
                        ""
                    )
                )

                if value:

                    teacher_parts.append(
                        value
                    )

            if teacher_parts:

                return cls.clean_text(
                    " ".join(
                        teacher_parts
                    )
                )

        return ""

    # ==========================================================
    # DAY DETECTION
    # ==========================================================

    @classmethod
    def detect_day(
        cls,
        value: Any
    ) -> Optional[str]:

        text = cls.clean_text(
            value
        ).lower()

        return cls.DAY_MAP.get(
            text
        )

    # ==========================================================
    # SLOT HEADER
    # ==========================================================

    @staticmethod
    def parse_slot_header(
        value: Any
    ) -> Optional[int]:

        if value is None:
            return None

        text = str(value).strip()

        match = re.match(
            r"^\s*(\d+)",
            text
        )

        if not match:
            return None

        try:

            slot = int(
                match.group(1)
            )

            if 1 <= slot <= 8:
                return slot

        except ValueError:
            pass

        return None

    # ==========================================================
    # TIME EXTRACTION
    # ==========================================================

    @classmethod
    def parse_time(
        cls,
        value: Any
    ) -> str:

        text = cls.clean_text(
            value
        )

        match = re.search(
            r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})",
            text
        )

        if not match:

            return ""

        h1, m1 = match.group(1).split(":")
        h2, m2 = match.group(2).split(":")

        return (
            f"{int(h1):02d}:{int(m1):02d} - "
            f"{int(h2):02d}:{int(m2):02d}"
        )

    # ==========================================================
    # SLOT HEADER DETECTION
    # ==========================================================

    @classmethod
    def detect_slot_headers(
        cls,
        row: List[Any]
    ) -> Dict[int, Dict[str, Any]]:

        result = {}

        if not row:
            return result

        for index, cell in enumerate(row):

            if cell is None:
                continue

            text = str(cell).strip()

            slot = cls.parse_slot_header(
                text
            )

            if slot is None:
                continue

            slot_time = cls.parse_time(
                text
            )

            if not slot_time:

                slot_time = cls.SLOT_TIMES.get(
                    slot,
                    ""
                )

            result[index] = {
                "slot": slot,
                "time": slot_time,
            }

        return result

    # ==========================================================
    # CLASS DETECTION
    # ==========================================================

    @staticmethod
    def detect_class(
        text: str
    ) -> str:

        if not text:
            return ""

        patterns = [

            # 3CS-DS-A
            r"\b\d+[A-Za-z]{2,}(?:-[A-Za-z0-9]+)+\b",

            # 7CS-IOT
            r"\b\d+[A-Za-z]{2,}[A-Za-z0-9-]*\b",
        ]

        candidates = []

        for pattern in patterns:

            found = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE
            )

            candidates.extend(
                found
            )

        if not candidates:
            return ""

        # Remove obvious room-like values
        candidates = [
            x for x in candidates
            if not re.fullmatch(
                r"\d+",
                x
            )
        ]

        if not candidates:
            return ""

        # Prefer class names containing '-'
        dashed = [
            x for x in candidates
            if "-" in x
        ]

        if dashed:
            return max(
                dashed,
                key=len
            )

        return max(
            candidates,
            key=len
        )

    # ==========================================================
    # ROOM DETECTION
    # ==========================================================

    @staticmethod
    def detect_room(
        text: str
    ) -> str:

        if not text:
            return ""

        candidates = []

        # CL-15
        candidates.extend(
            re.findall(
                r"\b[A-Za-z]{1,10}-[A-Za-z0-9:]*\d+[A-Za-z0-9:-]*\b",
                text
            )
        )

        # 7F:EE-Lab13
        candidates.extend(
            re.findall(
                r"\b[A-Za-z0-9]+:+[A-Za-z0-9:-]*\d+[A-Za-z0-9:-]*\b",
                text
            )
        )

        # 301 / 103 / 306
        candidates.extend(
            re.findall(
                r"\b\d{2,4}\b",
                text
            )
        )

        if not candidates:
            return ""

        class_name = (
            PDFImporter.detect_class(
                text
            )
        )

        filtered = [
            x for x in candidates
            if x.lower() != class_name.lower()
        ]

        if filtered:
            candidates = filtered

        # Prefer CL-/Lab-like identifiers
        structured = [
            x for x in candidates
            if "-" in x or ":" in x
        ]

        if structured:
            return structured[-1]

        return candidates[-1]

    # ==========================================================
    # SUBJECT DETECTION
    # ==========================================================

    @classmethod
    def detect_subject(
        cls,
        text: str
    ) -> str:

        text = cls.clean_text(
            text
        )

        if not text:
            return ""

        lines = [
            cls.clean_text(x)
            for x in text.splitlines()
            if cls.clean_text(x)
        ]

        if not lines:
            return ""

        # Remove group information
        lines = [
            x for x in lines
            if not re.match(
                r"^group\s*\d+",
                x,
                flags=re.IGNORECASE
            )
        ]

        if not lines:
            return ""

        class_name = cls.detect_class(
            text
        )

        room = cls.detect_room(
            text
        )

        subject = lines[0]

        if class_name:

            subject = re.sub(
                re.escape(class_name),
                "",
                subject,
                flags=re.IGNORECASE
            )

        if room:

            subject = re.sub(
                re.escape(room),
                "",
                subject,
                flags=re.IGNORECASE
            )

        subject = cls.clean_text(
            subject
        )

        return subject

    # ==========================================================
    # TYPE DETECTION
    # ==========================================================

    @staticmethod
    def detect_type(
        subject: str
    ) -> str:

        text = str(
            subject or ""
        ).lower()

        if not text:
            return ""

        if "lab" in text:
            return "Lab"

        if "seminar" in text:
            return "Seminar"

        if "tutorial" in text:
            return "Tutorial"

        return "Theory"

    # ==========================================================
    # CREATE RECORD
    # ==========================================================

    @classmethod
    def create_record(
        cls,
        teacher: str,
        day: str,
        slot: int,
        slot_time: str,
        cell_text: str,
        source_file: str,
        source_page: int
    ) -> Dict[str, Any]:

        cell_text = (
            cell_text
            if cell_text is not None
            else ""
        )

        cell_text = str(
            cell_text
        ).replace(
            "\xa0",
            " "
        ).strip()

        # ------------------------------------------------------
        # IMPORTANT:
        #
        # DO NOT remove empty cells.
        #
        # Empty cell is required to determine FREE.
        # ------------------------------------------------------

        subject = cls.detect_subject(
            cell_text
        )

        room = cls.detect_room(
            cell_text
        )

        class_name = cls.detect_class(
            cell_text
        )

        record_type = (
            "FACULTY_FREE_SLOT"
            if not cell_text
            else "FACULTY_SCHEDULED"
        )

        return {

            "teacher":
                cls.clean_text(
                    teacher
                ),

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
                "",

            "type":
                cls.detect_type(
                    subject
                ),

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

            "record_type":
                record_type,
        }

    # ==========================================================
    # TABLE EXTRACTION
    # ==========================================================

    @staticmethod
    def extract_tables_from_page(
        page
    ) -> List[List[List[Any]]]:

        try:

            tables = page.extract_tables()

            if tables:
                return tables

        except Exception:
            pass

        return []

    # ==========================================================
    # PROCESS ONE PAGE
    # ==========================================================

    @classmethod
    def process_page(
        cls,
        page,
        page_number: int,
        source_file: str
    ) -> List[Dict[str, Any]]:

        records = []

        # ------------------------------------------------------
        # Detect teacher
        # ------------------------------------------------------

        teacher = cls.detect_teacher(
            page
        )

        # ------------------------------------------------------
        # If no teacher, this page is not a faculty timetable.
        #
        # For classwise/locationwise PDFs, we still return
        # records using their existing parser later if needed.
        # ------------------------------------------------------

        if not teacher:
            return records

        # ------------------------------------------------------
        # Extract tables
        # ------------------------------------------------------

        tables = cls.extract_tables_from_page(
            page
        )

        for table in tables:

            if not table:
                continue

            slot_headers = {}
            header_index = None

            # --------------------------------------------------
            # Find row containing:
            #
            # 1 2 3 4 5 6 7 8
            # --------------------------------------------------

            for row_index, row in enumerate(
                table
            ):

                if not row:
                    continue

                detected = (
                    cls.detect_slot_headers(
                        row
                    )
                )

                if len(detected) >= 4:

                    slot_headers = detected
                    header_index = row_index
                    break

            if not slot_headers:
                continue

            # --------------------------------------------------
            # Process day rows
            # --------------------------------------------------

            for row in table[
                header_index + 1:
            ]:

                if not row:
                    continue

                if not row[0]:
                    continue

                day = cls.detect_day(
                    row[0]
                )

                if not day:
                    continue

                # ------------------------------------------------
                # VERY IMPORTANT:
                #
                # Iterate over ALL slot columns.
                #
                # Do NOT skip None.
                # None means FREE.
                # ------------------------------------------------

                for column_index, slot_info in (
                    slot_headers.items()
                ):

                    if column_index >= len(row):
                        continue

                    cell = row[
                        column_index
                    ]

                    if cell is None:
                        cell = ""

                    record = cls.create_record(
                        teacher=teacher,
                        day=day,
                        slot=slot_info["slot"],
                        slot_time=slot_info["time"],
                        cell_text=cell,
                        source_file=source_file,
                        source_page=page_number,
                    )

                    records.append(
                        record
                    )

        return records

    # ==========================================================
    # IMPORT FILE
    # ==========================================================

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

                page_records = (
                    cls.process_page(
                        page,
                        page_number,
                        path.name
                    )
                )

                records.extend(
                    page_records
                )

        return records

    # ==========================================================
    # INSPECT FILE
    # ==========================================================

    @classmethod
    def inspect_file(
        cls,
        file_path: str | Path
    ) -> Dict[str, Any]:

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

        pages = 0
        pages_with_teacher = 0
        pages_with_tables = 0
        total_records = 0

        with pdfplumber.open(
            path
        ) as pdf:

            pages = len(
                pdf.pages
            )

            for page_number, page in enumerate(
                pdf.pages,
                start=1
            ):

                teacher = cls.detect_teacher(
                    page
                )

                if teacher:
                    pages_with_teacher += 1

                tables = cls.extract_tables_from_page(
                    page
                )

                if tables:
                    pages_with_tables += 1

                total_records += len(
                    cls.process_page(
                        page,
                        page_number,
                        path.name
                    )
                )

        return {

            "file":
                path.name,

            "size_bytes":
                validation["size_bytes"],

            "size_mb":
                validation["size_mb"],

            "pages":
                pages,

            "pages_with_teacher":
                pages_with_teacher,

            "pages_with_tables":
                pages_with_tables,

            "records":
                total_records,

            "dataset_type":
                "FACULTYWISE"
                if pages_with_teacher
                else "UNKNOWN",
        }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 80)

    print(
        "UNISCHED AI - PDF IMPORTER"
    )

    print("=" * 80)

    pdf = (
        "data/Facultywise TT 20 sep.pdf"
    )

    records = (
        PDFImporter.import_file(
            pdf
        )
    )

    print(
        "Imported records:",
        len(records)
    )

    archika = [

        r for r in records

        if (
            "archika"
            in str(
                r.get(
                    "teacher",
                    ""
                )
            ).lower()
        )

        and r.get("day")
        == "monday"
    ]

    print()
    print(
        "ARCHIKA MONDAY"
    )

    print("-" * 80)

    for record in archika:

        print(
            record
        )