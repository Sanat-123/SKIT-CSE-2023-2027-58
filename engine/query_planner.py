class QueryPlanner:

    """
    Connects the NLP chatbot with the existing QueryEngine.
    """

    @staticmethod
    def plan(
        intent,
        entities,
        day_slot,
        query_engine
    ):

        # ==================================================
        # EXTRACT ENTITIES
        # ==================================================

        teachers = entities.get("teachers", [])
        subjects = entities.get("subjects", [])
        rooms = entities.get("rooms", [])
        classes = entities.get("classes", [])

        teacher = (
            teachers[0]["value"]
            if teachers
            else None
        )

        subject = (
            subjects[0]["value"]
            if subjects
            else None
        )

        room = (
            rooms[0]["value"]
            if rooms
            else None
        )

        class_name = (
            classes[0]["value"]
            if classes
            else None
        )

        day = day_slot.get("day")
        slot = day_slot.get("slot")

        # ==================================================
        # FIND TEACHER
        # ==================================================

        if intent == "FIND_TEACHER":

            if not subject:

                return {
                    "count": 0,
                    "results": [],
                    "message": "Please specify a subject."
                }

            result = query_engine.subject_search(
                subject
            )

            results = result.get(
                "results",
                []
            )

            # Filter by day
            if day:

                results = [
                    r for r in results
                    if str(
                        r.get("day", "")
                    ).lower() == day.lower()
                ]

            # Filter by slot
            if slot is not None:

                results = [
                    r for r in results
                    if r.get("slot") == slot
                ]

            return {
                "count": len(results),
                "results": results
            }

        # ==================================================
        # FIND SUBJECT
        # ==================================================

        if intent == "FIND_SUBJECT":

            if not teacher:

                return {
                    "count": 0,
                    "results": [],
                    "message": (
                        "Please specify a faculty member."
                    )
                }

            result = query_engine.teacher_search(
                teacher
            )

            results = result.get(
                "results",
                []
            )

            # Filter by day
            if day:

                results = [
                    r for r in results
                    if str(
                        r.get("day", "")
                    ).lower() == day.lower()
                ]

            # Filter by slot
            if slot is not None:

                results = [
                    r for r in results
                    if r.get("slot") == slot
                ]

            return {
                "count": len(results),
                "results": results
            }

        # ==================================================
        # SHOW TIMETABLE
        # ==================================================

        if intent == "SHOW_TIMETABLE":

            # ------------------------------
            # Teacher timetable
            # ------------------------------

            if teacher:

                return query_engine.teacher_schedule(
                    teacher=teacher,
                    day=day,
                    slot=slot
                )

            # ------------------------------
            # Class timetable
            # ------------------------------

            if class_name:

                return query_engine.class_schedule(
                    class_name=class_name,
                    day=day,
                    slot=slot
                )

            # ------------------------------
            # Room timetable
            # ------------------------------

            if room:

                return query_engine.room_schedule(
                    room=room,
                    day=day,
                    slot=slot
                )

            # ------------------------------
            # Subject timetable
            # ------------------------------

            if subject:

                result = query_engine.subject_search(
                    subject
                )

                results = result.get(
                    "results",
                    []
                )

                if day:

                    results = [
                        r for r in results
                        if str(
                            r.get("day", "")
                        ).lower() == day.lower()
                    ]

                if slot is not None:

                    results = [
                        r for r in results
                        if r.get("slot") == slot
                    ]

                return {
                    "count": len(results),
                    "results": results
                }

            return {
                "count": 0,
                "results": [],
                "message": (
                    "Please specify a faculty, "
                    "class, room, or subject."
                )
            }

        # ==================================================
        # FIND ROOM
        # ==================================================

        if intent == "FIND_ROOM":

            if not subject:

                return {
                    "count": 0,
                    "results": [],
                    "message": (
                        "Please specify a subject."
                    )
                }

            result = query_engine.subject_search(
                subject
            )

            results = result.get(
                "results",
                []
            )

            # Filter by day
            if day:

                results = [
                    r for r in results
                    if str(
                        r.get("day", "")
                    ).lower() == day.lower()
                ]

            # Filter by slot
            if slot is not None:

                results = [
                    r for r in results
                    if r.get("slot") == slot
                ]

            return {
                "count": len(results),
                "results": results
            }

        # ==================================================
        # FIND FREE FACULTY
        # ==================================================

        if intent == "FIND_FREE_FACULTY":

            # A day is always required
            if not day:

                return {
                    "count": 0,
                    "results": [],
                    "message": (
                        "Please specify a day."
                    )
                }

            # --------------------------------------------------
            # CASE 1:
            # Specific slot requested
            #
            # Example:
            # Available faculty Monday Slot 3
            # --------------------------------------------------

            if slot is not None:

                return query_engine.faculty_free_slots(
                    day=day,
                    slot=slot,
                    teacher=teacher
                )

            # --------------------------------------------------
            # CASE 2:
            # No slot requested
            #
            # Example:
            # When is Dr. Abdul Naim Khan free on Saturday?
            #
            # Return all free slots for the teacher on that day.
            # --------------------------------------------------

            result = query_engine.faculty_free_slots(
                day=day,
                slot=None,
                teacher=teacher
            )

            return result

        # ==================================================
        # UNKNOWN INTENT
        # ==================================================

        return {
            "count": 0,
            "results": [],
            "message": (
                "I could not understand the query."
            )
        }