"""
Diagnostic for the "1 free faculty records found" issue.
Does NOT modify any files.

IMPORTANT: add your actual Excel/CSV file path(s) to FILES below
so this matches your Streamlit app's exact combined dataset
(Records: 8531). As given, it only includes the 3 PDFs.

Run from your project root:

    python diagnose_faculty_free_count.py
"""

import inspect

from import_engine.import_manager import ImportManager
from data_engine.canonical_event_matcher import CanonicalEventMatcher
from query_engine import QueryEngine, NaturalLanguageQuery

FILES = [
    "Facultywise TT 20 sep.pdf",
    "classwise TT 27 sep.pdf",
    "Location wise TT 27 sep 2025.pdf",
    # "timetable.xlsx",   <-- uncomment/edit to match your real Excel file
]

print("=" * 70)
print("STEP 1: Import + canonicalize")
print("=" * 70)

manager = ImportManager()
all_records = []

for f in FILES:
    result = manager.import_file(f)
    records = result.get("records", []) if isinstance(result, dict) else result
    print(f"{f} -> {len(records)} records")
    all_records.extend(records)

print("TOTAL combined records:", len(all_records))
print(
    "(Compare this total to your Streamlit app's 'Records: 8531' -- "
    "if it differs, Q7/Q9 answer themselves: the app IS building the "
    "dataset differently than this script.)"
)

matcher = CanonicalEventMatcher(all_records)
matcher.match()

print("canonical events:", len(matcher.events))
print(
    "(Compare to Streamlit's 'Scheduled Events: 1785')"
)
print("faculty_free_slots (matcher):", len(matcher.faculty_free_slots))

engine = QueryEngine(matcher)
nlp = NaturalLanguageQuery(engine)

print()
print("=" * 70)
print("Q3: QueryEngine.faculty_free_slots(day='Monday', slot=2) -- direct")
print("=" * 70)

r3 = engine.faculty_free_slots(day="Monday", slot=2)
print("type:", type(r3))
if isinstance(r3, dict):
    print("keys:", list(r3.keys()))
    print("'count' field:", r3.get("count"))
    print("len(results):", len(r3.get("results", [])))

print()
print("=" * 70)
print("Q4/Q5: self._faculty_free() content, filtered to Monday slot 2")
print("=" * 70)

try:
    faculty_free_raw = engine._faculty_free()
    print("total len(_faculty_free()):", len(faculty_free_raw))

    monday_slot2_free = [
        r for r in faculty_free_raw
        if engine._day(r.get("day")) == "monday"
        and engine._slot(r.get("slot")) == 2
    ]
    print("Monday slot 2 FACULTY_FREE_SLOT records:", len(monday_slot2_free))
except Exception as e:
    print("ERROR calling _faculty_free():", repr(e))

print()
print("=" * 70)
print("Q6: SCHEDULED_EVENT records for Monday slot 2 (with a teacher)")
print("=" * 70)

try:
    events = engine._events()
    monday_slot2_events = [
        r for r in events
        if engine._day(r.get("day")) == "monday"
        and engine._slot(r.get("slot")) == 2
        and engine._get(r, "teacher", "faculty")
    ]
    print("count:", len(monday_slot2_events))
    print(
        "(FACULTY_FREE_SLOT + SCHEDULED_EVENT above should sum to ~93, "
        "the total faculty count, if the underlying data matches the "
        "earlier reconstruction.)"
    )
except Exception as e:
    print("ERROR calling _events():", repr(e))

print()
print("=" * 70)
print("Q1/Q2: execute_faculty_free() and call_engine_method(), step by step")
print("=" * 70)

q = "Who is free on Monday slot 2?"
day = nlp.extract_day(q)
slot = nlp.extract_slot(q)
print("extracted day:", repr(day), "| slot:", repr(slot))

cem_result = None
try:
    cem_result = nlp.call_engine_method("faculty_free_slots", day=day, slot=slot)
    print()
    print("call_engine_method('faculty_free_slots', ...) return type:", type(cem_result))
    if isinstance(cem_result, dict):
        print("  keys:", list(cem_result.keys()))
        print("  'count' field:", cem_result.get("count"))
        print("  len(results):", len(cem_result.get("results", [])))
    elif isinstance(cem_result, list):
        print("  len:", len(cem_result))
except Exception as e:
    print("ERROR calling call_engine_method():", repr(e))

print()
try:
    sig_params = inspect.signature(nlp.execute_faculty_free).parameters
    if "time_range" in sig_params:
        eff_result = nlp.execute_faculty_free(day, slot, time_range=None)
    else:
        eff_result = nlp.execute_faculty_free(day, slot)

    print("execute_faculty_free() return type:", type(eff_result))
    print("len:", len(eff_result) if isinstance(eff_result, list) else "N/A")

    if isinstance(eff_result, list) and eff_result:
        first = eff_result[0]
        print("first item type:", type(first))
        if isinstance(first, dict):
            print("first item keys:", list(first.keys()))
            if "results" in first:
                print()
                print("!!! CONFIRMED: execute_faculty_free() wrapped the ENTIRE")
                print("    dict as a single-item list, instead of unwrapping")
                print("    its 'results' field. This is the bug. !!!")
                print("    inner 'count':", first.get("count"))
                print("    inner len('results'):", len(first.get("results", [])))
except Exception as e:
    print("ERROR calling execute_faculty_free():", repr(e))

print()
print("=" * 70)
print("Q8: result_to_list() source (the suspected culprit)")
print("=" * 70)
print(inspect.getsource(nlp.result_to_list))

print()
print("=" * 70)
print("Final answer() output")
print("=" * 70)
print(nlp.answer(q))