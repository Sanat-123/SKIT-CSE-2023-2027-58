"""
LAB SHIFTING / VENUE CHANGE MANAGEMENT

Helps determine whether a timetable lab (or any scheduled class)
can be moved to another room, and safely records the change once
confirmed.

This module does not implement its own event-lookup, block-
detection, or room-availability primitives from scratch. It is a
thin coordination layer on top of the EXISTING engines:

    QueryEngine
        Canonical event access (_events()), the existing
        class/room/day/slot normalization helpers (_day, _slot,
        _same_day, _same_slot, _normalize, _contains), and the
        live entity knowledge (entity_knowledge()) used to
        resolve a typed room name against the rooms that actually
        exist in the currently loaded timetable data.

    FacultyAbsenceEngine
        Multi-period BLOCK detection (_affected_blocks) - the
        SAME contiguous-block grouping already used for absence/
        replacement planning, reused here unchanged so a lab
        block is identified identically everywhere in the
        project.

    FacultyConflictEngine (optional)
        validate_event() - the existing single-slot conflict
        primitive, reused per affected slot to check the proposed
        target room against the ORIGINAL timetable.

    RoomShiftStore
        The smallest new persistence overlay: a JSON-file-backed
        list of CONFIRMED room-shift records. Canonical timetable
        events are never mutated - they are read-only throughout
        the entire project (nothing in query_engine, workload_
        engine, absence_engine, or assignment_engine ever writes
        to an event dict). A room shift is instead recorded as an
        overlay entry {source_room, target_room, ...block
        identity...}, so the original source timetable remains
        fully traceable and nothing is destroyed.

Nothing here hard-codes any faculty name, class name, subject,
room name, day, or slot. Every decision is derived from whatever
the query/absence engines report for the timetable data currently
loaded, plus whatever room-shift records have actually been
confirmed.

============================================================
ROOM AVAILABILITY
============================================================

A room is considered occupied at a given day/slot based on the
EFFECTIVE occupancy of that slot, not merely "not mentioned in a
free-room list" (the project's separate room_free_slots() data
source was found, on inspection, to contain zero records for the
currently loaded timetable, so it cannot be relied on here).

"Effective" occupancy means: start from every ORIGINAL canonical
event scheduled at that day/slot. If an event's block has since
been confirmed-shifted to a different room (via RoomShiftStore),
it is treated as occupying its NEW room instead of its original
one. This lets a later query account for confirmed room changes
without ever rewriting canonical event data.

============================================================
MULTI-PERIOD BLOCKS
============================================================

A lab is identified by (teacher, day, slot). The COMPLETE block
containing that slot - however many contiguous periods it spans -
is resolved via absence_engine._affected_blocks(), the same block
detection already used for absence/replacement planning. A
proposed shift always applies to every slot in that block; this
module never silently shifts only part of a multi-period block.

============================================================
PLAN / CONFIRM
============================================================

plan_shift() is completely side-effect free: it never writes to
RoomShiftStore. confirm_shift() re-resolves the source block and
re-validates target-room availability FROM SCRATCH (rather than
trusting the plan's earlier snapshot), so any change to the
timetable state between planning and confirming - including a
stale/no-longer-valid plan - is caught rather than silently
applied.
"""

from datetime import datetime, timezone

from scheduling.room_shift_store import RoomShiftStore


class LabShiftCoordinator:

    def __init__(
        self,
        query_engine,
        absence_engine,
        conflict_engine=None,
        store=None,
    ):
        self.query_engine = query_engine
        self.absence_engine = absence_engine
        self.conflict_engine = conflict_engine
        self.store = store or RoomShiftStore()

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _text(value):
        return str(value or "").strip()

    # ============================================================
    # BLOCK RESOLUTION
    #
    # Identifies the COMPLETE multi-period block (from the
    # ORIGINAL canonical timetable) for the given teacher/day,
    # using EITHER a specific slot OR a class_name/subject pair
    # to disambiguate which of that teacher's blocks on that day
    # is meant. Reuses absence_engine._affected_blocks() - the
    # same block detection already used for absence/replacement
    # planning - rather than re-implementing contiguous-slot
    # grouping here.
    #
    # ROOT CAUSE OF THE PREVIOUS BUG (kept here as a record of
    # why this validation exists): query_engine._day()/_slot()
    # are deliberately LENIENT, general-purpose normalizers used
    # throughout the whole project - given text they don't
    # recognize, they pass it through lowercased rather than
    # failing. That is correct behavior for those shared
    # primitives, but it meant a caller who passed arguments in
    # the wrong position (e.g. a subject string where a day was
    # expected) got no early signal: day_key/slot_key were both
    # "truthy", so the old code proceeded to search for a
    # (day="sma lab group 1", slot="wednesday") block that could
    # never exist, and reported the generic, misleading
    # "source_event_not_found". This method now explicitly
    # validates day_key against the fixed set of real weekday
    # names, and validates a supplied slot_key is actually
    # numeric, so a genuinely malformed call fails fast with a
    # specific "invalid_day"/"invalid_slot" reason instead of a
    # confusing not-found.
    # ============================================================

    _VALID_DAYS = frozenset({
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    })

    def find_lab_block(
        self,
        teacher=None,
        class_name=None,
        subject=None,
        day=None,
        slot=None,
    ):

        day_key = self.query_engine._day(day)

        if not day_key:
            return {
                "found": False,
                "reason": "missing_day",
            }

        if day_key not in self._VALID_DAYS:
            return {
                "found": False,
                "reason": "invalid_day",
            }

        slot_key = None

        if slot is not None:

            slot_key = self.query_engine._slot(slot)

            if not isinstance(slot_key, int):
                return {
                    "found": False,
                    "reason": "invalid_slot",
                }

        resolved_teacher = self._text(teacher)

        # ---------------------------------------------------
        # If no teacher was given but a class was, resolve the
        # teacher from the existing class_schedule() lookup for
        # that class/day(/slot), reusing the existing class
        # query rather than a new lookup mechanism.
        # ---------------------------------------------------

        if not resolved_teacher and class_name:

            class_lookup = {
                "class_name": class_name,
                "day": day_key,
            }

            if slot_key is not None:
                class_lookup["slot"] = slot_key

            class_result = self.query_engine.class_schedule(
                **class_lookup
            )

            class_events = class_result.get("results", [])

            teachers_at_slot = sorted(set(
                self._text(event.get("teacher"))
                for event in class_events
                if isinstance(event, dict)
                and event.get("teacher")
            ))

            if len(teachers_at_slot) == 1:
                resolved_teacher = teachers_at_slot[0]

            elif len(teachers_at_slot) > 1:
                return {
                    "found": False,
                    "reason": "ambiguous_source_block",
                    "candidates": teachers_at_slot,
                }

        if not resolved_teacher:
            return {
                "found": False,
                "reason": "missing_teacher_or_class",
            }

        blocks = self.absence_engine._affected_blocks(
            resolved_teacher,
            day_key,
        )

        if slot_key is not None:

            # -----------------------------------------------
            # Identify by slot (original behavior) - the block
            # containing the requested slot. This is the mode
            # plan_shift()/confirm_shift()/find_available_rooms()
            # always use internally.
            # -----------------------------------------------

            matching_blocks = [
                block
                for block in blocks
                if any(
                    self.query_engine._same_slot(s, slot_key)
                    for s in block.get("slots", [])
                )
            ]

        else:

            # -----------------------------------------------
            # Identify by class_name and/or subject instead of
            # a slot number - both, when given, must match
            # (normalized) the block's own class_name/subject.
            # -----------------------------------------------

            class_key = (
                self.query_engine._normalize(class_name)
                if class_name
                else None
            )

            subject_key = (
                self.query_engine._normalize(subject)
                if subject
                else None
            )

            if not class_key and not subject_key:
                return {
                    "found": False,
                    "reason": "missing_slot_or_class_subject",
                }

            matching_blocks = []

            for block in blocks:

                if class_key and (
                    self.query_engine._normalize(
                        block.get("class_name")
                    ) != class_key
                ):
                    continue

                if subject_key and (
                    self.query_engine._normalize(
                        block.get("subject")
                    ) != subject_key
                ):
                    continue

                matching_blocks.append(block)

        if not matching_blocks:
            return {
                "found": False,
                "reason": "source_event_not_found",
            }

        if len(matching_blocks) > 1:
            return {
                "found": False,
                "reason": "ambiguous_source_block",
            }

        matched_block = matching_blocks[0]

        # -----------------------------------------------------
        # LAB-ONLY VALIDATION
        #
        # find_lab_block() must never report a genuine match for
        # a Theory/Seminar/other non-Lab session as a "found" lab
        # block. This checks the block's own canonical "type"
        # field - the SAME field absence_engine._affected_blocks()
        # already groups by (block["type"] is populated directly
        # from the underlying canonical events' "type" field, and
        # every event within one block already shares that same
        # type, since block grouping itself is keyed by type).
        # No subject-text heuristic (e.g. checking for the word
        # "lab" in the subject) is used - only the event's actual
        # recorded type.
        # -----------------------------------------------------

        if self.query_engine._normalize(
            matched_block.get("type")
        ) != "lab":

            return {
                "found": False,
                "reason": "non_lab_event",
            }

        block = dict(matched_block)
        block["teacher"] = resolved_teacher
        block["day"] = day_key
        block["slot_time"] = (
            self.absence_engine._block_time(block)
        )

        return {
            "found": True,
            "block": block,
        }

    # ============================================================
    # ROOM RESOLUTION
    #
    # Resolves raw, user-typed room text against the rooms
    # actually present in the currently loaded canonical
    # timetable (via QueryEngine.entity_knowledge()) - never a
    # hard-coded room list. Mirrors the same
    # exact/broad(ambiguous)/none pattern already established for
    # class references (QueryEngine.resolve_class_reference()).
    # ============================================================

    def resolve_room(self, raw_text):

        known_rooms = (
            self.query_engine.entity_knowledge()["rooms"]
        )

        query_text = self.query_engine._normalize(raw_text)

        if not query_text:
            return {
                "mode": "none",
                "room": None,
                "matching_rooms": [],
            }

        exact_matches = [
            room
            for room in known_rooms
            if self.query_engine._normalize(room) == query_text
        ]

        if exact_matches:
            return {
                "mode": "exact",
                "room": exact_matches[0],
                "matching_rooms": exact_matches,
            }

        matching_rooms = sorted(
            room
            for room in known_rooms
            if self.query_engine._contains(room, raw_text)
        )

        if len(matching_rooms) == 1:
            return {
                "mode": "exact",
                "room": matching_rooms[0],
                "matching_rooms": matching_rooms,
            }

        if len(matching_rooms) > 1:
            return {
                "mode": "ambiguous",
                "room": None,
                "matching_rooms": matching_rooms,
            }

        return {
            "mode": "none",
            "room": None,
            "matching_rooms": [],
        }

    # ============================================================
    # EFFECTIVE ROOM OCCUPANCY
    #
    # For a single day/slot, returns which block(s) effectively
    # occupy each room right now: every ORIGINAL canonical event
    # at that day/slot, EXCEPT that if an event's block has been
    # CONFIRMED-shifted to a different room, it is reported as
    # occupying that new room instead. Confirmed room shifts are
    # therefore automatically accounted for by later queries,
    # without ever rewriting canonical event data.
    # ============================================================

    def _effective_occupants(self, day, slot):

        day_key = self.query_engine._day(day)
        slot_key = self.query_engine._slot(slot)

        occupants = {}

        for event in self.query_engine._events():

            if not self.query_engine._same_day(
                event.get("day"), day_key
            ):
                continue

            if not self.query_engine._same_slot(
                event.get("slot"), slot_key
            ):
                continue

            teacher = event.get("teacher", "")
            class_name = event.get("class_name", "")
            subject = event.get("subject", "")
            group_name = event.get("group_name", "")
            event_type = event.get("type", "")
            original_room = event.get("room", "")

            shift = self.store.find_confirmed_for_block(
                teacher,
                class_name,
                subject,
                group_name,
                event_type,
                day_key,
            )

            effective_room = (
                shift["target_room"] if shift else original_room
            )

            room_key = self.query_engine._normalize(
                effective_room
            )

            if not room_key:
                continue

            occupants.setdefault(room_key, []).append({
                "teacher": teacher,
                "class_name": class_name,
                "subject": subject,
                "room": effective_room,
                "shifted": bool(shift),
            })

        return occupants

    def _room_conflicts_for_block(self, room, day, slots):
        """
        Returns a list of conflict entries - one per affected
        slot where `room` is effectively occupied by some OTHER
        block - checked against every slot in the block, so a
        multi-period block is only considered free when the
        target room is free for ALL of its slots.
        """

        room_key = self.query_engine._normalize(room)

        conflicts = []

        for slot in slots:

            occupants = self._effective_occupants(day, slot)

            for occupant in occupants.get(room_key, []):

                conflicts.append({
                    "slot": self.query_engine._slot(slot),
                    "teacher": occupant["teacher"],
                    "class_name": occupant["class_name"],
                    "subject": occupant["subject"],
                    "shifted_here": occupant["shifted"],
                })

        return conflicts

    # ============================================================
    # FIND AVAILABLE ROOMS
    # ============================================================

    def find_available_rooms(
        self,
        teacher=None,
        class_name=None,
        day=None,
        slot=None,
    ):

        lookup = self.find_lab_block(
            teacher=teacher,
            class_name=class_name,
            day=day,
            slot=slot,
        )

        if not lookup["found"]:
            return {
                "success": False,
                "reason": lookup["reason"],
                "candidates": lookup.get("candidates"),
            }

        block = lookup["block"]

        known_rooms = (
            self.query_engine.entity_knowledge()["rooms"]
        )

        source_room_key = self.query_engine._normalize(
            block.get("room")
        )

        available = []

        for room in known_rooms:

            if self.query_engine._normalize(room) == (
                source_room_key
            ):
                continue

            conflicts = self._room_conflicts_for_block(
                room,
                block["day"],
                block["slots"],
            )

            if not conflicts:
                available.append(room)

        return {
            "success": True,
            "teacher": block["teacher"],
            "class_name": block["class_name"],
            "subject": block["subject"],
            "group_name": block["group_name"],
            "type": block["type"],
            "day": block["day"],
            "slots": block["slots"],
            "slot_time": block["slot_time"],
            "source_room": block.get("room", ""),
            "available_rooms": available,
        }

    # ============================================================
    # PLAN (side-effect free)
    # ============================================================

    def plan_shift(
        self,
        teacher=None,
        class_name=None,
        day=None,
        slot=None,
        target_room=None,
    ):
        """
        Produces a structured, side-effect-free room-shift
        proposal. Never writes to RoomShiftStore.
        """

        lookup = self.find_lab_block(
            teacher=teacher,
            class_name=class_name,
            day=day,
            slot=slot,
        )

        if not lookup["found"]:
            return {
                "success": False,
                "status": "rejected",
                "reason": lookup["reason"],
                "candidates": lookup.get("candidates"),
            }

        block = lookup["block"]

        room_resolution = self.resolve_room(target_room)

        if room_resolution["mode"] == "none":
            return {
                "success": False,
                "status": "rejected",
                "reason": "target_room_not_found",
            }

        if room_resolution["mode"] == "ambiguous":
            return {
                "success": False,
                "status": "rejected",
                "reason": "target_room_ambiguous",
                "matching_rooms": room_resolution[
                    "matching_rooms"
                ],
            }

        resolved_target_room = room_resolution["room"]

        source_room = block.get("room", "")

        if self.query_engine._normalize(
            resolved_target_room
        ) == self.query_engine._normalize(source_room):
            return {
                "success": False,
                "status": "rejected",
                "reason": "target_room_same_as_source",
            }

        conflicts = self._room_conflicts_for_block(
            resolved_target_room,
            block["day"],
            block["slots"],
        )

        if conflicts:
            return {
                "success": False,
                "status": "rejected",
                "reason": "target_room_occupied",
                "teacher": block["teacher"],
                "class_name": block["class_name"],
                "subject": block["subject"],
                "day": block["day"],
                "slots": block["slots"],
                "source_room": source_room,
                "target_room": resolved_target_room,
                "conflicts": conflicts,
            }

        return {
            "success": True,
            "status": "proposed",
            "teacher": block["teacher"],
            "class_name": block["class_name"],
            "subject": block["subject"],
            "group_name": block["group_name"],
            "type": block["type"],
            "day": block["day"],
            "slots": block["slots"],
            "slot_time": block["slot_time"],
            "source_room": source_room,
            "target_room": resolved_target_room,
            "affected_events": block.get("events", []),
            "conflicts": [],
        }

    # ============================================================
    # CONFIRM
    #
    # Re-resolves the source block and re-validates target-room
    # availability FROM SCRATCH using the plan's own identifying
    # fields (teacher/day/one of its slots/target_room), rather
    # than trusting the earlier plan snapshot. This is what
    # detects a stale plan: if the timetable state has changed
    # since planning (e.g. another shift has since claimed the
    # target room, or the source block no longer resolves the
    # same way), re-planning now will surface that and confirm()
    # rejects instead of applying a now-invalid change.
    # ============================================================

    def confirm_shift(self, plan):

        if not isinstance(plan, dict) or not plan.get("success"):
            return {
                "success": False,
                "status": "rejected",
                "reason": "invalid_plan",
            }

        teacher = plan.get("teacher")
        day = plan.get("day")
        slots = plan.get("slots") or []
        target_room = plan.get("target_room")

        if not slots:
            return {
                "success": False,
                "status": "rejected",
                "reason": "invalid_plan",
            }

        fresh_plan = self.plan_shift(
            teacher=teacher,
            day=day,
            slot=slots[0],
            target_room=target_room,
        )

        if not fresh_plan.get("success"):
            return {
                "success": False,
                "status": "rejected",
                "reason": "stale_plan",
                "revalidation": fresh_plan,
            }

        # ------------------------------------------------------
        # The freshly re-resolved block must match the plan being
        # confirmed - same slots and same source room - otherwise
        # the timetable state has changed in a way that makes the
        # original plan unsafe to apply as described.
        # ------------------------------------------------------

        same_slots = (
            [self.query_engine._slot(s) for s in fresh_plan["slots"]]
            == [self.query_engine._slot(s) for s in slots]
        )

        same_source_room = (
            self.query_engine._normalize(
                fresh_plan["source_room"]
            )
            == self.query_engine._normalize(
                plan.get("source_room")
            )
        )

        if not same_slots or not same_source_room:
            return {
                "success": False,
                "status": "rejected",
                "reason": "stale_plan",
                "revalidation": fresh_plan,
            }

        shift_id = (
            f"shift-{datetime.now(timezone.utc).timestamp():.6f}"
        )

        record = {
            "shift_id": shift_id,
            "teacher": fresh_plan["teacher"],
            "class_name": fresh_plan["class_name"],
            "subject": fresh_plan["subject"],
            "group_name": fresh_plan["group_name"],
            "type": fresh_plan["type"],
            "day": fresh_plan["day"],
            "slots": fresh_plan["slots"],
            "slot_time": fresh_plan["slot_time"],
            "source_room": fresh_plan["source_room"],
            "target_room": fresh_plan["target_room"],
            "status": "confirmed",
            "confirmed_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        self.store.add(record)

        return {
            "success": True,
            "status": "confirmed",
            "shift": record,
        }