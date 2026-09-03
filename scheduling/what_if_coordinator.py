"""
WHAT-IF SIMULATION

A thin, side-effect-free simulation layer over the EXISTING,
already-tested domain planners/checkers:

    MultiAbsenceCoordinator (scheduling/multi_absence_planner.py)
        - faculty absence what-if

    LabShiftCoordinator (scheduling/lab_shift_planner.py)
        - lab/room shift what-if

    FacultyAssignmentEngine.check_conflict()
        (scheduling/assignment_engine.py)
        - single-replacement conflict what-if

This module does not implement its own block detection, room
occupancy, replacement ranking, or conflict-checking logic. Every
one of those already exists, is already tested, and is reused
here unchanged. WhatIfCoordinator's only job is to call the right
existing planner/checker for the requested scenario and normalize
its result into one consistent, explanatory shape.

============================================================
SIDE-EFFECT FREEDOM
============================================================

None of the three simulate_*() methods below ever write to
AssignmentStore, RoomShiftStore, or any canonical timetable data:

    - simulate_absence() calls MultiAbsenceCoordinator.plan()
      only - never .confirm().
    - simulate_lab_shift() calls LabShiftCoordinator.plan_shift()
      only - never .confirm_shift().
    - simulate_replacement() calls
      FacultyAssignmentEngine.check_conflict() only, which is
      already explicitly documented as not creating an
      assignment, and never calls .assign()/
      .assign_recommendation().

Every simulate_*() result includes "applied": False and
"side_effect_free": True, making this explicit in the returned
data itself, not just in this docstring.

Confirming a simulated change remains the sole responsibility of
the existing, already-tested confirm methods
(MultiAbsenceCoordinator.confirm(), LabShiftCoordinator.
confirm_shift(), FacultyAssignmentEngine.assign_recommendation())
- this coordinator never calls them.

============================================================
SCOPE
============================================================

Three scenario types only, matching the three existing domain
planners: "absence", "lab_shift", "replacement". Cross-domain,
multi-change staged simulation (e.g. simulating an absence AND a
room shift together and checking whether they'd conflict with
each other) is explicitly out of scope for this pass.

Nothing here hard-codes any faculty name, class name, subject,
room, day, slot, or semester. Every value comes from whatever the
delegated-to planner/checker reports for the timetable data
currently loaded.
"""


class WhatIfCoordinator:

    def __init__(
        self,
        query_engine,
        absence_engine,
        assignment_engine,
        lab_shift_coordinator,
        multi_absence_coordinator,
    ):
        self.query_engine = query_engine
        self.absence_engine = absence_engine
        self.assignment_engine = assignment_engine
        self.lab_shift_coordinator = lab_shift_coordinator
        self.multi_absence_coordinator = multi_absence_coordinator

    # ============================================================
    # RESULT ENVELOPE
    #
    # Every simulate_*() method returns this same shape, so a
    # caller (chatbot response formatting, or anything else) does
    # not need to know which domain planner actually produced the
    # answer.
    # ============================================================

    @staticmethod
    def _envelope(
        scenario_type,
        success,
        current_state,
        proposed_change,
        affected_entities,
        conflicts,
        outcome,
        recommendation=None,
        reason=None,
    ):

        return {
            "scenario_type": scenario_type,
            "success": success,
            "applied": False,
            "side_effect_free": True,
            "current_state": current_state,
            "proposed_change": proposed_change,
            "affected_entities": affected_entities,
            "conflicts": conflicts,
            "outcome": outcome,
            "recommendation": recommendation,
            "reason": reason,
        }

    # ============================================================
    # A. FACULTY ABSENCE WHAT-IF
    #
    # "What if <teacher> is absent on <day>?"
    #
    # Delegates entirely to
    # MultiAbsenceCoordinator.plan([{"teacher": teacher,
    # "day": day}]) - the SAME side-effect-free planning already
    # used for real multi-absence coordination. A single-teacher
    # call is simply a batch of one; no absence/block-detection
    # logic is duplicated here. Replacement analysis (which
    # candidate would cover each affected block, and why) comes
    # directly from plan()'s "covered" entries, which already
    # carry the existing tiered ranking from
    # FacultyAbsenceEngine.replacement_candidates().
    # ============================================================

    def simulate_absence(self, teacher, day):

        plan = self.multi_absence_coordinator.plan([
            {"teacher": teacher, "day": day}
        ])

        affected_entities = (
            list(plan.get("covered", []))
            + list(plan.get("uncovered", []))
        )

        # "Conflicts" here means blocks the hypothetical absence
        # would leave uncoverable, each already carrying its own
        # existing structured reason
        # (no_qualified_candidate / all_qualified_candidates_
        # claimed) from MultiAbsenceCoordinator - not
        # re-derived here.
        conflicts = list(plan.get("uncovered", []))

        covered_count = plan.get("covered_count", 0)
        uncovered_count = plan.get("uncovered_count", 0)

        if not affected_entities:
            outcome = "no_scheduled_classes"
        elif uncovered_count == 0:
            outcome = "fully_coverable"
        elif covered_count == 0:
            outcome = "not_coverable"
        else:
            outcome = "partially_coverable"

        recommendation = None

        if plan.get("covered"):

            lines = [
                f"{item['replacement_teacher']} for "
                f"{item['class_name']} "
                f"({item['subject']}) slots {item['slots']}"
                for item in plan["covered"]
            ]

            recommendation = (
                "Suggested replacements: " + "; ".join(lines)
            )

        return self._envelope(
            scenario_type="absence",
            success=True,
            current_state={
                "teacher": teacher,
                "day": day,
            },
            proposed_change={
                "teacher": teacher,
                "day": day,
                "action": "mark_absent",
            },
            affected_entities=affected_entities,
            conflicts=conflicts,
            outcome=outcome,
            recommendation=recommendation,
        )

    # ============================================================
    # B. LAB / ROOM SHIFT WHAT-IF
    #
    # "What if I move this lab to <room>?"
    # "Would moving this lab to <room> cause a conflict?"
    #
    # Delegates entirely to LabShiftCoordinator.plan_shift() -
    # the SAME side-effect-free planning (block resolution, Lab-
    # only validation, room occupancy checking) already used for
    # real lab shifting. Nothing is re-implemented here.
    # ============================================================

    def simulate_lab_shift(
        self,
        teacher=None,
        class_name=None,
        day=None,
        slot=None,
        target_room=None,
    ):

        plan = self.lab_shift_coordinator.plan_shift(
            teacher=teacher,
            class_name=class_name,
            day=day,
            slot=slot,
            target_room=target_room,
        )

        current_state = {
            "teacher": plan.get("teacher", teacher),
            "class_name": plan.get("class_name", class_name),
            "subject": plan.get("subject"),
            "day": plan.get("day", day),
            "slots": plan.get("slots"),
            "room": plan.get("source_room"),
        }

        proposed_change = {
            "target_room": plan.get(
                "target_room",
                target_room,
            ),
        }

        conflicts = plan.get("conflicts", [])

        affected_entities = plan.get("affected_events", [])

        if plan.get("success"):
            outcome = "feasible"
            recommendation = (
                f"Room {plan['target_room']} is free for the "
                "complete block and could be used for this "
                "shift."
            )
        elif plan.get("reason") == "target_room_occupied":
            outcome = "conflict"
            recommendation = None
        else:
            outcome = "infeasible"
            recommendation = None

        return self._envelope(
            scenario_type="lab_shift",
            success=plan.get("success", False),
            current_state=current_state,
            proposed_change=proposed_change,
            affected_entities=affected_entities,
            conflicts=conflicts,
            outcome=outcome,
            recommendation=recommendation,
            reason=plan.get("reason"),
        )

    # ============================================================
    # C. REPLACEMENT ASSIGNMENT WHAT-IF
    #
    # "What if this replacement is assigned?"
    #
    # Delegates entirely to
    # FacultyAssignmentEngine.check_conflict() - already
    # explicitly documented as not creating an assignment. No
    # conflict-detection logic is duplicated here.
    # ============================================================

    def simulate_replacement(
        self,
        replacement_teacher,
        day,
        slots,
        absent_teacher=None,
    ):

        if not isinstance(slots, list):
            slots = [slots]

        result = self.assignment_engine.check_conflict(
            replacement_teacher,
            day,
            slots,
        )

        conflicts = result.get("conflicts", [])

        outcome = "conflict" if result.get("conflict") else (
            "feasible"
        )

        recommendation = (
            None
            if result.get("conflict")
            else (
                f"{replacement_teacher} is free for the "
                "requested slot(s) and could be assigned."
            )
        )

        return self._envelope(
            scenario_type="replacement",
            success=not result.get("conflict"),
            current_state={
                "absent_teacher": absent_teacher,
                "day": day,
                "slots": slots,
            },
            proposed_change={
                "replacement_teacher": replacement_teacher,
                "day": day,
                "slots": slots,
            },
            affected_entities=[
                entry.get("event") or entry.get("assignment")
                for entry in conflicts
                if entry.get("event") or entry.get("assignment")
            ],
            conflicts=conflicts,
            outcome=outcome,
            recommendation=recommendation,
        )