from collections import defaultdict


class FacultyWorkloadEngine:

    def __init__(self, query_engine):
        self.query_engine = query_engine

    # --------------------------------------------------
    # GET ALL SCHEDULED EVENTS
    # --------------------------------------------------

    def _events(self):
        try:
            return list(self.query_engine._events())
        except Exception:
            return []

    # --------------------------------------------------
    # NORMALIZE DAY
    # --------------------------------------------------

    @staticmethod
    def _normalize_day(day):

        if not day:
            return None

        day = str(day).strip().lower()

        days = {
            "mon": "monday",
            "monday": "monday",

            "tue": "tuesday",
            "tues": "tuesday",
            "tuesday": "tuesday",

            "wed": "wednesday",
            "wednesday": "wednesday",

            "thu": "thursday",
            "thur": "thursday",
            "thurs": "thursday",
            "thursday": "thursday",

            "fri": "friday",
            "friday": "friday",

            "sat": "saturday",
            "saturday": "saturday",

            "sun": "sunday",
            "sunday": "sunday",
        }

        return days.get(day)

    # --------------------------------------------------
    # GET FACULTY NAME
    # --------------------------------------------------

    @staticmethod
    def _teacher(event):

        if not isinstance(event, dict):
            return ""

        return str(
            event.get(
                "teacher",
                event.get("faculty", "")
            )
        ).strip()

    # --------------------------------------------------
    # GET DAY FROM EVENT
    # --------------------------------------------------

    @staticmethod
    def _event_day(event):

        if not isinstance(event, dict):
            return ""

        return str(
            event.get("day", "")
        ).strip().lower()

    # --------------------------------------------------
    # DAILY WORKLOAD
    # --------------------------------------------------

    def daily_workload(self, day):

        day_key = self._normalize_day(day)

        if not day_key:
            return {
                "day": day,
                "count": 0,
                "results": []
            }

        workload = defaultdict(int)

        for event in self._events():

            teacher = self._teacher(event)

            if not teacher:
                continue

            event_day = self._event_day(event)

            if event_day != day_key:
                continue

            workload[teacher] += 1

        results = []

        for teacher, periods in workload.items():

            results.append({
                "teacher": teacher,
                "periods": periods
            })

        results.sort(
            key=lambda x: (
                -x["periods"],
                x["teacher"].lower()
            )
        )

        return {
            "query_type": "daily_workload",
            "day": day_key,
            "count": len(results),
            "results": results
        }

    # --------------------------------------------------
    # WORKLOAD OF ONE FACULTY ON ONE DAY
    # --------------------------------------------------

    def faculty_daily_workload(
        self,
        teacher,
        day
    ):

        day_key = self._normalize_day(day)

        if not day_key:
            return {
                "teacher": teacher,
                "day": day,
                "periods": 0,
                "events": []
            }

        teacher_key = str(
            teacher
        ).strip().lower()

        events = []

        for event in self._events():

            event_teacher = self._teacher(event)

            if not event_teacher:
                continue

            if event_teacher.lower() != teacher_key:
                continue

            if self._event_day(event) != day_key:
                continue

            events.append(event)

        return {
            "query_type": "faculty_daily_workload",
            "teacher": teacher,
            "day": day_key,
            "periods": len(events),
            "events": events
        }

    # --------------------------------------------------
    # SEMESTER WORKLOAD
    #
    # Faculty workload (period counts) for an entire
    # semester, e.g. "7th semester".
    #
    # A semester is not a field stored anywhere in the
    # timetable data. It is derived from the leading digit
    # of each event's class_name, using the exact same
    # derivation query_engine.semester_schedule() already
    # uses (query_engine._semester_from_class_name), so
    # "semester 7" means the same thing everywhere in the
    # app and the mapping is never duplicated or hard-coded.
    #
    # Uses the same "one canonical event = one period"
    # definition as daily_workload()/weekly_workload() above.
    # Multi-slot labs are already represented as one canonical
    # event per slot (see CanonicalEventMatcher), so counting
    # one period per matching event here is consistent with
    # the rest of the workload engine and does not double- or
    # under-count multi-hour blocks.
    # --------------------------------------------------

    def semester_workload(
        self,
        semester,
        day=None
    ):

        try:
            target_semester = int(semester)
        except (TypeError, ValueError):
            return {
                "query_type": "semester_workload",
                "semester": semester,
                "day": day,
                "count": 0,
                "results": []
            }

        day_key = None

        if day:
            day_key = self._normalize_day(day)

        workload = defaultdict(int)
        subjects = defaultdict(set)

        # teacher -> (class_name, subject) -> day -> list of slots
        #
        # Groups this teacher's matching canonical events by the
        # actual class_name + subject pair recorded on each event,
        # so the response can show exactly which class(es) the
        # workload comes from - e.g. two different lab groups
        # under the same class_name still show as two separate
        # entries, since their subject text differs (this mirrors
        # how the real data is structured; nothing here invents a
        # "section" concept beyond the class_name/subject fields
        # that are actually present on the canonical event).
        #
        # The event's own day is also part of the grouping key
        # (even when no day filter was requested) so that, for a
        # semester-wide query spanning multiple days, the SAME
        # class_name/subject combination taught on two different
        # days is never merged into one misleading slot list (a
        # slot number is only meaningful within a single day).
        class_breakdown = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )

        for event in self._events():

            teacher = self._teacher(event)

            if not teacher:
                continue

            class_name = (
                event.get("class_name")
                if isinstance(event, dict)
                else None
            )

            record_semester = (
                self.query_engine._semester_from_class_name(
                    class_name
                )
            )

            if record_semester != target_semester:
                continue

            event_day = self._event_day(event)

            if day_key:

                if event_day != day_key:
                    continue

            workload[teacher] += 1

            subject = (
                str(
                    event.get("subject", "")
                ).strip()
                if isinstance(event, dict)
                else ""
            )

            if subject:
                subjects[teacher].add(subject)

            class_label = str(class_name).strip() if class_name else ""

            slot = (
                event.get("slot")
                if isinstance(event, dict)
                else None
            )

            class_breakdown[teacher][
                (class_label, subject)
            ][event_day].append(slot)

        results = []

        for teacher, periods in workload.items():

            classes = []

            for (class_label, subject), by_day in sorted(
                class_breakdown[teacher].items(),
                key=lambda item: (item[0][0], item[0][1])
            ):

                # -------------------------------------------
                # Only attach a day label to each breakdown
                # row when this class_name/subject pair is
                # genuinely taught on more than one distinct
                # day within the current (unfiltered) result.
                # When a specific day was requested, or this
                # combination only ever occurs on one day
                # anyway, the day is left out entirely to
                # avoid repeating information the header
                # already states or that carries no extra
                # meaning.
                # -------------------------------------------

                show_day_label = (
                    not day_key and len(by_day) > 1
                )

                for event_day, slots in sorted(by_day.items()):

                    sorted_slots = sorted(
                        slot for slot in slots if slot is not None
                    )

                    classes.append({
                        "class_name": class_label,
                        "subject": subject,
                        "day": (
                            event_day if show_day_label else None
                        ),
                        "slots": sorted_slots,
                        "period_count": len(sorted_slots),
                    })

            results.append({
                "teacher": teacher,
                "periods": periods,
                "subjects": sorted(
                    subjects.get(teacher, [])
                ),
                "classes": classes,
            })

        results.sort(
            key=lambda x: (
                -x["periods"],
                x["teacher"].lower()
            )
        )

        return {
            "query_type": "semester_workload",
            "semester": target_semester,
            "day": day_key,
            "count": len(results),
            "results": results
        }

    # --------------------------------------------------
    # WEEKLY WORKLOAD
    # --------------------------------------------------

    def weekly_workload(self, teacher):

        teacher_key = str(
            teacher
        ).strip().lower()

        workload = defaultdict(int)
        events = []

        for event in self._events():

            event_teacher = self._teacher(event)

            if not event_teacher:
                continue

            if event_teacher.lower() != teacher_key:
                continue

            day = self._event_day(event)

            if not day:
                continue

            workload[day] += 1
            events.append(event)

        return {
            "query_type": "weekly_workload",
            "teacher": teacher,
            "total_periods": len(events),
            "by_day": dict(workload),
            "events": events
        }

    # --------------------------------------------------
    # LOWEST WORKLOAD FACULTY
    # --------------------------------------------------

    def lowest_workload(
        self,
        day,
        limit=10
    ):

        result = self.daily_workload(day)

        records = result["results"]

        records = sorted(
            records,
            key=lambda x: (
                x["periods"],
                x["teacher"].lower()
            )
        )

        return records[:limit]

    # --------------------------------------------------
    # HIGHEST WORKLOAD FACULTY
    # --------------------------------------------------

    def highest_workload(
        self,
        day,
        limit=10
    ):

        result = self.daily_workload(day)

        records = result["results"]

        records = sorted(
            records,
            key=lambda x: (
                -x["periods"],
                x["teacher"].lower()
            )
        )

        return records[:limit]

    # --------------------------------------------------
    # WORKLOAD SUMMARY
    # --------------------------------------------------

    def workload_summary(self, day):

        result = self.daily_workload(day)

        records = result["results"]

        if not records:
            return {
                "day": day,
                "faculty_count": 0,
                "total_periods": 0,
                "average_periods": 0,
                "minimum_periods": 0,
                "maximum_periods": 0
            }

        periods = [
            item["periods"]
            for item in records
        ]

        return {
            "day": result["day"],
            "faculty_count": len(records),
            "total_periods": sum(periods),
            "average_periods": round(
                sum(periods) / len(periods),
                2
            ),
            "minimum_periods": min(periods),
            "maximum_periods": max(periods)
        }
        # --------------------------------------------------
    # EXAM DUTY CANDIDATES
    # --------------------------------------------------

    def exam_duty_candidates(
        self,
        day,
        start_time,
        end_time
    ):

        day_key = self._normalize_day(day)

        if not day_key:
            return {
                "query_type": "exam_duty_candidates",
                "day": day,
                "start_time": start_time,
                "end_time": end_time,
                "count": 0,
                "results": []
            }

        # ----------------------------------------------
        # GET FACULTY WHO ARE FREE IN THE PERIOD
        # ----------------------------------------------

        free_result = (
            self.query_engine.faculty_free_for_period(
                day_key,
                start_time,
                end_time
            )
        )

        free_faculty = []

        if isinstance(free_result, dict):

            for item in free_result.get("results", []):

                if not isinstance(item, dict):
                    continue

                teacher = str(
                    item.get("teacher", "")
                ).strip()

                if teacher:
                    free_faculty.append(teacher)

        # Remove duplicate faculty names
        free_faculty = list(
            dict.fromkeys(free_faculty)
        )

        # ----------------------------------------------
        # GET DAILY WORKLOAD
        # ----------------------------------------------

        workload_result = self.daily_workload(day_key)

        workload_map = {}

        for item in workload_result.get(
            "results",
            []
        ):

            teacher = str(
                item.get("teacher", "")
            ).strip()

            if not teacher:
                continue

            workload_map[
                teacher.lower()
            ] = item.get(
                "periods",
                0
            )

        # ----------------------------------------------
        # BUILD CANDIDATE LIST
        # ----------------------------------------------

        candidates = []

        for teacher in free_faculty:

            periods = workload_map.get(
                teacher.lower(),
                0
            )

            # Lower workload = better candidate
            if periods <= 1:
                priority = "HIGH"
            elif periods == 2:
                priority = "HIGH"
            elif periods == 3:
                priority = "MEDIUM"
            elif periods == 4:
                priority = "LOW"
            else:
                priority = "VERY_LOW"

            candidates.append({
                "teacher": teacher,
                "daily_periods": periods,
                "priority": priority
            })

        # ----------------------------------------------
        # SORT BY LOWEST WORKLOAD
        # ----------------------------------------------

        candidates.sort(
            key=lambda x: (
                x["daily_periods"],
                x["teacher"].lower()
            )
        )

        return {
            "query_type": "exam_duty_candidates",
            "day": day_key,
            "start_time": start_time,
            "end_time": end_time,
            "count": len(candidates),
            "results": candidates
        }
          


    # --------------------------------------------------
    # AUTOMATIC EXAM DUTY ASSIGNMENT
    # --------------------------------------------------

    def assign_exam_duty(
        self,
        day,
        start_time,
        end_time,
        required_faculty
    ):

        try:
            required_faculty = int(required_faculty)

        except (TypeError, ValueError):

            return {
                "query_type": "assign_exam_duty",
                "success": False,
                "message": "Number of faculty must be an integer.",
                "results": []
            }

        if required_faculty <= 0:

            return {
                "query_type": "assign_exam_duty",
                "success": False,
                "message": "Number of faculty must be greater than 0.",
                "results": []
            }

        candidates = self.exam_duty_candidates(
            day,
            start_time,
            end_time
        )

        available = candidates.get(
            "results",
            []
        )

        if len(available) < required_faculty:

            return {
                "query_type": "assign_exam_duty",
                "success": False,
                "message": (
                    f"Only {len(available)} faculty members "
                    f"are available, but {required_faculty} "
                    f"were requested."
                ),
                "available_count": len(available),
                "required_count": required_faculty,
                "results": available
            }

        selected = available[:required_faculty]

        return {
            "query_type": "assign_exam_duty",
            "success": True,
            "day": candidates.get("day"),
            "start_time": candidates.get("start_time"),
            "end_time": candidates.get("end_time"),
            "required_count": required_faculty,
            "assigned_count": len(selected),
            "results": selected
        }