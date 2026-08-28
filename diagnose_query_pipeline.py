"""
UNISCHED AI - CURRENT QUERY PIPELINE DIAGNOSTIC

Run from project root:

    python diagnose_query_pipeline.py
"""

from import_engine.import_manager import ImportManager
from data_engine.canonical_event_matcher import CanonicalEventMatcher
from query_engine import QueryEngine, NaturalLanguageQuery

import inspect
from collections import Counter


# ============================================================
# REAL FILES
# ============================================================

FILES = [
    "data/Facultywise TT 20 sep.pdf",
    "data/classwise TT 27 sep.pdf",
    "data/Location wise TT 27 sep 2025.pdf",
]


# ============================================================
# STEP 0
# ============================================================

print("=" * 70)
print("STEP 0: CURRENT CODE CHECK")
print("=" * 70)

print(
    "QueryEngine source:",
    inspect.getsourcefile(QueryEngine)
)

print(
    "Has _faculty_records:",
    hasattr(QueryEngine, "_faculty_records")
)

print(
    "Has _faculty_source:",
    hasattr(QueryEngine, "_faculty_source")
)

print(
    "Has faculty_free_slots:",
    hasattr(QueryEngine, "faculty_free_slots")
)

print(
    "Has faculty_free_for_period:",
    hasattr(QueryEngine, "faculty_free_for_period")
)

print(
    "NaturalLanguageQuery has extract_time_range:",
    hasattr(NaturalLanguageQuery, "extract_time_range")
)


# ============================================================
# STEP 1 - IMPORT
# ============================================================

print()
print("=" * 70)
print("STEP 1: IMPORT FILES")
print("=" * 70)

manager = ImportManager()

all_records = []

for file_path in FILES:

    result = manager.import_file(file_path)

    records = (
        result.get("records", [])
        if isinstance(result, dict)
        else result
    )

    print()
    print("FILE:", file_path)
    print("Success:", result.get("success") if isinstance(result, dict) else "N/A")
    print("Records:", len(records))

    if isinstance(result, dict):

        if result.get("error"):
            print("ERROR:", result["error"])

        if result.get("warnings"):
            print("Warnings:", result["warnings"])

    if records:
        print("First record:")
        print(records[0])

    all_records.extend(records)


print()
print("TOTAL COMBINED RECORDS:", len(all_records))


# ============================================================
# STEP 2 - CANONICALIZE
# ============================================================

print()
print("=" * 70)
print("STEP 2: CANONICALIZE")
print("=" * 70)

matcher = CanonicalEventMatcher(all_records)

matcher.match()

print(
    "Canonical events:",
    len(matcher.events)
)

print(
    "Faculty free slots:",
    len(matcher.faculty_free_slots)
)

print(
    "Class free slots:",
    len(matcher.class_free_slots)
)

print(
    "Room free slots:",
    len(matcher.room_free_slots)
)


# ============================================================
# STEP 3 - QUERY ENGINE
# ============================================================

print()
print("=" * 70)
print("STEP 3: QUERY ENGINE")
print("=" * 70)

engine = QueryEngine(matcher)

faculty_records = engine._faculty_records()

print(
    "_faculty_records() count:",
    len(faculty_records)
)

if faculty_records:

    print()
    print("FIRST FACULTY RECORD:")
    print(faculty_records[0])

else:

    print()
    print("!!! _faculty_records() IS EMPTY !!!")


# ============================================================
# STEP 4 - FACULTY FREE SLOT
# ============================================================

print()
print("=" * 70)
print("STEP 4: DIRECT FACULTY FREE QUERY")
print("=" * 70)

try:

    result = engine.faculty_free_slots(
        day="Monday",
        slot=2
    )

    print(
        "faculty_free_slots(day='Monday', slot=2):"
    )

    print(result)

except Exception as error:

    print(
        "ERROR:",
        type(error).__name__,
        error
    )


# ============================================================
# STEP 5 - FACULTY FREE PERIOD
# ============================================================

print()
print("=" * 70)
print("STEP 5: FACULTY FREE PERIOD QUERY")
print("=" * 70)

try:

    result = engine.faculty_free_for_period(
        day="Monday",
        start_time="09:00",
        end_time="11:00"
    )

    print(
        "faculty_free_for_period("
        "Monday, 09:00-11:00):"
    )

    print(result)

except Exception as error:

    print(
        "ERROR:",
        type(error).__name__,
        error
    )


# ============================================================
# STEP 6 - NATURAL LANGUAGE QUERY
# ============================================================

print()
print("=" * 70)
print("STEP 6: NATURAL LANGUAGE QUERY")
print("=" * 70)

nlp = NaturalLanguageQuery(engine)

queries = [
    "Who is free on Monday slot 2?",
    "Who is free on Monday from 9 AM to 11 AM?",
    "Who is free on Monday from 1:30 PM to 3:30 PM?",
]


for question in queries:

    print()
    print("-" * 70)
    print("QUESTION:", question)
    print("-" * 70)

    try:

        print(
            "Day:",
            nlp.extract_day(question)
        )

        print(
            "Slot:",
            nlp.extract_slot(question)
        )

        if hasattr(
            nlp,
            "extract_time_range"
        ):

            print(
                "Time range:",
                nlp.extract_time_range(question)
            )

        print(
            "Intent:",
            nlp.detect_intent(question)
        )

        answer = nlp.answer(question)

        print()
        print("ANSWER:")
        print(answer)

    except Exception as error:

        print(
            "ERROR:",
            type(error).__name__,
            error
        )


# ============================================================
# STEP 7 - DUPLICATE CHECK
# ============================================================

print()
print("=" * 70)
print("STEP 7: DUPLICATE CHECK - MONDAY SLOT 2")
print("=" * 70)

monday_slot2 = [
    record
    for record in faculty_records
    if engine._day(record.get("day")) == "monday"
    and engine._slot(record.get("slot")) == 2
]

teacher_counts = Counter(
    engine._normalize(
        record.get("teacher")
    )
    for record in monday_slot2
)

duplicates = {
    teacher: count
    for teacher, count in teacher_counts.items()
    if count > 1
}

print(
    "Monday slot 2 records:",
    len(monday_slot2)
)

print(
    "Teachers appearing more than once:"
)

print(
    duplicates
    if duplicates
    else "none"
)


# ============================================================
# FINAL
# ============================================================

print()
print("=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)