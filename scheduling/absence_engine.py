from collections import defaultdict
import re


class FacultyAbsenceEngine:

    def __init__(self, query_engine, workload_engine=None):
        self.query_engine = query_engine
        self.workload_engine = workload_engine

    def _events(self):
        try:
            return list(self.query_engine._events())
        except Exception:
            return []

    @staticmethod
    def _normalize_day(day):
        if not day:
            return None
        days = {
            "mon": "monday", "monday": "monday",
            "tue": "tuesday", "tues": "tuesday", "tuesday": "tuesday",
            "wed": "wednesday", "wednesday": "wednesday",
            "thu": "thursday", "thur": "thursday", "thurs": "thursday", "thursday": "thursday",
            "fri": "friday", "friday": "friday",
            "sat": "saturday", "saturday": "saturday",
            "sun": "sunday", "sunday": "sunday",
        }
        return days.get(str(day).strip().lower())

    @staticmethod
    def _text(value):
        return str(value or "").strip()

    @staticmethod
    def _slot_number(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            match = re.search(r"\b(\d+)\b", str(value or ""))
            return int(match.group(1)) if match else None

    @staticmethod
    def _time_range(value):
        if not value:
            return None
        text = str(value).strip().lower().replace(".", ":")
        match = re.search(
            r"(\d{1,2}):(\d{2})\s*(am|pm)?\s*(?:-|–|—|to)\s*"
            r"(\d{1,2}):(\d{2})\s*(am|pm)?", text
        )
        if not match:
            return None
        h1, m1, ap1, h2, m2, ap2 = match.groups()

        def minutes(hour, minute, ampm):
            hour, minute = int(hour), int(minute)
            if ampm == "am" and hour == 12:
                hour = 0
            elif ampm == "pm" and hour != 12:
                hour += 12
            return hour * 60 + minute

        start = minutes(h1, m1, ap1)
        end = minutes(h2, m2, ap2)
        return (start, end) if end > start else None

    def faculty_events(self, teacher, day=None):
        teacher_key = self._text(teacher).lower()
        day_key = self._normalize_day(day) if day else None
        results = []
        for event in self._events():
            if self._text(event.get("teacher")).lower() != teacher_key:
                continue
            if day_key and self._normalize_day(event.get("day")) != day_key:
                continue
            results.append(event)
        return results

    def absent_faculty_classes(self, teacher, day):
        day_key = self._normalize_day(day)
        if not day_key:
            return {"query_type": "absent_faculty_classes", "teacher": teacher,
                    "day": day, "count": 0, "classes": []}
        classes = []
        for event in self.faculty_events(teacher, day_key):
            classes.append({
                "teacher": event.get("teacher", ""),
                "day": event.get("day", ""),
                "slot": event.get("slot"),
                "slot_time": event.get("slot_time", ""),
                "subject": event.get("subject", ""),
                "class_name": event.get("class_name", ""),
                "group_name": event.get("group_name", ""),
                "type": event.get("type", ""),
                "room": event.get("room", "")
            })
        return {"query_type": "absent_faculty_classes", "teacher": teacher,
                "day": day_key, "count": len(classes), "classes": classes}

    def is_faculty_free(self, teacher, day, slot):
        teacher_key = self._text(teacher).lower()
        day_key = self._normalize_day(day)
        target_slot = self._slot_number(slot)
        for event in self._events():
            if (self._text(event.get("teacher")).lower() == teacher_key and
                    self._normalize_day(event.get("day")) == day_key and
                    self._slot_number(event.get("slot")) == target_slot):
                return False
        return True

    def is_faculty_free_for_block(self, teacher, day, block):
        return all(self.is_faculty_free(teacher, day, e.get("slot"))
                   for e in block["events"])

    def same_class_faculty(self, class_name, exclude_teacher=None):
        class_key = self._text(class_name).lower()
        exclude_key = self._text(exclude_teacher).lower()
        faculty = set()
        for event in self._events():
            if self._text(event.get("class_name")).lower() != class_key:
                continue
            teacher = self._text(event.get("teacher"))
            if teacher and teacher.lower() != exclude_key:
                faculty.add(teacher)
        return sorted(faculty, key=str.lower)

    def same_subject_faculty(self, subject, exclude_teacher=None):
        subject_key = self._text(subject).lower()
        exclude_key = self._text(exclude_teacher).lower()
        faculty = set()
        for event in self._events():
            if self._text(event.get("subject")).lower() != subject_key:
                continue
            teacher = self._text(event.get("teacher"))
            if teacher and teacher.lower() != exclude_key:
                faculty.add(teacher)
        return faculty

    def all_faculty(self, exclude_teacher=None):
        exclude_key = self._text(exclude_teacher).lower()
        faculty = set()
        for event in self._events():
            teacher = self._text(event.get("teacher"))
            if teacher and teacher.lower() != exclude_key:
                faculty.add(teacher)
        return sorted(faculty, key=str.lower)

    def _daily_workload_map(self, day):
        day_key = self._normalize_day(day)
        workload = defaultdict(int)
        for event in self._events():
            if self._normalize_day(event.get("day")) != day_key:
                continue
            teacher = self._text(event.get("teacher"))
            if teacher:
                workload[teacher.lower()] += 1
        return workload

    @classmethod
    def _block_key(cls, event):
        return (
            cls._text(event.get("class_name")).lower(),
            cls._text(event.get("subject")).lower(),
            cls._text(event.get("group_name")).lower(),
            cls._text(event.get("type")).lower(),
            cls._text(event.get("room")).lower(),
        )

    def _affected_blocks(self, teacher, day):
        events = []
        for event in self.faculty_events(teacher, day):
            tr = self._time_range(event.get("slot_time"))
            events.append({
                **event,
                "_slot": self._slot_number(event.get("slot")),
                "_start": tr[0] if tr else None,
                "_end": tr[1] if tr else None,
                "_key": self._block_key(event),
            })

        events.sort(key=lambda x: (
            x["_start"] is None,
            x["_start"] if x["_start"] is not None else 99999,
            x["_slot"] if x["_slot"] is not None else 99999,
        ))

        blocks = []
        for event in events:
            if not blocks:
                blocks.append([event])
                continue
            previous = blocks[-1][-1]
            same_identity = previous["_key"] == event["_key"]
            time_contiguous = (
                previous["_end"] is not None and event["_start"] is not None and
                previous["_end"] == event["_start"]
            )
            slot_contiguous = (
                previous["_slot"] is not None and event["_slot"] is not None and
                event["_slot"] == previous["_slot"] + 1
            )
            if same_identity and (time_contiguous or
                                  (previous["_start"] is None and event["_start"] is None and slot_contiguous)):
                blocks[-1].append(event)
            else:
                blocks.append([event])

        result = []
        for block_events in blocks:
            first = block_events[0]
            result.append({
                "class_name": first.get("class_name", ""),
                "subject": first.get("subject", ""),
                "group_name": first.get("group_name", ""),
                "type": first.get("type", ""),
                "room": first.get("room", ""),
                "slots": [e.get("slot") for e in block_events],
                "events": block_events,
                "period_count": len(block_events),
            })
        return result

    @classmethod
    def _block_time(cls, block):
        events = block.get("events", [])
        if not events:
            return ""
        first = cls._time_range(events[0].get("slot_time"))
        last = cls._time_range(events[-1].get("slot_time"))
        if first and last:
            def fmt(value):
                return f"{value // 60:02d}:{value % 60:02d}"
            return f"{fmt(first[0])} - {fmt(last[1])}"
        return " / ".join(str(e.get("slot_time", "")) for e in events)

       # --------------------------------------------------
    # FIND REPLACEMENT FACULTY
    # --------------------------------------------------

    def replacement_candidates(
        self,
        teacher,
        day
    ):

        day_key = self._normalize_day(day)

        if not day_key:
            return {
                "query_type": "replacement_candidates",
                "absent_teacher": teacher,
                "day": day,
                "count": 0,
                "block_count": 0,
                "blocks": [],
                "results": []
            }

        # --------------------------------------------------
        # FIND ACTUAL ABSENCE BLOCKS FROM TIMETABLE
        # --------------------------------------------------

        blocks = self._affected_blocks(
            teacher,
            day_key
        )

        # --------------------------------------------------
        # GET DAILY WORKLOAD OF ALL FACULTY
        # --------------------------------------------------

        workload = self._daily_workload_map(
            day_key
        )

        results = []

        # --------------------------------------------------
        # PROCESS EACH ABSENT CLASS / LAB BLOCK
        # --------------------------------------------------

        for block_index, block in enumerate(
            blocks,
            start=1
        ):

            # Faculty already teaching the same class
            class_faculty = {
                str(x).strip().lower()
                for x in self.same_class_faculty(
                    block["class_name"],
                    teacher
                )
            }

            # Faculty already teaching the same subject
            subject_faculty = {
                str(x).strip().lower()
                for x in self.same_subject_faculty(
                    block["subject"],
                    teacher
                )
            }

            candidates = []

            # --------------------------------------------------
            # CHECK ALL FACULTY
            # --------------------------------------------------

            for replacement in self.all_faculty(
                teacher
            ):

                replacement_key = (
                    str(replacement)
                    .strip()
                    .lower()
                )

                # --------------------------------------------------
                # MUST BE FREE FOR THE COMPLETE BLOCK
                # --------------------------------------------------

                if not self.is_faculty_free_for_block(
                    replacement,
                    day_key,
                    block
                ):
                    continue

                # --------------------------------------------------
                # DAILY WORKLOAD
                # --------------------------------------------------

                periods = workload.get(
                    replacement_key,
                    0
                )

                # --------------------------------------------------
                # CLASS / SUBJECT PREFERENCE
                # --------------------------------------------------

                same_class = (
                    replacement_key
                    in class_faculty
                )

                same_subject = (
                    replacement_key
                    in subject_faculty
                )

                # --------------------------------------------------
                # RANKING
                #
                # 1. Lowest workload
                # 2. Same class
                # 3. Same subject
                # 4. Alphabetical only as final tie-breaker
                # --------------------------------------------------

                score = (
                    periods,
                    0 if same_class else 1,
                    0 if same_subject else 1,
                    replacement_key
                )

                candidates.append({

                    "replacement_teacher":
                        replacement,

                    "daily_periods":
                        periods,

                    "same_class":
                        same_class,

                    "same_subject":
                        same_subject,

                    "complete_block":
                        True,

                    "block_index":
                        block_index,

                    "day":
                        day_key,

                    "slots":
                        block["slots"],

                    "slot_time":
                        self._block_time(block),

                    "period_count":
                        block["period_count"],

                    "subject":
                        block["subject"],

                    "class_name":
                        block["class_name"],

                    "group_name":
                        block["group_name"],

                    "type":
                        block["type"],

                    "room":
                        block["room"],

                    "_score":
                        score
                })

            # --------------------------------------------------
            # SORT BEST CANDIDATES
            # --------------------------------------------------

            candidates.sort(
                key=lambda x: x["_score"]
            )

            # --------------------------------------------------
            # ASSIGN RANK
            # --------------------------------------------------

            for rank, candidate in enumerate(
                candidates,
                start=1
            ):

                candidate["rank"] = rank

                candidate.pop(
                    "_score",
                    None
                )

                results.append(
                    candidate
                )

        # --------------------------------------------------
        # RETURN RESULT
        # --------------------------------------------------

        return {
            "query_type":
                "replacement_candidates",

            "absent_teacher":
                teacher,

            "day":
                day_key,

            "count":
                len(results),

            "block_count":
                len(blocks),

            "blocks": [

                {
                    "block_index": i,

                    "slots":
                        b["slots"],

                    "slot_time":
                        self._block_time(b),

                    "period_count":
                        b["period_count"],

                    "subject":
                        b["subject"],

                    "class_name":
                        b["class_name"],

                    "group_name":
                        b["group_name"],

                    "type":
                        b["type"],

                    "room":
                        b["room"]
                }

                for i, b in enumerate(
                    blocks,
                    start=1
                )
            ],

            "results":
                results
        }