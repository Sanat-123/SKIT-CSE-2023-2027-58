"""
UNISCHED AI
Universal Excel/CSV Timetable Layout Benchmark

This benchmark does not require real files.

It creates representative timetable layouts
and verifies that the universal parser can
understand them.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from import_engine.universal_schedule_parser import (
    UniversalScheduleParser,
)


def run_test(
    name,
    records,
    expected_layout,
):

    parser = UniversalScheduleParser()

    parsed = parser.parse(
        records,
        source_file=name,
        source_type="benchmark",
    )

    actual_layout = parser.report()["layout"]

    passed = actual_layout == expected_layout

    print()
    print("=" * 80)
    print(name)
    print("=" * 80)

    print("Expected layout :", expected_layout)
    print("Detected layout :", actual_layout)
    print("Input records   :", len(records))
    print("Output records  :", len(parsed))

    if parsed:
        print("First record:")
        print(parsed[0])

    print("RESULT          :", "PASS" if passed else "FAIL")

    return passed


def main():

    tests = []

    # --------------------------------------------------------------
    # TEST 1
    # Row-based timetable
    # --------------------------------------------------------------

    tests.append(
        (
            "TEST 1 - ROW BASED",
            [
                {
                    "Teacher": "Dr. ABC",
                    "Day": "Monday",
                    "Slot": 1,
                    "Subject": "Operating Systems",
                    "Room": "301",
                    "Class": "3CS-A",
                },
                {
                    "Teacher": "Dr. ABC",
                    "Day": "Monday",
                    "Slot": 2,
                    "Subject": "DBMS",
                    "Room": "302",
                    "Class": "3CS-A",
                },
            ],
            "ROW_BASED",
        )
    )

    # --------------------------------------------------------------
    # TEST 2
    # Row-based with time
    # --------------------------------------------------------------

    tests.append(
        (
            "TEST 2 - ROW BASED WITH TIME",
            [
                {
                    "Faculty": "Dr. XYZ",
                    "Day": "Mon",
                    "Time": "09:15 - 10:15",
                    "Course": "Computer Networks",
                    "Classroom": "303",
                    "Section": "3CS-B",
                },
                {
                    "Faculty": "Dr. XYZ",
                    "Day": "Tue",
                    "Time": "10:15 - 11:15",
                    "Course": "DBMS",
                    "Classroom": "304",
                    "Section": "3CS-B",
                },
            ],
            "ROW_BASED",
        )
    )

    # --------------------------------------------------------------
    # TEST 3
    # Day-column timetable
    # --------------------------------------------------------------

    tests.append(
        (
            "TEST 3 - DAY COLUMNS",
            [
                {
                    "Teacher": "Dr. PQR",
                    "Class": "4CS-A",
                    "Monday": "OS",
                    "Tuesday": "DBMS",
                    "Wednesday": "Free",
                    "Thursday": "CN",
                    "Friday": "Java",
                },
            ],
            "DAY_COLUMNS",
        )
    )

    # --------------------------------------------------------------
    # TEST 4
    # Period-column timetable
    # --------------------------------------------------------------

    tests.append(
        (
            "TEST 4 - PERIOD COLUMNS",
            [
                {
                    "Faculty": "Dr. LMN",
                    "Class": "5CS-A",
                    "P1": "OS",
                    "P2": "DBMS",
                    "P3": "Free",
                    "P4": "CN",
                    "P5": "Java",
                },
            ],
            "PERIOD_COLUMNS",
        )
    )

    # --------------------------------------------------------------
    # TEST 5
    # Matrix timetable
    # --------------------------------------------------------------

    tests.append(
        (
            "TEST 5 - MATRIX",
            [
                {
                    "Time": "08:15 - 09:15",
                    "Monday": "OS",
                    "Tuesday": "DBMS",
                    "Wednesday": "Free",
                    "Thursday": "CN",
                    "Friday": "Java",
                },
                {
                    "Time": "09:15 - 10:15",
                    "Monday": "DBMS",
                    "Tuesday": "Free",
                    "Wednesday": "OS",
                    "Thursday": "Java",
                    "Friday": "CN",
                },
            ],
            "MATRIX",
        )
    )

    passed = 0

    print()
    print("=" * 80)
    print("UNISCHED AI - UNIVERSAL TIMETABLE BENCHMARK")
    print("=" * 80)

    for name, records, expected in tests:

        if run_test(
            name,
            records,
            expected,
        ):
            passed += 1

    print()
    print("=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)

    print("Tests :", len(tests))
    print("Passed:", passed)
    print("Failed:", len(tests) - passed)

    if passed == len(tests):
        print()
        print("ALL UNIVERSAL FORMAT TESTS PASSED")
    else:
        print()
        print("SOME TESTS FAILED")

    print("=" * 80)


if __name__ == "__main__":
    main()