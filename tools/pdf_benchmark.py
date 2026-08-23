"""
==========================================================
UNISCHED AI - UNIVERSAL PDF BENCHMARK
==========================================================

Purpose
-------
Inspect timetable PDFs using the CURRENT PDFImporter.

This script is intentionally non-destructive.

It does NOT modify:
    - pdf_importer.py
    - canonical data
    - database
    - query engine

It only reports what the current PDF importer detects.

==========================================================
"""

from __future__ import annotations

import sys
from pathlib import Path


# ==========================================================
# PROJECT ROOT
# ==========================================================
# pdf_benchmark.py is inside:
#
# Faculty_Free_Slot_AI/
# └── tools/
#     └── pdf_benchmark.py
#
# Therefore parent.parent is the project root.
# This allows:
#
# from import_engine.pdf_importer import PDFImporter
#
# to work correctly.
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ==========================================================
# IMPORT PDF IMPORTER
# ==========================================================

from import_engine.pdf_importer import PDFImporter


# ==========================================================
# CONFIGURATION
# ==========================================================

DATA_DIR = PROJECT_ROOT / "data"

PDF_FILES = [
    "Facultywise TT 20 sep.pdf",
    "classwise TT 27 sep.pdf",
    "Location wise TT 27 sep 2025.pdf",
]


# ==========================================================
# PRINT SECTION
# ==========================================================

def print_section(title: str) -> None:
    """
    Print a formatted section heading.
    """

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


# ==========================================================
# SAFE VALUE
# ==========================================================

def safe_value(value) -> str:
    """
    Convert any value into a printable string.
    """

    if value is None:
        return ""

    return str(value)


# ==========================================================
# BENCHMARK ONE PDF
# ==========================================================

def benchmark_file(file_path: Path) -> None:
    """
    Inspect and import one PDF without modifying project data.
    """

    print_section(
        f"PDF: {file_path.name}"
    )

    # ------------------------------------------------------
    # FILE EXISTENCE
    # ------------------------------------------------------

    if not file_path.exists():

        print(
            f"ERROR: File not found:"
        )

        print(
            f"       {file_path}"
        )

        return

    # ------------------------------------------------------
    # BASIC FILE INFORMATION
    # ------------------------------------------------------

    print(
        f"Path       : {file_path}"
    )

    print(
        f"Size (MB)  : "
        f"{file_path.stat().st_size / (1024 * 1024):.2f}"
    )

    # ------------------------------------------------------
    # INSPECTION
    # ------------------------------------------------------

    print_section(
        "STRUCTURE DETECTION"
    )

    try:

        inspection = PDFImporter.inspect_file(
            file_path
        )

    except Exception as exc:

        print(
            "INSPECTION ERROR:"
        )

        print(
            repr(exc)
        )

        return

    # ------------------------------------------------------
    # DISPLAY INSPECTION INFORMATION
    # ------------------------------------------------------

    inspection_fields = [
        "pages",
        "pages_with_text",
        "pages_with_tables",
        "total_tables",
        "pages_with_slot_headers",
        "pages_with_day_rows",
        "pages_with_teacher",
        "dataset_type",
        "has_day",
        "has_slot",
        "has_teacher",
    ]

    for field in inspection_fields:

        value = inspection.get(
            field,
            "N/A"
        )

        print(
            f"{field:<30}: {value}"
        )

    # ------------------------------------------------------
    # FULL IMPORT
    # ------------------------------------------------------

    print_section(
        "CURRENT IMPORT RESULT"
    )

    try:

        records = PDFImporter.import_file(
            file_path
        )

    except Exception as exc:

        print(
            "IMPORT ERROR:"
        )

        print(
            repr(exc)
        )

        return

    print(
        f"Records imported           : "
        f"{len(records)}"
    )

    # ------------------------------------------------------
    # RECORD TYPES
    # ------------------------------------------------------

    record_types = {}

    for record in records:

        record_type = safe_value(
            record.get(
                "record_type",
                "NORMAL"
            )
        )

        if not record_type:
            record_type = "NORMAL"

        record_types[record_type] = (
            record_types.get(
                record_type,
                0
            ) + 1
        )

    print()
    print(
        "Record types:"
    )

    if record_types:

        for name, count in sorted(
            record_types.items()
        ):

            print(
                f"  {name:<30}: {count}"
            )

    else:

        print(
            "  No record types detected."
        )

    # ------------------------------------------------------
    # DAYS
    # ------------------------------------------------------

    days = {}

    for record in records:

        day = safe_value(
            record.get(
                "day",
                ""
            )
        ).strip()

        if day:

            days[day] = (
                days.get(
                    day,
                    0
                ) + 1
            )

    print()
    print(
        "Detected days:"
    )

    if days:

        for day, count in sorted(
            days.items()
        ):

            print(
                f"  {day:<20}: {count}"
            )

    else:

        print(
            "  No day values detected."
        )

    # ------------------------------------------------------
    # SLOTS
    # ------------------------------------------------------

    slots = {}

    for record in records:

        slot = record.get(
            "slot"
        )

        if slot is not None:

            slot_key = safe_value(
                slot
            )

            slots[slot_key] = (
                slots.get(
                    slot_key,
                    0
                ) + 1
            )

    print()
    print(
        "Detected slots:"
    )

    if slots:

        for slot, count in sorted(
            slots.items(),
            key=lambda item: item[0]
        ):

            print(
                f"  {slot:<20}: {count}"
            )

    else:

        print(
            "  No slot values detected."
        )

    # ------------------------------------------------------
    # SLOT TIMES
    # ------------------------------------------------------

    slot_times = {}

    for record in records:

        slot_time = safe_value(
            record.get(
                "slot_time",
                ""
            )
        ).strip()

        if slot_time:

            slot_times[slot_time] = (
                slot_times.get(
                    slot_time,
                    0
                ) + 1
            )

    print()
    print(
        "Detected slot times:"
    )

    if slot_times:

        for time_value, count in list(
            slot_times.items()
        )[:20]:

            print(
                f"  {time_value:<25}: {count}"
            )

    else:

        print(
            "  No slot times detected."
        )

    # ------------------------------------------------------
    # TEACHERS
    # ------------------------------------------------------

    teachers = set()

    for record in records:

        teacher = safe_value(
            record.get(
                "teacher",
                ""
            )
        ).strip()

        if teacher:

            teachers.add(
                teacher
            )

    print()
    print(
        f"Unique teachers detected : "
        f"{len(teachers)}"
    )

    for teacher in sorted(
        teachers
    )[:20]:

        print(
            f"  {teacher}"
        )

    if len(teachers) > 20:

        print(
            f"  ... "
            f"{len(teachers) - 20} more"
        )

    # ------------------------------------------------------
    # SUBJECTS
    # ------------------------------------------------------

    subjects = set()

    for record in records:

        subject = safe_value(
            record.get(
                "subject",
                ""
            )
        ).strip()

        if subject:

            subjects.add(
                subject
            )

    print()
    print(
        f"Unique subjects detected : "
        f"{len(subjects)}"
    )

    for subject in sorted(
        subjects
    )[:20]:

        print(
            f"  {subject}"
        )

    if len(subjects) > 20:

        print(
            f"  ... "
            f"{len(subjects) - 20} more"
        )

    # ------------------------------------------------------
    # CLASSES
    # ------------------------------------------------------

    classes = set()

    for record in records:

        class_name = safe_value(
            record.get(
                "class_name",
                ""
            )
        ).strip()

        if class_name:

            classes.add(
                class_name
            )

    print()
    print(
        f"Unique classes detected  : "
        f"{len(classes)}"
    )

    for class_name in sorted(
        classes
    )[:20]:

        print(
            f"  {class_name}"
        )

    if len(classes) > 20:

        print(
            f"  ... "
            f"{len(classes) - 20} more"
        )

    # ------------------------------------------------------
    # ROOMS
    # ------------------------------------------------------

    rooms = set()

    for record in records:

        room = safe_value(
            record.get(
                "room",
                ""
            )
        ).strip()

        if room:

            rooms.add(
                room
            )

    print()
    print(
        f"Unique rooms detected    : "
        f"{len(rooms)}"
    )

    for room in sorted(
        rooms
    )[:20]:

        print(
            f"  {room}"
        )

    if len(rooms) > 20:

        print(
            f"  ... "
            f"{len(rooms) - 20} more"
        )

    # ------------------------------------------------------
    # PARTIAL RECORD ANALYSIS
    # ------------------------------------------------------

    no_teacher = 0
    no_subject = 0
    no_class = 0
    no_room = 0
    no_day = 0
    no_slot = 0

    for record in records:

        if not safe_value(
            record.get("teacher")
        ).strip():

            no_teacher += 1

        if not safe_value(
            record.get("subject")
        ).strip():

            no_subject += 1

        if not safe_value(
            record.get("class_name")
        ).strip():

            no_class += 1

        if not safe_value(
            record.get("room")
        ).strip():

            no_room += 1

        if not safe_value(
            record.get("day")
        ).strip():

            no_day += 1

        if record.get("slot") is None:

            no_slot += 1

    print_section(
        "PARTIAL RECORD ANALYSIS"
    )

    print(
        f"Missing teacher : {no_teacher}"
    )

    print(
        f"Missing subject : {no_subject}"
    )

    print(
        f"Missing class   : {no_class}"
    )

    print(
        f"Missing room    : {no_room}"
    )

    print(
        f"Missing day     : {no_day}"
    )

    print(
        f"Missing slot    : {no_slot}"
    )

    # ------------------------------------------------------
    # SAMPLE RECORDS
    # ------------------------------------------------------

    print_section(
        "SAMPLE RECORDS"
    )

    if not records:

        print(
            "No records imported."
        )

        return

    for index, record in enumerate(
        records[:5],
        start=1
    ):

        print()
        print(
            f"RECORD {index}"
        )

        for key, value in record.items():

            print(
                f"  {key:<24}: "
                f"{value}"
            )


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:
    """
    Run the benchmark against all configured PDFs.
    """

    print("=" * 80)

    print(
        "UNISCHED AI - UNIVERSAL PDF BENCHMARK"
    )

    print("=" * 80)

    print(
        "This benchmark does not modify project data."
    )

    print(
        f"Project root: {PROJECT_ROOT}"
    )

    print(
        f"Data directory: {DATA_DIR}"
    )

    for filename in PDF_FILES:

        file_path = (
            DATA_DIR / filename
        )

        benchmark_file(
            file_path
        )

    print_section(
        "BENCHMARK COMPLETED"
    )

    print(
        "No project files were modified."
    )


# ==========================================================
# ENTRY POINT
# ==========================================================

if __name__ == "__main__":

    main()