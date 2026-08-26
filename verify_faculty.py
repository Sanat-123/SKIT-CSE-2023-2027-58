from import_engine.import_manager import ImportManager
from data_engine.canonical_event_matcher import CanonicalEventMatcher

files = [
    "Facultywise TT 20 sep.pdf",
    "classwise TT 27 sep.pdf",
    "Location wise TT 27 sep 2025.pdf",
    "timetable.xlsx",
    "test_timetable.csv"
]

manager = ImportManager()
records = []

for filename in files:
    result = manager.import_file("data/" + filename)

    if isinstance(result, dict):
        records.extend(result.get("records", []))
    else:
        records.extend(result)

matcher = CanonicalEventMatcher(records)
matcher.match()

s2 = {
    x.get("teacher")
    for x in matcher.faculty_free_slots
    if str(x.get("day", "")).lower() == "monday"
    and x.get("slot") == 2
}

s3 = {
    x.get("teacher")
    for x in matcher.faculty_free_slots
    if str(x.get("day", "")).lower() == "monday"
    and x.get("slot") == 3
}

print()
print("=" * 100)
print("MONDAY FACULTY AVAILABILITY")
print("=" * 100)
print()
print(f"{'FACULTY':45} {'SLOT 2':12} {'SLOT 3':12} {'09:15-11:15':15}")
print("-" * 100)

for teacher in sorted(s2 | s3):
    slot2 = "FREE" if teacher in s2 else "BUSY"
    slot3 = "FREE" if teacher in s3 else "BUSY"
    complete = "FREE" if teacher in s2 and teacher in s3 else "BUSY"

    print(f"{teacher:45} {slot2:12} {slot3:12} {complete:15}")

print("-" * 100)
print()
print(f"Total unique faculty : {len(s2 | s3)}")
print(f"Free in Slot 2       : {len(s2)}")
print(f"Free in Slot 3       : {len(s3)}")
print(f"Free in BOTH         : {len(s2 & s3)}")
print(f"Free only Slot 2     : {len(s2 - s3)}")
print(f"Free only Slot 3     : {len(s3 - s2)}")
print()
