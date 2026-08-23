"""
==========================================================
UNISCHED AI - PDF SEMANTIC PARSER BENCHMARK
==========================================================

Purpose
-------
Benchmark the semantic parser against the actual timetable
PDF imported by PDFImporter.

IMPORTANT
---------
This script does NOT modify:
    - PDFImporter
    - QueryEngine
    - canonical data
    - database
    - timetable files

It only measures extraction quality.

==========================================================
"""

from __future__ import annotations

import os
import sys
from collections import Counter

# ----------------------------------------------------------
# Make project root importable when this file is executed
# directly.
# ----------------------------------------------------------

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )

from import_engine.pdf_importer import PDFImporter
from import_engine.pdf_semantic_parser import (
    PDFSemanticParser,
)


PDF_FILES = [
    "data/Facultywise TT 20 sep.pdf",
    "data/classwise TT 27 sep.pdf",
    "data/Location wise TT 27 sep 2025.pdf",
]


def count_nonempty(
    records,
    field,
):
    return sum(
        1
        for record in records
        if str(
            record.get(
                field,
                ""
            )
        ).strip()
    )


def unique_values(
    records,
    field,
):
    values = set()

    for record in records:

        value = str(
            record.get(
                field,
                ""
            )
        ).strip()

        if value:
            values.add(
                value
            )

    return values


def print_summary(
    name,
    records,
):
    total = len(records)

    print()
    print("=" * 80)
    print(
        f"DATASET: {name}"
    )
    print("=" * 80)

    print(
        f"Total records        : {total:,}"
    )

    for field in [
        "teacher",
        "teacher_code",
        "subject",
        "room",
        "class_name",
        "group_name",
    ]:

        count = count_nonempty(
            records,
            field,
        )

        percentage = (
            count / total * 100
            if total
            else 0
        )

        print(
            f"{field:<20}: "
            f"{count:,} "
            f"({percentage:6.2f}%)"
        )


def compare_fields(
    original,
    parsed,
):
    fields = [
        "teacher",
        "teacher_code",
        "subject",
        "room",
        "class_name",
        "group_name",
    ]

    print()
    print(
        "=" * 80
    )
    print(
        "FIELD COMPARISON"
    )
    print(
        "=" * 80
    )

    print(
        f"{'FIELD':<20}"
        f"{'ORIGINAL':>12}"
        f"{'PARSED':>12}"
        f"{'CHANGE':>12}"
    )

    print("-" * 80)

    for field in fields:

        original_count = (
            count_nonempty(
                original,
                field,
            )
        )

        parsed_count = (
            count_nonempty(
                parsed,
                field,
            )
        )

        change = (
            parsed_count
            - original_count
        )

        print(
            f"{field:<20}"
            f"{original_count:>12,}"
            f"{parsed_count:>12,}"
            f"{change:>+12,}"
        )


def show_changed_records(
    original,
    parsed,
    limit=20,
):
    print()
    print(
        "=" * 80
    )
    print(
        f"SAMPLE SEMANTIC CHANGES "
        f"(first {limit})"
    )
    print(
        "=" * 80
    )

    shown = 0

    for old, new in zip(
        original,
        parsed,
    ):

        old_values = {
            key: str(
                old.get(
                    key,
                    ""
                )
            ).strip()
            for key in [
                "teacher",
                "teacher_code",
                "subject",
                "room",
                "class_name",
                "group_name",
            ]
        }

        new_values = {
            key: str(
                new.get(
                    key,
                    ""
                )
            ).strip()
            for key in [
                "teacher",
                "teacher_code",
                "subject",
                "room",
                "class_name",
                "group_name",
            ]
        }

        if old_values == new_values:
            continue

        print()
        print(
            f"RAW: "
            f"{old.get('raw_text', '')}"
        )

        for field in old_values:

            old_value = old_values[field]
            new_value = new_values[field]

            if old_value != new_value:

                print(
                    f"  {field:<15}: "
                    f"{old_value!r} "
                    f"-> "
                    f"{new_value!r}"
                )

        shown += 1

        if shown >= limit:
            break

    if shown == 0:

        print(
            "No semantic changes detected."
        )


def suspicious_records(
    parsed,
):
    """
    Find records that deserve manual inspection.

    These are not automatically errors.
    They are simply unusual records.
    """

    suspicious = []

    for record in parsed:

        raw = str(
            record.get(
                "raw_text",
                ""
            )
        ).strip()

        subject = str(
            record.get(
                "subject",
                ""
            )
        ).strip()

        teacher_code = str(
            record.get(
                "teacher_code",
                ""
            )
        ).strip()

        room = str(
            record.get(
                "room",
                ""
            )
        ).strip()

        class_name = str(
            record.get(
                "class_name",
                ""
            )
        ).strip()

        # Empty raw text is not useful for semantic parsing.
        if not raw:
            continue

        # Subject consisting of one suspiciously short token.
        if (
            subject
            and len(subject) <= 2
            and not class_name
            and not room
        ):
            suspicious.append(
                (
                    "short_subject",
                    record,
                )
            )

        # Unknown teacher code.
        if (
            teacher_code
            and not record.get(
                "teacher"
            )
        ):
            suspicious.append(
                (
                    "unresolved_teacher_code",
                    record,
                )
            )

    return suspicious


def benchmark_file(
    pdf_path,
):
    print()
    print("#" * 80)
    print(
        f"PROCESSING: {pdf_path}"
    )
    print("#" * 80)

    if not os.path.exists(
        pdf_path
    ):

        print(
            f"ERROR: File not found: "
            f"{pdf_path}"
        )

        return

    # ------------------------------------------------------
    # Import using the existing PDFImporter.
    # ------------------------------------------------------

    original = (
        PDFImporter.import_file(
            pdf_path
        )
    )

    print()
    print(
        f"PDFImporter records: "
        f"{len(original):,}"
    )

    # ------------------------------------------------------
    # Build semantic parser.
    # ------------------------------------------------------

    parser = PDFSemanticParser()

    # ------------------------------------------------------
    # Parse records.
    # ------------------------------------------------------

    parsed = (
        parser.parse_records(
            original
        )
    )

    print(
        f"Semantic records   : "
        f"{len(parsed):,}"
    )

    # ------------------------------------------------------
    # Basic summaries.
    # ------------------------------------------------------

    print_summary(
        "ORIGINAL",
        original,
    )

    print_summary(
        "SEMANTIC",
        parsed,
    )

    # ------------------------------------------------------
    # Compare extraction.
    # ------------------------------------------------------

    compare_fields(
        original,
        parsed,
    )

    # ------------------------------------------------------
    # Show changes.
    # ------------------------------------------------------

    show_changed_records(
        original,
        parsed,
        limit=20,
    )

    # ------------------------------------------------------
    # Suspicious records.
    # ------------------------------------------------------

    suspicious = (
        suspicious_records(
            parsed
        )
    )

    print()
    print(
        "=" * 80
    )
    print(
        "SEMANTIC QUALITY FLAGS"
    )
    print(
        "=" * 80
    )

    counter = Counter(
        category
        for category, _ in suspicious
    )

    if not counter:

        print(
            "No suspicious records detected."
        )

    else:

        for category, count in (
            counter.most_common()
        ):

            print(
                f"{category:<30}: "
                f"{count:,}"
            )

    # ------------------------------------------------------
    # Sample suspicious records.
    # ------------------------------------------------------

    if suspicious:

        print()
        print(
            "=" * 80
        )
        print(
            "SAMPLE SUSPICIOUS RECORDS"
        )
        print(
            "=" * 80
        )

        for category, record in (
            suspicious[:20]
        ):

            print()
            print(
                f"[{category}]"
            )

            print(
                f"Raw       : "
                f"{record.get('raw_text', '')}"
            )

            print(
                f"Subject   : "
                f"{record.get('subject', '')}"
            )

            print(
                f"Teacher   : "
                f"{record.get('teacher', '')}"
            )

            print(
                f"Code      : "
                f"{record.get('teacher_code', '')}"
            )

            print(
                f"Room      : "
                f"{record.get('room', '')}"
            )

            print(
                f"Class     : "
                f"{record.get('class_name', '')}"
            )

    return original, parsed


def main():

    print("=" * 80)

    print(
        "UNISCHED AI - PDF SEMANTIC "
        "PARSER BENCHMARK"
    )

    print("=" * 80)

    print()
    print(
        "This benchmark DOES NOT modify "
        "the existing project."
    )

    print(
        "It only compares PDFImporter "
        "output with semantic parsing."
    )

    results = []

    for pdf_path in PDF_FILES:

        result = benchmark_file(
            pdf_path
        )

        if result:

            results.append(
                (
                    pdf_path,
                    result,
                )
            )

    # ------------------------------------------------------
    # Final summary.
    # ------------------------------------------------------

    print()
    print("#" * 80)
    print(
        "FINAL BENCHMARK SUMMARY"
    )
    print("#" * 80)

    for pdf_path, (
        original,
        parsed,
    ) in results:

        print()
        print(
            os.path.basename(
                pdf_path
            )
        )

        print(
            f"  Original : "
            f"{len(original):,}"
        )

        print(
            f"  Parsed   : "
            f"{len(parsed):,}"
        )

    print()
    print("=" * 80)
    print(
        "BENCHMARK COMPLETED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()