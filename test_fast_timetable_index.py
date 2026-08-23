


from import_engine.import_manager import ImportManager
from data_engine.canonical_event_matcher import CanonicalEventMatcher
from data_engine.timetable_index import FastTimetableIndex


FILES = [
    "data/Facultywise TT 20 sep.pdf",
    "data/classwise TT 27 sep.pdf",
    "data/Location wise TT 27 sep 2025.pdf",
]


def main():
    print("=" * 80)
    print("UNISCHED AI - FAST INDEX TEST")
    print("=" * 80)

    manager = ImportManager()
    records = []

    for path in FILES:
        result = manager.import_file(path)
        imported = result.get("records", []) if isinstance(result, dict) else result
        print(f"{path}: {len(imported)} imported")
        records.extend(imported)

    print(f"Total raw records: {len(records)}")

    matcher = CanonicalEventMatcher(records)
    matcher.match()

    print(f"Canonical events: {len(matcher.events)}")
    print(
        "Multi-source events:",
        sum(1 for e in matcher.events if e.get("multi_source"))
    )

    index = FastTimetableIndex(matcher.events)

    print("\nINDEX SUMMARY")
    for key, value in index.summary().items():
        print(f"{key:20}: {value}")

    print("\nTEST 1 - MONDAY SLOT 2")
    events = index.events_at("Monday", 2)
    print("Events:", len(events))

    print("\nTEST 2 - FREE FACULTY")
    free = index.free_faculty("Monday", 2)
    print("Free faculty:", len(free))
    for row in free[:10]:
        print(" ", row["teacher"])

    print("\nTEST 3 - TEACHER SCHEDULE")
    schedule = index.teacher_schedule("Dr. Mehul Mahrishi", "Monday")
    print("Events:", len(schedule))
    for row in schedule[:5]:
        print(
            row.get("slot"),
            "|",
            row.get("subject", ""),
            "|",
            row.get("room", ""),
            "|",
            row.get("class_name", ""),
        )

    print("\nTEST 4 - SUBJECT SEARCH")
    subject = index.subject_search("OS III")
    print("Results:", len(subject))
    for row in subject[:5]:
        print(
            row.get("teacher", ""),
            "|",
            row.get("day", ""),
            "| slot",
            row.get("slot"),
            "|",
            row.get("room", ""),
        )

    print("\n" + "=" * 80)
    print("FAST INDEX TEST COMPLETED")
    print("=" * 80)


if __name__ == "__main__":
    main()