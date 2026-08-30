from collections import defaultdict
from copy import deepcopy


class FacultyConflictEngine:
    """
    Generic timetable conflict detection engine.

    Detects conflicts involving:

        - faculty
        - class
        - room
        - replacement assignments

    The engine does not modify the original timetable.

    No faculty names, subject names, class names, room names,
    branches, semesters, or sections are hard-coded.
    """

    def __init__(
        self,
        query_engine,
        assignment_engine=None,
    ):
        self.query_engine = query_engine
        self.assignment_engine = assignment_engine

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _text(value):
        return str(value or "").strip()

    @staticmethod
    def _normalize(value):
        return str(value or "").strip().lower()

    @staticmethod
    def _slot_number(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _same(cls, a, b):
        return cls._normalize(a) == cls._normalize(b)

    # ============================================================
    # EVENT ACCESS
    # ============================================================

    def _events(self):
        try:
            return list(self.query_engine._events())
        except Exception:
            return []

    # ============================================================
    # EVENT KEY
    # ============================================================

    @classmethod
    def _event_key(cls, event):
        """
        Return the basic scheduling coordinates of an event.
        """

        return {
            "day": cls._normalize(
                event.get("day")
            ),
            "slot": cls._slot_number(
                event.get("slot")
            ),
            "teacher": cls._normalize(
                event.get("teacher")
            ),
            "class_name": cls._normalize(
                event.get("class_name")
            ),
            "room": cls._normalize(
                event.get("room")
            ),
        }

    # ============================================================
    # FACULTY CONFLICTS
    # ============================================================

    def faculty_conflicts(self):
        """
        Find cases where the same faculty member is scheduled
        for multiple events at the same day and slot.
        """

        grouped = defaultdict(list)

        for event in self._events():

            key = (
                self._normalize(
                    event.get("teacher")
                ),
                self._normalize(
                    event.get("day")
                ),
                self._slot_number(
                    event.get("slot")
                ),
            )

            if not key[0] or not key[1]:
                continue

            grouped[key].append(event)

        conflicts = []

        for key, events in grouped.items():

            if len(events) <= 1:
                continue

            teacher, day, slot = key

            conflicts.append({
                "conflict_type": "faculty",
                "teacher": teacher,
                "day": day,
                "slot": slot,
                "event_count": len(events),
                "events": deepcopy(events),
                "message": (
                    "Faculty member is scheduled for "
                    "multiple events at the same time."
                ),
            })

        return conflicts

    # ============================================================
    # CLASS CONFLICTS
    # ============================================================

    def class_conflicts(self):
        """
        Find cases where the same class is scheduled for multiple
        events at the same day and slot.

        Group information is retained so legitimate simultaneous
        subgroup teaching can be distinguished later.
        """

        grouped = defaultdict(list)

        for event in self._events():

            class_name = self._normalize(
                event.get("class_name")
            )

            day = self._normalize(
                event.get("day")
            )

            slot = self._slot_number(
                event.get("slot")
            )

            if not class_name or not day:
                continue

            key = (
                class_name,
                day,
                slot,
            )

            grouped[key].append(event)

        conflicts = []

        for key, events in grouped.items():

            if len(events) <= 1:
                continue

            class_name, day, slot = key

            # ----------------------------------------------------
            # Same group events are always suspicious.
            #
            # Different groups may legitimately occur together,
            # therefore the conflict is still reported but marked
            # as potentially valid subgroup scheduling.
            # ----------------------------------------------------

            groups = [
                self._normalize(
                    event.get("group_name")
                )
                for event in events
            ]

            unique_groups = set(
                group
                for group in groups
                if group
            )

            potentially_parallel = (
                len(unique_groups) == len(events)
                and len(unique_groups) > 1
            )

            conflicts.append({
                "conflict_type": "class",
                "class_name": class_name,
                "day": day,
                "slot": slot,
                "event_count": len(events),
                "events": deepcopy(events),
                "potential_subgroups": (
                    potentially_parallel
                ),
                "message": (
                    "Class has multiple events in the "
                    "same timetable slot."
                ),
            })

        return conflicts

    # ============================================================
    # ROOM CONFLICTS
    # ============================================================

    def room_conflicts(self):
        """
        Find cases where the same room is allocated to multiple
        events at the same day and slot.
        """

        grouped = defaultdict(list)

        for event in self._events():

            room = self._normalize(
                event.get("room")
            )

            day = self._normalize(
                event.get("day")
            )

            slot = self._slot_number(
                event.get("slot")
            )

            if not room or not day:
                continue

            key = (
                room,
                day,
                slot,
            )

            grouped[key].append(event)

        conflicts = []

        for key, events in grouped.items():

            if len(events) <= 1:
                continue

            room, day, slot = key

            conflicts.append({
                "conflict_type": "room",
                "room": room,
                "day": day,
                "slot": slot,
                "event_count": len(events),
                "events": deepcopy(events),
                "message": (
                    "Room is allocated to multiple "
                    "events at the same time."
                ),
            })

        return conflicts

    # ============================================================
    # REPLACEMENT ASSIGNMENT CONFLICTS
    # ============================================================

    def assignment_conflicts(self):
        """
        Check confirmed replacement assignments against:

            - original timetable
            - other replacement assignments
            - faculty availability

        This method is intentionally defensive so it can also
        operate when no assignment engine has been connected.
        """

        if self.assignment_engine is None:
            return []

        conflicts = []

        try:
            assignments = (
                self.assignment_engine.assignments()
            )
        except Exception:
            assignments = []

        for assignment in assignments:

            teacher = assignment.get(
                "replacement_teacher",
                "",
            )

            day = assignment.get(
                "day",
                "",
            )

            slots = assignment.get(
                "slots",
                [],
            )

            assignment_id = assignment.get(
                "assignment_id"
            )

            # ----------------------------------------------------
            # Compare each assigned slot against original timetable.
            # ----------------------------------------------------

            for slot in slots:

                for event in self._events():

                    if not self._same(
                        event.get("teacher"),
                        teacher,
                    ):
                        continue

                    if not self._same(
                        event.get("day"),
                        day,
                    ):
                        continue

                    if (
                        self._slot_number(
                            event.get("slot")
                        )
                        != self._slot_number(slot)
                    ):
                        continue

                    conflicts.append({
                        "conflict_type": (
                            "replacement_vs_timetable"
                        ),
                        "assignment_id": assignment_id,
                        "teacher": teacher,
                        "day": day,
                        "slot": slot,
                        "assignment": deepcopy(
                            assignment
                        ),
                        "event": deepcopy(event),
                        "message": (
                            "Replacement assignment conflicts "
                            "with the faculty member's original "
                            "timetable."
                        ),
                    })

            # ----------------------------------------------------
            # Compare assignment against other assignments.
            # ----------------------------------------------------

            for other in assignments:

                other_id = other.get(
                    "assignment_id"
                )

                if assignment_id == other_id:
                    continue

                if not self._same(
                    other.get(
                        "replacement_teacher"
                    ),
                    teacher,
                ):
                    continue

                if not self._same(
                    other.get("day"),
                    day,
                ):
                    continue

                current_slots = {
                    self._slot_number(slot)
                    for slot in slots
                }

                other_slots = {
                    self._slot_number(slot)
                    for slot in other.get(
                        "slots",
                        [],
                    )
                }

                overlap = (
                    current_slots
                    & other_slots
                )

                for slot in sorted(
                    x for x in overlap
                    if x is not None
                ):

                    conflicts.append({
                        "conflict_type": (
                            "replacement_vs_replacement"
                        ),
                        "assignment_id": assignment_id,
                        "other_assignment_id": other_id,
                        "teacher": teacher,
                        "day": day,
                        "slot": slot,
                        "assignment": deepcopy(
                            assignment
                        ),
                        "other_assignment": deepcopy(
                            other
                        ),
                        "message": (
                            "Faculty member has multiple "
                            "replacement assignments at "
                            "the same time."
                        ),
                    })

        return conflicts

    # ============================================================
    # ALL CONFLICTS
    # ============================================================

    def all_conflicts(self):
        """
        Return all detected timetable conflicts.
        """

        faculty = self.faculty_conflicts()
        classes = self.class_conflicts()
        rooms = self.room_conflicts()
        assignments = self.assignment_conflicts()

        return {
            "faculty": faculty,
            "class": classes,
            "room": rooms,
            "replacement": assignments,
            "total": (
                len(faculty)
                + len(classes)
                + len(rooms)
                + len(assignments)
            ),
        }

    # ============================================================
    # CONFLICT SUMMARY
    # ============================================================

    def summary(self):
        """
        Return only conflict counts.
        """

        result = self.all_conflicts()

        return {
            "faculty_conflicts": len(
                result["faculty"]
            ),
            "class_conflicts": len(
                result["class"]
            ),
            "room_conflicts": len(
                result["room"]
            ),
            "replacement_conflicts": len(
                result["replacement"]
            ),
            "total_conflicts": result["total"],
        }

    # ============================================================
    # CONFLICTS FOR ONE FACULTY MEMBER
    # ============================================================

    def faculty_conflicts_for(
        self,
        teacher,
        day=None,
    ):
        """
        Return conflicts involving a particular faculty member.
        """

        teacher_key = self._normalize(
            teacher
        )

        day_key = (
            self._normalize(day)
            if day is not None
            else None
        )

        results = []

        for conflict in self.faculty_conflicts():

            if (
                self._normalize(
                    conflict.get("teacher")
                )
                != teacher_key
            ):
                continue

            if (
                day_key is not None
                and self._normalize(
                    conflict.get("day")
                )
                != day_key
            ):
                continue

            results.append(
                deepcopy(conflict)
            )

        return results

    # ============================================================
    # CONFLICTS FOR ONE CLASS
    # ============================================================

    def class_conflicts_for(
        self,
        class_name,
        day=None,
    ):
        """
        Return conflicts involving a particular class.
        """

        class_key = self._normalize(
            class_name
        )

        day_key = (
            self._normalize(day)
            if day is not None
            else None
        )

        results = []

        for conflict in self.class_conflicts():

            if (
                self._normalize(
                    conflict.get("class_name")
                )
                != class_key
            ):
                continue

            if (
                day_key is not None
                and self._normalize(
                    conflict.get("day")
                )
                != day_key
            ):
                continue

            results.append(
                deepcopy(conflict)
            )

        return results

    # ============================================================
    # CONFLICTS FOR ONE ROOM
    # ============================================================

    def room_conflicts_for(
        self,
        room,
        day=None,
    ):
        """
        Return conflicts involving a particular room.
        """

        room_key = self._normalize(
            room
        )

        day_key = (
            self._normalize(day)
            if day is not None
            else None
        )

        results = []

        for conflict in self.room_conflicts():

            if (
                self._normalize(
                    conflict.get("room")
                )
                != room_key
            ):
                continue

            if (
                day_key is not None
                and self._normalize(
                    conflict.get("day")
                )
                != day_key
            ):
                continue

            results.append(
                deepcopy(conflict)
            )

        return results

    # ============================================================
    # VALIDATE A PROPOSED EVENT
    # ============================================================

    def validate_event(
        self,
        teacher,
        day,
        slot,
        class_name="",
        room="",
    ):
        """
        Validate a proposed timetable event without inserting it.

        Returns a detailed conflict report.
        """

        teacher_key = self._normalize(
            teacher
        )

        day_key = self._normalize(
            day
        )

        slot_key = self._slot_number(
            slot
        )

        class_key = self._normalize(
            class_name
        )

        room_key = self._normalize(
            room
        )

        conflicts = []

        for event in self._events():

            event_day = self._normalize(
                event.get("day")
            )

            event_slot = self._slot_number(
                event.get("slot")
            )

            if (
                event_day != day_key
                or event_slot != slot_key
            ):
                continue

            # ----------------------------------------------------
            # Faculty
            # ----------------------------------------------------

            if teacher_key and (
                self._normalize(
                    event.get("teacher")
                )
                == teacher_key
            ):
                conflicts.append({
                    "type": "faculty",
                    "event": deepcopy(event),
                })

            # ----------------------------------------------------
            # Class
            # ----------------------------------------------------

            if class_key and (
                self._normalize(
                    event.get("class_name")
                )
                == class_key
            ):
                conflicts.append({
                    "type": "class",
                    "event": deepcopy(event),
                })

            # ----------------------------------------------------
            # Room
            # ----------------------------------------------------

            if room_key and (
                self._normalize(
                    event.get("room")
                )
                == room_key
            ):
                conflicts.append({
                    "type": "room",
                    "event": deepcopy(event),
                })

        return {
            "valid": not bool(conflicts),
            "conflict": bool(conflicts),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "teacher": teacher,
            "day": day,
            "slot": slot,
            "class_name": class_name,
            "room": room,
        }