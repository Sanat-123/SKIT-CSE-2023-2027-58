"""
MULTI-ABSENCE COORDINATION

Coordinates replacement assignment across MULTIPLE simultaneously
absent faculty members, so the choice made for one absent
teacher's block is aware of the choices already made for every
other absent teacher's block in the same planning run.

This module does not implement its own qualification, timetable
access, or persistence logic. It is a thin coordination layer on
top of the EXISTING engines:

    FacultyAbsenceEngine
        Affected blocks (multi-period blocks preserved, never
        split - this planner does not touch that logic) and
        tier-ranked, timetable-qualified replacement candidates,
        computed PER absent teacher, in isolation.

    FacultyAssignmentEngine
        Availability against the original timetable AND every
        already-CONFIRMED replacement assignment
        (is_teacher_available), current total workload
        (total_workload), and the actual persistence of a
        confirmed assignment (assign_recommendation) - reused
        unchanged for both eligibility checks and confirmation.

    FacultyConflictEngine (optional)
        Used only as a post-confirm audit (assignment_conflicts)
        so a caller gets an extra, independently-computed
        assurance that a freshly confirmed batch introduced no
        conflicts. Never consulted during planning/selection.

Nothing in this file hard-codes any faculty name, class name,
subject, day, slot, or workload number. Every decision is derived
from whatever the absence/assignment engines report for the
timetable data currently loaded.

============================================================
ALGORITHM
============================================================

For each requested absence, FacultyAbsenceEngine.replacement_
candidates() already computes the absent teacher's affected
blocks and, per block, the set of tier-qualified candidates
(subject/class-context similarity tiers), each already required
to be free against the ORIGINAL timetable for the block's
complete set of slots.

This planner pools every block from every requested absence
together and treats replacement selection as a BIPARTITE
MATCHING problem:

    left  (demand)    nodes = affected blocks, one per absent
                                teacher's block, tagged with that
                                teacher and day
    right (candidate) nodes = eligible replacement faculty

An edge block -> candidate exists only when the candidate:

    1. is one of absence_engine's already tier-qualified
       candidates for that block (existing ranking semantics
       reused as-is, never re-implemented here), AND
    2. is not one of the OTHER faculty members being planned as
       absent in this same batch (an absent teacher can never be
       used as somebody else's replacement), AND
    3. is available for the block's COMPLETE set of slots against
       BOTH the original timetable and every CURRENTLY CONFIRMED
       replacement assignment (assignment_engine.
       is_teacher_available - reused as-is).

Each candidate may be matched to AT MOST ONE block within a
single plan. See "DESIGN SIMPLIFICATION" below for why.

The matching itself is solved with a textbook augmenting-path
(Kuhn's) algorithm, which guarantees MAXIMUM CARDINALITY
matching (as many blocks covered as the constraints allow) no
matter what order blocks or candidate edges are visited in. This
planner deliberately orders blocks "most-constrained first"
(fewest eligible candidates first) and, within a block, orders
candidate edges by:

    1. tier (lower/better first - preserves absence_engine's
       existing priority tiers)
    2. total workload for that day (original timetable periods
       + already-CONFIRMED replacement periods, via
       assignment_engine.total_workload - existing method)
    3. replacement workload the candidate has ALREADY picked up
       elsewhere in THIS in-progress plan (recomputed live from
       the current partial matching as the algorithm runs)
    4. faculty name (final deterministic tie-break)

so that, among the (possibly several) maximum-cardinality
matchings that exist, the algorithm is naturally biased toward
higher-quality, better-balanced assignments without ever
sacrificing the maximum-coverage guarantee.

============================================================
DESIGN SIMPLIFICATION - one block per candidate per plan
============================================================

A single replacement teacher COULD legitimately cover two
different absent teachers' blocks on the same day, as long as
the blocks' slots do not overlap. Modelling that fully would
turn this into a resource-constrained (per-slot capacity)
matching problem rather than a classical 1-1 bipartite one.

This planner instead matches each candidate to at most ONE block
per plan. This is a deliberate, documented simplification:

    - it keeps the matching a classical bipartite problem,
      solvable with a plain augmenting-path algorithm,
    - it trivially guarantees a faculty member is never given
      two simultaneous (or even non-overlapping) replacement
      duties from a single planning run, satisfying "do not
      assign one faculty to overlapping duties" and "do not
      silently assign a faculty member to two simultaneous
      classes" without any extra slot-overlap bookkeeping,
    - it naturally spreads replacement duty across more distinct
      faculty rather than concentrating it.

The trade-off is that a plan may occasionally leave a block
uncovered even though some already-matched candidate would, in
principle, have been free for it too (on a different, non-
overlapping slot). This is flagged here rather than hidden, in
case a future revision wants to lift the restriction.

============================================================
PLAN vs CONFIRM
============================================================

plan() is completely side-effect free. It never writes to
AssignmentStore and never calls assign()/assign_recommendation().
It only reads timetable data (via absence_engine/assignment_
engine) and returns a structured result.

confirm() takes a plan produced by plan() and persists every
covered block by calling assignment_engine.assign_recommendation()
- the EXISTING, already-tested confirmation/persistence path.
No new persistence logic is implemented here. Each item is
confirmed independently, in order; a failure on one item does
not roll back items already confirmed earlier in the same call,
because each earlier confirm is already a real, independently
valid, persisted assignment by the time a later one fails.
"""

from collections import defaultdict


class MultiAbsenceCoordinator:

    def __init__(
        self,
        absence_engine,
        assignment_engine,
        workload_engine=None,
        conflict_engine=None,
    ):
        self.absence_engine = absence_engine
        self.assignment_engine = assignment_engine

        # Not read directly - assignment_engine.total_workload()
        # already combines original-timetable periods with
        # confirmed replacement periods, which covers the
        # "total workload" ranking criterion without duplicating
        # counting logic. Kept as a constructor parameter so
        # callers that already wire up every engine together can
        # pass it, and so a future revision can use it directly
        # without changing this class's public signature.
        self.workload_engine = workload_engine

        # Optional. Used only as a post-confirm audit step (see
        # confirm()) - never consulted during planning/selection.
        self.conflict_engine = conflict_engine

    # ============================================================
    # BASIC HELPERS
    # ============================================================

    @staticmethod
    def _text(value):
        return str(value or "").strip()

    @staticmethod
    def _key(value):
        return str(value or "").strip().lower()

    def _normalize_day(self, day):
        return self.absence_engine._normalize_day(day)

    # ============================================================
    # PLAN (side-effect free)
    # ============================================================

    def plan(self, absences):
        """
        absences: iterable of {"teacher": ..., "day": ...}

        Returns a structured, side-effect-free plan:

            {
                "query_type": "multi_absence_plan",
                "absences_considered": [...],
                "covered": [ recommendation-shaped dicts, ready
                              for assignment_engine.
                              assign_recommendation() ],
                "uncovered": [ {..., "reason": ...} ],
                "warnings": [ {...} ],
                "covered_count": int,
                "uncovered_count": int,
            }

        Never reads or writes AssignmentStore beyond the
        read-only checks already performed by
        assignment_engine.is_teacher_available()/total_workload().
        Never calls assign()/assign_recommendation().
        """

        normalized_absences, warnings = self._normalize_absences(
            absences
        )

        by_day = defaultdict(list)

        for entry in normalized_absences:
            by_day[entry["day"]].append(entry["teacher"])

        covered = []
        uncovered = []

        for day_key, teachers in by_day.items():

            day_result = self._plan_for_day(day_key, teachers)

            covered.extend(day_result["covered"])
            uncovered.extend(day_result["uncovered"])
            warnings.extend(day_result["warnings"])

        return {
            "query_type": "multi_absence_plan",
            "absences_considered": normalized_absences,
            "covered": covered,
            "uncovered": uncovered,
            "warnings": warnings,
            "covered_count": len(covered),
            "uncovered_count": len(uncovered),
        }

    # ------------------------------------------------------------
    # INPUT NORMALIZATION
    # ------------------------------------------------------------

    def _normalize_absences(self, absences):

        normalized = []
        warnings = []
        seen = set()

        for item in absences or []:

            if not isinstance(item, dict):
                warnings.append({
                    "type": "invalid_absence_entry",
                    "input": item,
                    "message": (
                        "Each absence entry must be a "
                        "dictionary with 'teacher' and 'day'."
                    ),
                })
                continue

            teacher = self._text(item.get("teacher"))
            raw_day = item.get("day")
            day_key = self._normalize_day(raw_day)

            if not teacher:
                warnings.append({
                    "type": "invalid_absence_entry",
                    "input": item,
                    "message": "Missing faculty name.",
                })
                continue

            if not day_key:
                warnings.append({
                    "type": "invalid_day",
                    "teacher": teacher,
                    "day": raw_day,
                    "message": (
                        "Day could not be recognized."
                    ),
                })
                continue

            dedupe_key = (self._key(teacher), day_key)

            if dedupe_key in seen:
                warnings.append({
                    "type": "duplicate_absence_entry",
                    "teacher": teacher,
                    "day": day_key,
                    "message": (
                        "Duplicate absence entry ignored."
                    ),
                })
                continue

            seen.add(dedupe_key)

            normalized.append({
                "teacher": teacher,
                "day": day_key,
            })

        return normalized, warnings

    # ------------------------------------------------------------
    # PLAN FOR ONE DAY
    # ------------------------------------------------------------

    def _plan_for_day(self, day_key, teachers):
        """
        Builds the block/candidate pool for every absent teacher
        on this single day, then solves ONE bipartite matching
        across all of them together (blocks on different days
        never compete for the same slot, so each day is planned
        independently).
        """

        warnings = []
        absent_set = {self._key(t) for t in teachers}

        blocks = []
        workload_cache = {}

        for teacher in teachers:

            result = self.absence_engine.replacement_candidates(
                teacher,
                day_key,
            )

            block_summaries = result.get("blocks", [])

            if not block_summaries:
                warnings.append({
                    "type": "no_scheduled_classes",
                    "teacher": teacher,
                    "day": day_key,
                    "message": (
                        f"{teacher} has no scheduled classes on "
                        f"{day_key} - nothing to cover."
                    ),
                })
                continue

            all_candidates = result.get("results", [])

            for block_summary in block_summaries:

                block_index = block_summary["block_index"]

                raw_candidates = [
                    candidate
                    for candidate in all_candidates
                    if candidate["block_index"] == block_index
                ]

                eligible = self._eligible_candidates(
                    raw_candidates,
                    day_key,
                    block_summary["slots"],
                    absent_set,
                    workload_cache,
                )

                room = (
                    raw_candidates[0].get("room", "")
                    if raw_candidates
                    else ""
                )

                blocks.append({
                    "absent_teacher": teacher,
                    "day": day_key,
                    "block_index": block_index,
                    "slots": block_summary["slots"],
                    "slot_time": block_summary["slot_time"],
                    "period_count": block_summary["period_count"],
                    "subject": block_summary["subject"],
                    "subject_family": block_summary[
                        "subject_family"
                    ],
                    "class_name": block_summary["class_name"],
                    "group_name": block_summary["group_name"],
                    "type": block_summary["type"],
                    "room": room,
                    "candidates": eligible,
                })

        # ----------------------------------------------------
        # Deterministic, most-constrained-block-first order.
        # This does not affect the MAXIMUM CARDINALITY the
        # matcher finds (a guaranteed property of Kuhn's
        # algorithm regardless of processing order) but tends
        # to reduce avoidable contention over scarce candidates.
        # ----------------------------------------------------

        blocks.sort(
            key=lambda b: (
                len(b["candidates"]),
                self._key(b["absent_teacher"]),
                b["block_index"],
                self._key(b["class_name"]),
                self._key(b["subject"]),
            )
        )

        matcher = _BipartiteMatcher(blocks)
        matcher.solve()

        covered = []
        uncovered = []

        for index, block in enumerate(blocks):

            candidate = matcher.block_index_to_candidate.get(
                index
            )

            if candidate is None:

                reason = (
                    "no_qualified_candidate"
                    if not block["candidates"]
                    else "all_qualified_candidates_claimed"
                )

                uncovered.append({
                    "absent_teacher": block["absent_teacher"],
                    "day": block["day"],
                    "block_index": block["block_index"],
                    "slots": block["slots"],
                    "slot_time": block["slot_time"],
                    "period_count": block["period_count"],
                    "subject": block["subject"],
                    "subject_family": block["subject_family"],
                    "class_name": block["class_name"],
                    "group_name": block["group_name"],
                    "type": block["type"],
                    "room": block["room"],
                    "reason": reason,
                })

                continue

            covered.append({
                "absent_teacher": block["absent_teacher"],
                "day": block["day"],
                "slots": block["slots"],
                "slot_time": block["slot_time"],
                "period_count": block["period_count"],
                "subject": block["subject"],
                "subject_family": block["subject_family"],
                "class_name": block["class_name"],
                "group_name": block["group_name"],
                "type": block["type"],
                "room": block["room"],
                "replacement_teacher": candidate[
                    "replacement_teacher"
                ],
                "priority": candidate["priority"],
                "priority_reason": candidate[
                    "priority_reason"
                ],
                "class_similarity": candidate[
                    "class_similarity"
                ],
                "subject_similarity": candidate[
                    "subject_similarity"
                ],
            })

        return {
            "covered": covered,
            "uncovered": uncovered,
            "warnings": warnings,
        }

    # ------------------------------------------------------------
    # ELIGIBLE CANDIDATES FOR ONE BLOCK
    # ------------------------------------------------------------

    def _eligible_candidates(
        self,
        raw_candidates,
        day_key,
        slots,
        absent_set,
        workload_cache,
    ):
        """
        Filters absence_engine's already tier-qualified candidate
        list down to those that:

            - are not themselves absent in this same batch, and
            - are available for the block's complete slots against
              the original timetable AND every currently confirmed
              replacement assignment.

        Tier qualification/ranking itself is NOT re-implemented
        here - it is taken as-is from absence_engine.
        """

        eligible = []

        for candidate in raw_candidates:

            candidate_name = candidate["replacement_teacher"]
            candidate_key = self._key(candidate_name)

            if candidate_key in absent_set:
                continue

            if not self.assignment_engine.is_teacher_available(
                candidate_name,
                day_key,
                slots,
            ):
                continue

            if candidate_key not in workload_cache:

                workload_cache[candidate_key] = (
                    self.assignment_engine.total_workload(
                        candidate_name,
                        day_key,
                    )["total_periods"]
                )

            eligible.append({
                **candidate,
                "_total_workload": workload_cache[
                    candidate_key
                ],
            })

        return eligible

    # ============================================================
    # CONFIRM (uses the EXISTING assignment engine)
    # ============================================================

    def confirm(self, plan):
        """
        Confirms every block in plan["covered"] by calling the
        EXISTING assignment_engine.assign_recommendation() -
        no new persistence logic is implemented here.

        Each item is confirmed independently and in order. A
        failure on one item does not roll back items already
        confirmed earlier in this call.

        If a conflict_engine was supplied to the constructor,
        assignment_conflicts() is run once AFTER all confirms as
        a purely informational post-confirm audit; it never
        affects which items are confirmed.
        """

        confirmed = []
        failed = []

        for item in plan.get("covered", []):

            result = self.assignment_engine.assign_recommendation(
                item,
                absent_teacher=item.get("absent_teacher", ""),
            )

            if result.get("success"):
                confirmed.append(result["assignment"])
            else:
                failed.append({
                    "item": item,
                    "error": result,
                })

        post_confirm_conflicts = None

        if self.conflict_engine is not None:

            try:
                post_confirm_conflicts = (
                    self.conflict_engine.assignment_conflicts()
                )
            except Exception:
                post_confirm_conflicts = None

        return {
            "query_type": "multi_absence_confirm",
            "confirmed": confirmed,
            "failed": failed,
            "confirmed_count": len(confirmed),
            "failed_count": len(failed),
            "post_confirm_conflicts": post_confirm_conflicts,
        }


class _BipartiteMatcher:
    """
    Classical augmenting-path (Kuhn's algorithm) bipartite matcher.

    Left nodes  = blocks (each requiring a COMPLETE-block
                  replacement - never split across candidates)
    Right nodes = eligible replacement faculty (candidate teacher
                  names)

    Each right node (candidate) is matched to AT MOST ONE left
    node (block) within a single plan - see the module docstring
    ("DESIGN SIMPLIFICATION") for why.

    Guarantees MAXIMUM CARDINALITY matching - a textbook property
    of Kuhn's algorithm, independent of node/edge processing
    order. Candidate edges are explored in a deterministic
    QUALITY order (tier -> total workload -> workload already
    accumulated by this candidate elsewhere in the current plan
    -> faculty name) so that, among the possibly several
    maximum-cardinality matchings that exist, the result is
    biased toward higher-quality, better-balanced assignments
    without sacrificing the maximum-coverage guarantee.
    """

    def __init__(self, blocks):
        self.blocks = blocks

        # candidate_key -> index into self.blocks
        self.candidate_to_block_index = {}

        # index into self.blocks -> candidate dict
        self.block_index_to_candidate = {}

    def _accumulated_plan_workload(self, candidate_key):

        block_index = self.candidate_to_block_index.get(
            candidate_key
        )

        if block_index is None:
            return 0

        return self.blocks[block_index].get(
            "period_count",
            0,
        ) or 0

    def _sorted_candidates(self, block):

        def sort_key(candidate):

            name_key = candidate[
                "replacement_teacher"
            ].strip().lower()

            return (
                candidate.get("priority", 99),
                candidate.get("_total_workload", 0),
                self._accumulated_plan_workload(name_key),
                name_key,
            )

        return sorted(
            block["candidates"],
            key=sort_key,
        )

    def _try_augment(self, block_index, visited):

        block = self.blocks[block_index]

        for candidate in self._sorted_candidates(block):

            name_key = candidate[
                "replacement_teacher"
            ].strip().lower()

            if name_key in visited:
                continue

            visited.add(name_key)

            current_block_index = (
                self.candidate_to_block_index.get(name_key)
            )

            if (
                current_block_index is None
                or self._try_augment(
                    current_block_index,
                    visited,
                )
            ):
                self.candidate_to_block_index[name_key] = (
                    block_index
                )
                self.block_index_to_candidate[block_index] = (
                    candidate
                )
                return True

        return False

    def solve(self):

        for block_index in range(len(self.blocks)):

            visited = set()
            self._try_augment(block_index, visited)

        return self.block_index_to_candidate