def _generate_response(intent, result):

    # =====================================================
    # SAFETY CHECK
    # =====================================================

    if result is None:
        return "No matching information found."

    # =====================================================
    # SHOW TIMETABLE
    # =====================================================
    #
    # IMPORTANT:
    # teacher_schedule() returns only BUSY records in
    # "results", but it also returns has_any_records=True
    # when the teacher has timetable records that are FREE.
    #
    # Therefore SHOW_TIMETABLE must be handled before
    # the generic "no data" logic.
    # =====================================================

    if intent == "SHOW_TIMETABLE":

        timetable = result if isinstance(result, dict) else {}

        teacher = timetable.get(
            "teacher",
            "This faculty"
        )

        day = timetable.get("day")

        results = timetable.get(
            "results",
            []
        )

        has_any_records = timetable.get(
            "has_any_records",
            False
        )

        # -------------------------------------------------
        # CASE 1: Teacher has scheduled/busy classes
        # -------------------------------------------------

        if results:

            lines = [
                f"{teacher}'s schedule"
                + (
                    f" on {day.capitalize()}"
                    if day
                    else ""
                )
                + ":"
            ]

            for record in results:

                slot = record.get(
                    "slot",
                    ""
                )

                slot_time = record.get(
                    "slot_time",
                    ""
                )

                subject = record.get(
                    "subject",
                    ""
                )

                room = record.get(
                    "room",
                    ""
                )

                line = f"• Slot {slot}"

                if slot_time:
                    line += f" — {slot_time}"

                if subject:
                    line += f" — {subject}"

                if room:
                    line += f" — Room {room}"

                lines.append(line)

            return "\n".join(lines)

        # -------------------------------------------------
        # CASE 2:
        # Teacher has records but all are FREE
        # -------------------------------------------------

        if has_any_records:

            if day:

                return (
                    f"{teacher} has no scheduled classes on "
                    f"{day.capitalize()} — all slots are free."
                )

            return (
                f"{teacher} has no scheduled classes — "
                f"all available slots are free."
            )

        # -------------------------------------------------
        # CASE 3:
        # No teacher/day records exist
        # -------------------------------------------------

        return "No timetable information found."

    # =====================================================
    # NORMALIZE RESULT FOR OTHER QUERY TYPES
    # =====================================================

    if isinstance(result, dict):

        message = result.get(
            "message"
        )

        count = result.get(
            "count",
            0
        )

        data = result.get(
            "results",
            []
        )

        if message and not data:
            return message

    else:

        count = (
            len(result)
            if hasattr(result, "__len__")
            else 0
        )

        data = result

    # =====================================================
    # NO RESULTS
    # =====================================================

    if not data:

        if intent == "FIND_FREE_FACULTY":

            return (
                "No faculty members are free "
                "for the requested slot."
            )

        if intent == "FIND_TEACHER":

            return (
                "No teacher found for "
                "the requested subject."
            )

        if intent == "FIND_SUBJECT":

            return (
                "No subjects found for "
                "the requested faculty."
            )

        if intent == "FIND_ROOM":

            return "No room information found."

        return "No matching information found."

        # =====================================================
        # FIND TEACHER
        # =====================================================

        if intent == "FIND_TEACHER":

            teachers = set()

            for row in data:

                if isinstance(row, dict):

                    teacher = row.get(
                        "teacher",
                        ""
                    )

                else:

                    try:
                        teacher = row[0]
                    except Exception:
                        teacher = ""

                if teacher:
                    teachers.add(
                        str(teacher)
                    )

            teachers = sorted(teachers)

            return (
                f"Teacher(s) ({len(teachers)}):\n\n"
                + "\n".join(
                    f"• {teacher}"
                    for teacher in teachers
                )
            )

        # =====================================================
        # FIND FREE FACULTY
        # =====================================================

        if intent == "FIND_FREE_FACULTY":

            # -------------------------------------------------
            # IMPORTANT:
            #
            # If the query asks for a particular faculty,
            # the result contains that faculty's free slots.
            #
            # We therefore display slot information instead
            # of only displaying the teacher name.
            # -------------------------------------------------

            # Check whether the returned records contain
            # slot information.
            has_slot_information = any(
                isinstance(row, dict)
                and row.get("slot") is not None
                for row in data
            )

            # -------------------------------------------------
            # CASE 1:
            # Faculty-specific free-slot query
            # -------------------------------------------------

            if has_slot_information:

                # Group records by teacher
                faculty_slots = {}

                for row in data:

                    if not isinstance(row, dict):
                        continue

                    teacher = str(
                        row.get(
                            "teacher",
                            ""
                        )
                    ).strip()

                    if not teacher:
                        continue

                    slot = row.get(
                        "slot"
                    )

                    slot_time = str(
                        row.get(
                            "slot_time",
                            ""
                        )
                    ).strip()

                    if teacher not in faculty_slots:
                        faculty_slots[teacher] = []

                    faculty_slots[teacher].append(
                        (
                            slot,
                            slot_time
                        )
                    )

                # -------------------------------------------------
                # Build response
                # -------------------------------------------------

                output = []

                for teacher in sorted(
                    faculty_slots.keys()
                ):

                    slots = faculty_slots[
                        teacher
                    ]

                    # Remove duplicate slots
                    unique_slots = {}

                    for slot, slot_time in slots:

                        if slot not in unique_slots:
                            unique_slots[
                                slot
                            ] = slot_time

                    # Sort numerically when possible
                    def slot_sort_key(item):

                        slot = item[0]

                        try:
                            return (
                                0,
                                int(slot)
                            )
                        except (
                            ValueError,
                            TypeError
                        ):
                            return (
                                1,
                                str(slot)
                            )

                    sorted_slots = sorted(
                        unique_slots.items(),
                        key=slot_sort_key
                    )

                    output.append(
                        f"{teacher} is FREE."
                    )

                    output.append(
                        "\nFree slots:"
                    )

                    for slot, slot_time in sorted_slots:

                        if slot_time:

                            output.append(
                                f"• Slot {slot} "
                                f"— {slot_time}"
                            )

                        else:

                            output.append(
                                f"• Slot {slot}"
                            )

                    output.append("")

                return "\n".join(output).strip()

            # -------------------------------------------------
            # CASE 2:
            # Normal "Available faculty Monday Slot 3"
            #
            # This query returns many teachers for ONE slot.
            # Preserve the existing behavior.
            # -------------------------------------------------

            teachers = []

            for row in data:

                if isinstance(row, dict):

                    teacher = row.get(
                        "teacher",
                        ""
                    )

                else:

                    teacher = str(row)

                if teacher:
                    teachers.append(
                        str(teacher)
                    )

            teachers = sorted(
                set(teachers)
            )

            return (
                f"Available Faculty "
                f"({len(teachers)}):\n\n"
                + "\n".join(
                    f"• {teacher}"
                    for teacher in teachers
                )
            )

        # =====================================================
        # FIND SUBJECT
        # =====================================================

        if intent == "FIND_SUBJECT":

            subjects = set()

            for row in data:

                if isinstance(row, dict):

                    subject = row.get(
                        "subject",
                        ""
                    )

                else:

                    try:
                        subject = row[3]
                    except Exception:
                        subject = ""

                if subject:
                    subjects.add(
                        str(subject)
                    )

            subjects = sorted(subjects)

            return (
                f"Subjects ({len(subjects)}):\n\n"
                + "\n".join(
                    f"• {subject}"
                    for subject in subjects
                )
            )

        # =====================================================
        # FIND ROOM
        # =====================================================

        if intent == "FIND_ROOM":

            output = []

            for row in data:

                if isinstance(row, dict):

                    subject = row.get(
                        "subject",
                        ""
                    )

                    teacher = row.get(
                        "teacher",
                        ""
                    )

                    day = row.get(
                        "day",
                        ""
                    )

                    slot = row.get(
                        "slot",
                        ""
                    )

                    room = row.get(
                        "room",
                        ""
                    )

                    class_name = row.get(
                        "class_name",
                        ""
                    )

                    group = row.get(
                        "group_name",
                        ""
                    )

                    lecture_type = row.get(
                        "type",
                        ""
                    )

                else:

                    try:

                        (
                            teacher,
                            day,
                            slot,
                            subject,
                            room,
                            class_name,
                            group,
                            lecture_type
                        ) = row

                    except Exception:
                        continue

                output.append(
                    f"Subject : {subject}\n"
                    f"Teacher : {teacher}\n"
                    f"Day     : {day}\n"
                    f"Slot    : {slot}\n"
                    f"Room    : {room}\n"
                    f"Class   : {class_name}\n"
                    f"Group   : {group}\n"
                    f"Type    : {lecture_type}"
                )

            return (
                f"Room Information "
                f"({len(output)}):\n\n"
                + "\n\n".join(output)
            )

        # =====================================================
        # SHOW TIMETABLE
        # =====================================================

        if intent == "SHOW_TIMETABLE":
            timetable = result if isinstance(result, dict) else {}
            teacher = timetable.get("teacher", "This faculty")
            day = timetable.get("day")

            results = timetable.get("results", data)
            has_any_records = timetable.get("has_any_records", False)

            if results:
                lines = [
                    f"{teacher}'s schedule"
                    + (f" on {day.capitalize()}" if day else "")
                    + ":"
                ]

                for record in results:
                    slot = record.get("slot", "")
                    slot_time = record.get("slot_time", "")
                    subject = record.get("subject", "")
                    room = record.get("room", "")

                    line = f"• Slot {slot}"

                    if slot_time:
                        line += f" — {slot_time}"

                    if subject:
                        line += f" — {subject}"

                    if room:
                        line += f" — Room {room}"

                    lines.append(line)

                return "\n".join(lines)

            # Records exist, but none are busy.
            if has_any_records:
                if day:
                    return (
                        f"{teacher} has no scheduled classes on "
                        f"{day.capitalize()} — all slots are free."
                    )

                return f"{teacher} has no scheduled classes — all available slots are free."

            return "No timetable information found."
        # =====================================================
        # UNKNOWN / FALLBACK
        # =====================================================

        return str(data)


class ResponseGenerator:
    generate = staticmethod(_generate_response)