from import_engine.pdf_importer import PDFImporter
from import_engine.universal_schedule_parser import UniversalScheduleParser


FILES = [
    "data/Facultywise TT 20 sep.pdf",
    "data/classwise TT 27 sep.pdf",
    "data/Location wise TT 27 sep 2025.pdf",
]


def check_pdf_format(file_path, parser):
    print()
    print("=" * 80)
    print("FILE:", file_path)
    print("=" * 80)

    # ---------------------------------------------------------
    # STEP 1: Import PDF
    # ---------------------------------------------------------
    imported = PDFImporter.import_file(file_path)

    print("Imported records:", len(imported))

    assert imported, f"No records imported from {file_path}"

    # ---------------------------------------------------------
    # STEP 2: Universal parsing
    # IMPORTANT:
    # UniversalScheduleParser uses parse(), not parse_records()
    # ---------------------------------------------------------
    parsed = parser.parse(
        imported,
        source_file=file_path,
        source_type="pdf",
    )

    print("Parsed records   :", len(parsed))

    assert parsed, f"No records parsed from {file_path}"

    # ---------------------------------------------------------
    # STEP 3: Show first record
    # ---------------------------------------------------------
    print()
    print("FIRST PARSED RECORD:")
    print(parsed[0])

    # ---------------------------------------------------------
    # STEP 4: Statistics
    # ---------------------------------------------------------
    day_count = sum(
        1
        for record in parsed
        if str(record.get("day", "")).strip()
    )

    slot_count = sum(
        1
        for record in parsed
        if record.get("slot") is not None
    )

    time_count = sum(
        1
        for record in parsed
        if str(record.get("slot_time", "")).strip()
    )

    teacher_count = sum(
        1
        for record in parsed
        if str(record.get("teacher", "")).strip()
    )

    subject_count = sum(
        1
        for record in parsed
        if str(record.get("subject", "")).strip()
    )

    class_count = sum(
        1
        for record in parsed
        if str(record.get("class_name", "")).strip()
    )

    room_count = sum(
        1
        for record in parsed
        if str(record.get("room", "")).strip()
    )

    print()
    print("STATISTICS")
    print("-" * 80)
    print("Day records       :", day_count)
    print("Slot records      :", slot_count)
    print("Time records      :", time_count)
    print("Teacher records   :", teacher_count)
    print("Subject records   :", subject_count)
    print("Class records     :", class_count)
    print("Room records      :", room_count)

    return parsed


def main():

    print("=" * 80)
    print("UNISCHED AI - REAL PDF FORMAT TEST")
    print("=" * 80)

    parser = UniversalScheduleParser()

    results = {}
    failed = []

    for file_path in FILES:

        try:

            results[file_path] = check_pdf_format(
                file_path,
                parser,
            )

            print()
            print("RESULT          : PASS")

        except Exception as exc:

            failed.append(file_path)

            print()
            print("RESULT          : FAIL")
            print(
                type(exc).__name__,
                ":",
                exc,
            )

    # ---------------------------------------------------------
    # FINAL SUMMARY
    # ---------------------------------------------------------
    print()
    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print("Files tested :", len(FILES))
    print("Passed       :", len(results))
    print("Failed       :", len(failed))

    for file_path, records in results.items():

        print(
            "PASS:",
            file_path,
            "->",
            len(records),
            "records",
        )

    for file_path in failed:

        print(
            "FAIL:",
            file_path,
        )

    print()
    print("=" * 80)

    if not failed:
        print("ALL REAL PDF FORMAT TESTS PASSED")
    else:
        print("SOME REAL PDF FORMAT TESTS FAILED")

    print("=" * 80)


if __name__ == "__main__":
    main()