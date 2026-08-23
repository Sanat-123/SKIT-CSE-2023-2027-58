import sqlite3
import os

from utils.validator import is_valid_teacher


DB_FILE = os.path.join(
    "database",
    "faculty.db"
)


# =========================================================
# OLD / DATABASE-BASED FREE FACULTY SEARCH
# =========================================================

def find_free_faculty(day, slot):

    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # -----------------------------------------------------
    # Get all teachers
    # -----------------------------------------------------

    cursor.execute("""
        SELECT DISTINCT teacher
        FROM timetable
    """)

    all_teachers = {
        row[0]
        for row in cursor.fetchall()
        if row[0]
    }

    # -----------------------------------------------------
    # Get teachers who are busy
    # -----------------------------------------------------

    cursor.execute("""
        SELECT DISTINCT teacher
        FROM timetable
        WHERE day = ?
        AND slot = ?
    """, (day, slot))

    busy_teachers = {
        row[0]
        for row in cursor.fetchall()
        if row[0]
    }

    connection.close()

    print("Busy Teachers:", len(busy_teachers))
    print(busy_teachers)

    # -----------------------------------------------------
    # Old method:
    # all teachers - busy teachers
    # -----------------------------------------------------

    free_teachers = sorted(
        all_teachers - busy_teachers
    )

    print(
        "Before Validation:",
        free_teachers[:10]
    )

    # -----------------------------------------------------
    # Validate faculty names
    # -----------------------------------------------------

    free_teachers = [
        teacher
        for teacher in free_teachers
        if is_valid_teacher(teacher)
    ]

    print(
        "After Validation:",
        free_teachers[:10]
    )

    return free_teachers


# =========================================================
# CANONICAL / FACULTYWISE FREE FACULTY SEARCH
# =========================================================
#
# This is the preferred method for the main AI chatbot.
#
# Facultywise timetable is treated as the authoritative
# source for faculty availability.
#
# FREE means:
#   Facultywise timetable explicitly contains a free slot.
#
# We DO NOT infer that a teacher is free merely because
# they are absent from the busy-teacher list.
# =========================================================

def find_free_faculty_canonical(
    day,
    slot,
    matcher
):

    if matcher is None:
        raise ValueError(
            "CanonicalEventMatcher is required."
        )

    # -----------------------------------------------------
    # Normalize day and slot using the canonical matcher
    # -----------------------------------------------------

    day = matcher.normalize_day(day)

    slot = matcher.normalize_slot(slot)

    # -----------------------------------------------------
    # Get explicitly free faculty records
    # -----------------------------------------------------

    free_records = (
        matcher.find_faculty_free_slots(
            day=day,
            slot=slot
        )
    )

    free_teachers = set()

    # -----------------------------------------------------
    # Extract teacher names
    # -----------------------------------------------------

    for record in free_records:

        teacher = record.get(
            "teacher"
        )

        if not teacher:
            continue

        # -------------------------------------------------
        # Validate faculty name
        # -------------------------------------------------

        if is_valid_teacher(teacher):

            free_teachers.add(
                teacher
            )

    # -----------------------------------------------------
    # Return sorted unique faculty names
    # -----------------------------------------------------

    return sorted(
        free_teachers
    )


# =========================================================
# CANONICAL FACULTY STATUS
# =========================================================
#
# Returns:
#
#   BUSY
#   FREE
#   UNKNOWN
#
# This is useful for testing individual faculty members.
# =========================================================

def get_faculty_status(
    teacher,
    day,
    slot,
    matcher
):

    if matcher is None:
        raise ValueError(
            "CanonicalEventMatcher is required."
        )

    return matcher.faculty_status(
        teacher=teacher,
        day=day,
        slot=slot
    )


# =========================================================
# STANDALONE TEST
# =========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("FACULTY FREE SLOT SEARCH")
    print("=" * 60)

    day = input(
        "Enter Day: "
    ).strip()

    slot = int(
        input(
            "Enter Slot: "
        )
    )

    teachers = find_free_faculty(
        day,
        slot
    )

    print("\nFree Faculty\n")

    for i, teacher in enumerate(
        teachers,
        start=1
    ):

        print(
            f"{i}. {teacher}"
        )

    print(
        "\nTotal Free Faculty:",
        len(teachers)
    )