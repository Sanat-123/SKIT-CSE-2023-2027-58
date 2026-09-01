def _class_reference_label(result):
    """
    Builds a human-readable label for a class-scoped response
    (class-teacher search or class timetable), distinguishing an
    EXACT canonical class match from a BROAD query that matches
    several canonical classes at once.

    Driven entirely by the "class_name"/"class_query_mode"/
    "matching_classes" keys QueryPlanner attaches to the result
    (see QueryEngine.resolve_class_reference()) - never a
    hard-coded class name. Used by both the FIND_CLASS_TEACHER
    and SHOW_TIMETABLE branches below so "7CS" is described the
    same way regardless of which query type asked about it.

    Returns None if there is no class information to label.
    """

    if not isinstance(result, dict):
        return None

    class_name = result.get("class_name")

    if not class_name:
        return None

    mode = result.get("class_query_mode")
    matching_classes = result.get("matching_classes") or []

    if mode == "broad" and len(matching_classes) > 1:
        return (
            f"classes matching {class_name} "
            f"({', '.join(matching_classes)})"
        )

    return class_name


def _group_teachers_with_subjects(results):
    """
    Groups a list of timetable event records by teacher,
    collecting the distinct subject(s) each teacher appears
    against. Built entirely from whatever records are passed
    in - no teacher, class, or subject name is hard-coded.

    Shared by the FIND_CLASS_TEACHER response formatting below
    and by the semester-wide faculty-load lookup in
    faculty_chatbot.py, so this grouping logic lives in exactly
    one place.
    """

    teacher_subjects = {}

    for row in results or []:

        if not isinstance(row, dict):
            continue

        teacher = str(
            row.get("teacher", "")
        ).strip()

        if not teacher:
            continue

        subject = str(
            row.get("subject", "")
        ).strip()

        if teacher not in teacher_subjects:
            teacher_subjects[teacher] = set()

        if subject:
            teacher_subjects[teacher].add(subject)

    return teacher_subjects


def format_teacher_list(header, results):
    """
    Builds a bulleted "Teacher — subject(s)" list from
    timetable event records, prefixed with the given header
    and a count. `header` should NOT include the count or the
    trailing colon - both are added here.
    """

    teacher_subjects = _group_teachers_with_subjects(results)

    teacher_names = sorted(teacher_subjects.keys())

    lines = [
        f"{header} ({len(teacher_names)}):",
        ""
    ]

    for teacher in teacher_names:

        subjects_for_teacher = sorted(
            teacher_subjects[teacher]
        )

        if subjects_for_teacher:

            lines.append(
                f"• {teacher} — "
                f"{', '.join(subjects_for_teacher)}"
            )

        else:

            lines.append(f"• {teacher}")

    return "\n".join(lines)


def format_teacher_workload_list(header, results):
    """
    Builds a bulleted "Teacher — N periods" list from
    workload-engine-style records - each a dict with at
    least "teacher" and "periods", and optionally a "classes"
    breakdown (see FacultyWorkloadEngine.semester_workload):
    a list of {"class_name", "subject", "slots", "period_count"}
    dicts, one per distinct class_name/subject pair the teacher
    was found teaching.

    Every class_name, subject, and slot number shown here comes
    directly from the canonical event records passed in - nothing
    is invented. If a record's class_name or subject is empty,
    it is shown as-is (empty) rather than fabricated, and if no
    "classes" breakdown is present at all, this falls back to the
    older "subjects"-only summary so callers that don't supply a
    breakdown still get a sensible response.

    `header` should NOT include the count or the trailing
    colon - both are added here.
    """

    rows = [
        item for item in (results or [])
        if isinstance(item, dict) and item.get("teacher")
    ]

    lines = [
        f"{header} ({len(rows)}):",
        ""
    ]

    for item in rows:

        teacher = str(item["teacher"]).strip()
        periods = item.get("periods", 0)

        try:
            periods = int(periods)
        except (TypeError, ValueError):
            periods = 0

        period_word = "period" if periods == 1 else "periods"

        lines.append(f"• {teacher} — {periods} {period_word}")

        classes = item.get("classes")

        if classes:

            for class_row in classes:

                if not isinstance(class_row, dict):
                    continue

                class_name = str(
                    class_row.get("class_name", "")
                ).strip()

                subject = str(
                    class_row.get("subject", "")
                ).strip()

                event_day = class_row.get("day")

                slots = class_row.get("slots") or []

                slot_text = ", ".join(
                    str(slot) for slot in slots
                )

                detail_parts = [
                    part for part in (class_name, subject)
                    if part
                ]

                detail = " — ".join(detail_parts)

                if event_day:
                    day_label = str(event_day).capitalize()
                    if detail:
                        detail += f" ({day_label})"
                    else:
                        detail = day_label

                if slot_text:

                    if detail:
                        detail += f" — Slots {slot_text}"
                    else:
                        detail = f"Slots {slot_text}"

                if detail:
                    lines.append(f"  - {detail}")

        else:

            subjects = item.get("subjects") or []

            if subjects:
                lines[-1] += f" ({', '.join(subjects)})"

        lines.append("")

    # Drop the trailing blank line left after the last entry.
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


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

        # ---------------------------------------------------
        # WHO/WHAT THIS TIMETABLE IS FOR
        #
        # SHOW_TIMETABLE can be answering a teacher, class,
        # room, or subject lookup (see QueryPlanner). Each of
        # query_engine's underlying methods (teacher_schedule,
        # class_schedule, room_schedule) echoes back the value
        # it was looked up with under its own key ("teacher",
        # "class_name", "room"). We use whichever of those is
        # actually present to label the response correctly,
        # instead of always assuming it's a faculty member.
        # Nothing here is a hard-coded name - it's read back
        # from the same dict the query engine already returned.
        # ---------------------------------------------------

        teacher = timetable.get("teacher")
        class_name = timetable.get("class_name")
        room = timetable.get("room")

        if teacher:
            subject_label = f"{teacher}'s schedule"
        elif class_name:
            class_label = (
                _class_reference_label(timetable) or class_name
            )
            subject_label = f"Timetable for {class_label}"
        elif room:
            subject_label = f"Timetable for Room {room}"
        else:
            subject_label = "Timetable"

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
        # CASE 1: Scheduled/busy classes exist
        # -------------------------------------------------

        if results:

            lines = [
                subject_label
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

        if intent == "FIND_CLASS_TEACHER":

            return (
                "No faculty found teaching "
                "the requested class."
            )

        return "No matching information found."

    # =====================================================
    # RESULTS FOUND - FORMAT PER INTENT
    #
    # NOTE: This section previously lived nested inside the
    # "if not data:" block above, which made it unreachable
    # any time results actually existed (the "if not data:"
    # block always returns before reaching it). It has been
    # moved back out to the correct indentation level so it
    # runs for every successful (non-empty) result, restoring
    # the intended behavior for FIND_TEACHER, FIND_FREE_FACULTY,
    # FIND_SUBJECT, and FIND_ROOM, and adding formatting for
    # the new FIND_CLASS_TEACHER intent.
    # =====================================================

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
    # FIND CLASS TEACHER
    #
    # Example:
    # Who teaches 7CS?
    # Show faculty teaching 7CS
    # Who teaches 7CS on Monday?
    #
    # Groups the faculty teaching this class together with
    # the subject(s) they teach for it, built entirely from
    # the records returned by the query engine. No faculty
    # name, class name, or subject is hard-coded.
    # =====================================================

    if intent == "FIND_CLASS_TEACHER":

        class_name = None
        day = None

        if isinstance(result, dict):
            class_name = result.get("class_name")
            day = result.get("day")

        class_label = _class_reference_label(result) or class_name

        header = (
            f"Faculty teaching {class_label}"
            if class_label
            else "Faculty teaching this class"
        )

        if day:
            header += f" on {str(day).capitalize()}"

        return format_teacher_list(header, data)

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
    #
    # NOTE: SHOW_TIMETABLE always returns earlier in this
    # function (see top of file), so this branch is kept
    # only as a defensive fallback and is not expected to
    # be reached in normal operation.
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
    format_teacher_list = staticmethod(format_teacher_list)
    format_teacher_workload_list = staticmethod(
        format_teacher_workload_list
    )