from __future__ import annotations

from copy import deepcopy
from typing import Any

from .assignment_store import AssignmentStore


class FacultyAssignmentEngine:
    """
    Manages replacement assignments for absent faculty.

    Responsibilities:
        - Check faculty availability
        - Detect timetable conflicts
        - Detect replacement conflicts
        - Create confirmed assignments
        - Remove assignments
        - Read persistent assignments
        - Calculate replacement workload

    The original timetable is never modified.

    Confirmed assignments are persisted through AssignmentStore.
    """

    def __init__(
        self,
        query_engine,
        absence_engine=None,
        assignment_store=None,
    ):
        self.query_engine = query_engine
        self.absence_engine = absence_engine

        self.assignment_store = (
            assignment_store
            if assignment_store is not None
            else AssignmentStore()
        )

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
    def _same_teacher(cls, teacher_a, teacher_b):
        return (
            cls._normalize(teacher_a)
            == cls._normalize(teacher_b)
        )

    @classmethod
    def _same_day(cls, day_a, day_b):
        return (
            cls._normalize(day_a)
            == cls._normalize(day_b)
        )

    # ============================================================
    # TIMETABLE ACCESS
    # ============================================================

    def _events(self):
        try:
            return list(self.query_engine._events())
        except Exception:
            return []

    # ============================================================
    # ASSIGNMENT STORAGE
    # ============================================================

    def assignments(self):
        """
        Return all persisted replacement assignments.
        """

        return self.assignment_store.all()

    def clear_assignments(self):
        """
        Remove all persisted replacement assignments.
        """

        self.assignment_store.clear()

    # ============================================================
    # ASSIGNMENT ID
    # ============================================================

    def _next_assignment_id(self):
        assignments = self.assignment_store.all()

        if not assignments:
            return 1

        ids = []

        for assignment in assignments:

            value = assignment.get(
                "assignment_id"
            )

            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                pass

        return max(ids, default=0) + 1

    # ============================================================
    # SLOT CONFLICT CHECKING
    # ============================================================

    def _faculty_busy_in_original_timetable(
        self,
        teacher,
        day,
        slot,
    ):
        """
        Check whether faculty already has an original timetable
        event at the requested day and slot.
        """

        teacher_key = self._normalize(teacher)
        day_key = self._normalize(day)

        target_slot = self._slot_number(slot)

        if not teacher_key or not day_key:
            return False

        for event in self._events():

            event_teacher = self._normalize(
                event.get("teacher")
            )

            event_day = self._normalize(
                event.get("day")
            )

            event_slot = self._slot_number(
                event.get("slot")
            )

            if (
                event_teacher == teacher_key
                and event_day == day_key
                and event_slot == target_slot
            ):
                return True

        return False

    def _faculty_busy_in_assignments(
        self,
        teacher,
        day,
        slot,
    ):
        """
        Check whether faculty already has a replacement
        assignment at the requested day and slot.
        """

        assignments = self.assignment_store.all()

        target_slot = self._slot_number(slot)

        for assignment in assignments:

            if not self._same_teacher(
                assignment.get(
                    "replacement_teacher"
                ),
                teacher,
            ):
                continue

            if not self._same_day(
                assignment.get("day"),
                day,
            ):
                continue

            assigned_slots = assignment.get(
                "slots",
                [],
            )

            if not isinstance(
                assigned_slots,
                list,
            ):
                assigned_slots = [
                    assigned_slots
                ]

            for assigned_slot in assigned_slots:

                if (
                    self._slot_number(
                        assigned_slot
                    )
                    == target_slot
                ):
                    return True

        return False

    def is_teacher_available(
        self,
        teacher,
        day,
        slots,
    ):
        """
        Check whether faculty is available for ALL requested slots.

        A teacher must have:
            1. No original timetable class.
            2. No existing replacement assignment.

        The complete block must therefore be free.
        """

        if not slots:
            return False

        for slot in slots:

            if self._faculty_busy_in_original_timetable(
                teacher,
                day,
                slot,
            ):
                return False

            if self._faculty_busy_in_assignments(
                teacher,
                day,
                slot,
            ):
                return False

        return True

    # ============================================================
    # CONFLICT DETECTION
    # ============================================================

    def check_conflict(
        self,
        replacement_teacher,
        day,
        slots,
    ):
        """
        Return a detailed conflict report.

        This method does not create an assignment.
        """

        conflicts = []

        if not slots:
            return {
                "conflict": True,
                "conflict_count": 0,
                "conflicts": [],
            }

        assignments = self.assignment_store.all()

        for slot in slots:

            # ----------------------------------------------------
            # Original timetable conflict
            # ----------------------------------------------------

            for event in self._events():

                if not self._same_teacher(
                    event.get("teacher"),
                    replacement_teacher,
                ):
                    continue

                if not self._same_day(
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
                    "type": "original_timetable",
                    "teacher": replacement_teacher,
                    "day": day,
                    "slot": slot,
                    "subject": event.get(
                        "subject",
                        "",
                    ),
                    "class_name": event.get(
                        "class_name",
                        "",
                    ),
                    "room": event.get(
                        "room",
                        "",
                    ),
                    "event": deepcopy(event),
                })

            # ----------------------------------------------------
            # Existing replacement conflict
            # ----------------------------------------------------

            for assignment in assignments:

                if not self._same_teacher(
                    assignment.get(
                        "replacement_teacher"
                    ),
                    replacement_teacher,
                ):
                    continue

                if not self._same_day(
                    assignment.get("day"),
                    day,
                ):
                    continue

                assigned_slots = assignment.get(
                    "slots",
                    [],
                )

                if not isinstance(
                    assigned_slots,
                    list,
                ):
                    assigned_slots = [
                        assigned_slots
                    ]

                if self._slot_number(slot) not in [
                    self._slot_number(x)
                    for x in assigned_slots
                ]:
                    continue

                conflicts.append({
                    "type": "replacement_assignment",
                    "teacher": replacement_teacher,
                    "day": day,
                    "slot": slot,
                    "assignment_id": assignment.get(
                        "assignment_id"
                    ),
                    "assignment": deepcopy(
                        assignment
                    ),
                })

        return {
            "conflict": bool(conflicts),
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
        }

    # ============================================================
    # CREATE ASSIGNMENT
    # ============================================================

    def assign(
        self,
        replacement_teacher,
        day,
        slots,
        *,
        absent_teacher="",
        subject="",
        subject_family="",
        class_name="",
        group_name="",
        type="",
        room="",
        slot_time="",
        period_count=None,
        priority=None,
        priority_reason="",
        class_similarity=None,
        subject_similarity=None,
    ):
        """
        Confirm and persist a replacement assignment.
        """

        replacement_teacher = self._text(
            replacement_teacher
        )

        day = self._text(day)

        slots = list(slots or [])

        if not replacement_teacher:
            return {
                "success": False,
                "error": "replacement_teacher_required",
                "message": (
                    "A replacement faculty member is required."
                ),
            }

        if not day:
            return {
                "success": False,
                "error": "day_required",
                "message": "A day is required.",
            }

        if not slots:
            return {
                "success": False,
                "error": "slots_required",
                "message": (
                    "At least one timetable slot is required."
                ),
            }

        # --------------------------------------------------------
        # Check complete block availability.
        # --------------------------------------------------------

        conflict_result = self.check_conflict(
            replacement_teacher,
            day,
            slots,
        )

        if conflict_result["conflict"]:

            return {
                "success": False,
                "error": "faculty_conflict",
                "message": (
                    "The replacement faculty member is not "
                    "available for the complete block."
                ),
                "conflicts": conflict_result[
                    "conflicts"
                ],
            }

        # --------------------------------------------------------
        # Determine period count automatically.
        # --------------------------------------------------------

        if period_count is None:
            period_count = len(slots)

        assignment = {
            "assignment_id": self._next_assignment_id(),

            "absent_teacher": self._text(
                absent_teacher
            ),

            "replacement_teacher": replacement_teacher,

            "day": day,
            "slots": slots,
            "slot_time": slot_time,

            "period_count": period_count,

            "subject": subject,
            "subject_family": subject_family,

            "class_name": class_name,
            "group_name": group_name,

            "type": type,
            "room": room,

            "priority": priority,
            "priority_reason": priority_reason,

            "class_similarity": class_similarity,
            "subject_similarity": subject_similarity,

            "status": "confirmed",
        }

        # --------------------------------------------------------
        # Persist assignment.
        # --------------------------------------------------------

        saved_assignment = self.assignment_store.add(
            assignment
        )

        return {
            "success": True,
            "message": (
                "Replacement assignment created successfully."
            ),
            "assignment": deepcopy(
                saved_assignment
            ),
        }

    # ============================================================
    # ASSIGN FROM RECOMMENDATION
    # ============================================================

    def assign_recommendation(
        self,
        recommendation,
        absent_teacher="",
    ):
        """
        Convert one recommendation returned by
        FacultyAbsenceEngine.best_replacements()
        into a confirmed persistent assignment.
        """

        if not recommendation:
            return {
                "success": False,
                "error": "recommendation_required",
                "message": (
                    "A replacement recommendation is required."
                ),
            }

        replacement_teacher = recommendation.get(
            "replacement_teacher"
        )

        if not replacement_teacher:
            return {
                "success": False,
                "error": "no_replacement_teacher",
                "message": (
                    "The recommendation does not contain "
                    "a replacement faculty member."
                ),
            }

        if absent_teacher == "":
            absent_teacher = recommendation.get(
                "absent_teacher",
                "",
            )

        day = recommendation.get("day", "")

        if not day:
            return {
                "success": False,
                "error": "day_required",
                "message": (
                    "The replacement recommendation does not contain "
                    "the day. Please provide the day explicitly."
                ),
            }

        return self.assign(
            replacement_teacher,
            day,
            recommendation.get("slots", []),
            absent_teacher=absent_teacher,

            subject=recommendation.get(
                "subject",
                "",
            ),

            subject_family=recommendation.get(
                "subject_family",
                "",
            ),

            class_name=recommendation.get(
                "class_name",
                "",
            ),

            group_name=recommendation.get(
                "group_name",
                "",
            ),

            type=recommendation.get(
                "type",
                "",
            ),

            room=recommendation.get(
                "room",
                "",
            ),

            slot_time=recommendation.get(
                "slot_time",
                "",
            ),

            period_count=recommendation.get(
                "period_count",
                None,
            ),

            priority=recommendation.get(
                "priority",
                None,
            ),

            priority_reason=recommendation.get(
                "priority_reason",
                "",
            ),

            class_similarity=recommendation.get(
                "class_similarity",
                None,
            ),

            subject_similarity=recommendation.get(
                "subject_similarity",
                None,
            ),
        )

    # ============================================================
    # REMOVE ASSIGNMENT
    # ============================================================

    def remove_assignment(
        self,
        assignment_id,
    ):
        """
        Remove a persisted assignment by ID.
        """

        removed = self.assignment_store.remove(
            str(assignment_id)
        )

        if not removed:
            return {
                "success": False,
                "error": "assignment_not_found",
                "message": (
                    "No assignment with the supplied ID "
                    "was found."
                ),
            }

        return {
            "success": True,
            "message": (
                "Assignment removed successfully."
            ),
            "assignment_id": assignment_id,
        }

    # ============================================================
    # FIND ASSIGNMENT
    # ============================================================

    def get_assignment(
        self,
        assignment_id,
    ):
        """
        Return one persisted assignment by ID.
        """

        assignment = self.assignment_store.find(
            str(assignment_id)
        )

        if assignment is None:
            return None

        return deepcopy(assignment)

    # ============================================================
    # FACULTY ASSIGNMENTS
    # ============================================================

    def faculty_assignments(
        self,
        teacher,
        day=None,
    ):
        """
        Return replacement assignments belonging to a faculty member.
        """

        assignments = self.assignment_store.for_teacher(
            teacher
        )

        if day is not None:

            assignments = [
                assignment
                for assignment in assignments
                if self._same_day(
                    assignment.get("day"),
                    day,
                )
            ]

        return deepcopy(assignments)

    # ============================================================
    # ABSENT FACULTY ASSIGNMENTS
    # ============================================================

    def absent_teacher_assignments(
        self,
        teacher,
        day=None,
    ):
        """
        Return assignments created to cover an absent faculty member.
        """

        teacher_key = self._normalize(
            teacher
        )

        assignments = []

        for assignment in self.assignment_store.all():

            if (
                self._normalize(
                    assignment.get(
                        "absent_teacher"
                    )
                )
                != teacher_key
            ):
                continue

            if (
                day is not None
                and not self._same_day(
                    assignment.get("day"),
                    day,
                )
            ):
                continue

            assignments.append(
                deepcopy(assignment)
            )

        return assignments

    # ============================================================
    # WORKLOAD INCLUDING REPLACEMENTS
    # ============================================================

    def replacement_workload(
        self,
        teacher,
        day=None,
    ):
        """
        Count confirmed replacement periods for a faculty member.
        """

        total = 0

        for assignment in self.faculty_assignments(
            teacher,
            day,
        ):

            try:

                total += int(
                    assignment.get(
                        "period_count",
                        len(
                            assignment.get(
                                "slots",
                                [],
                            )
                        ),
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                total += len(
                    assignment.get(
                        "slots",
                        [],
                    )
                )

        return total

    def total_workload(
        self,
        teacher,
        day,
    ):
        """
        Return:

            original timetable periods
            + confirmed replacement periods
        """

        original = 0

        teacher_key = self._normalize(
            teacher
        )

        day_key = self._normalize(
            day
        )

        for event in self._events():

            if (
                self._normalize(
                    event.get("teacher")
                )
                != teacher_key
            ):
                continue

            if (
                self._normalize(
                    event.get("day")
                )
                != day_key
            ):
                continue

            original += 1

        replacement = self.replacement_workload(
            teacher,
            day,
        )

        return {
            "teacher": teacher,
            "day": day,
            "original_periods": original,
            "replacement_periods": replacement,
            "total_periods": (
                original + replacement
            ),
        }

    # ============================================================
    # ASSIGNMENT SUMMARY
    # ============================================================

    def summary(self):
        """
        Return a high-level summary of persisted assignments.
        """

        assignments = self.assignment_store.all()

        faculty = set()

        for assignment in assignments:

            teacher = self._text(
                assignment.get(
                    "replacement_teacher"
                )
            )

            if teacher:
                faculty.add(
                    teacher.lower()
                )

        total_periods = 0

        for assignment in assignments:

            try:

                total_periods += int(
                    assignment.get(
                        "period_count",
                        len(
                            assignment.get(
                                "slots",
                                [],
                            )
                        ),
                    )
                )

            except (
                TypeError,
                ValueError,
            ):

                total_periods += len(
                    assignment.get(
                        "slots",
                        [],
                    )
                )

        return {
            "assignment_count": len(
                assignments
            ),
            "replacement_faculty_count": len(
                faculty
            ),
            "replacement_period_count": (
                total_periods
            ),
        }