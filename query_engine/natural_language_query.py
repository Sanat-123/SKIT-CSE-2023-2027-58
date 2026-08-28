"""
UNISCHED AI - NATURAL LANGUAGE QUERY

Natural-language query layer for QueryEngine.

This module:
    - extracts teacher, class, room, day, slot and time ranges
    - detects the query intent
    - calls QueryEngine
    - generates a readable answer

It does not read PDF/Excel/CSV files directly.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


class NaturalLanguageQuery:
    """Natural-language interface over QueryEngine."""

    def __init__(self, engine: Any):
        if engine is None:
            raise ValueError("NaturalLanguageQuery requires a QueryEngine.")

        self.engine = engine

    # =========================================================
    # BASIC HELPERS
    # =========================================================

    @staticmethod
    def normalize_text(value: Any) -> str:
        if value is None:
            return ""

        return " ".join(
            str(value)
            .replace("\xa0", " ")
            .strip()
            .split()
        )

    @classmethod
    def normalize_lower(cls, value: Any) -> str:
        return cls.normalize_text(value).casefold()

    @staticmethod
    def _unique(values: List[Any]) -> List[Any]:
        result = []
        seen = set()

        for value in values:
            text = str(value).strip()
            if not text:
                continue

            key = text.casefold()

            if key not in seen:
                seen.add(key)
                result.append(value)

        return result

    # =========================================================
    # RESULT HELPERS
    # =========================================================

    @staticmethod
    def result_to_list(result: Any) -> List[Dict[str, Any]]:
        if result is None:
            return []

        if isinstance(result, list):
            return result

        if isinstance(result, tuple):
            return list(result)

        if isinstance(result, dict):
            records = result.get("results")

            if isinstance(records, list):
                return records

            # A single actual record.
            if "teacher" in result or "class_name" in result or "room" in result:
                return [result]

            return []

        return []

    def call_engine_method(
        self,
        method_name: str,
        **kwargs: Any
    ) -> Any:
        method = getattr(self.engine, method_name, None)

        if method is None:
            raise AttributeError(
                f"QueryEngine has no method '{method_name}'."
            )

        # Try keyword arguments first.
        try:
            return method(**kwargs)
        except TypeError:
            # Compatibility with positional-only/older methods.
            if method_name == "faculty_status":
                return method(
                    kwargs.get("teacher"),
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "faculty_free_slots":
                return method(
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "class_free":
                return method(
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "room_free":
                return method(
                    kwargs.get("room"),
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "teacher_schedule":
                return method(
                    kwargs.get("teacher"),
                    kwargs.get("day")
                )

            if method_name == "class_schedule":
                return method(
                    kwargs.get("class_name"),
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "room_status":
                return method(
                    kwargs.get("room"),
                    kwargs.get("day"),
                    kwargs.get("slot")
                )

            if method_name == "subject_search":
                return method(kwargs.get("subject"))

            raise

    # =========================================================
    # DYNAMIC ENTITY VALUES
    # =========================================================

    def _events(self) -> List[Dict[str, Any]]:
        matcher = getattr(self.engine, "matcher", None)

        if matcher is None:
            matcher = getattr(self.engine, "_matcher", None)

        if matcher is None:
            return []

        events = getattr(matcher, "events", [])

        if isinstance(events, dict):
            events = list(events.values())

        if not isinstance(events, (list, tuple)):
            return []

        return [
            event for event in events
            if isinstance(event, dict)
        ]

    def _known_teachers(self) -> List[str]:
        values = []

        for event in self._events():
            for key in ("teacher", "faculty", "faculty_name", "teacher_name"):
                value = event.get(key)

                if value:
                    values.append(self.normalize_text(value))

        return sorted(
            self._unique(values),
            key=lambda x: len(str(x)),
            reverse=True
        )

    def _known_classes(self) -> List[str]:
        values = []

        for event in self._events():
            for key in (
                "class_name",
                "class",
                "section",
                "group"
            ):
                value = event.get(key)

                if value:
                    values.append(self.normalize_text(value))

        return sorted(
            self._unique(values),
            key=lambda x: len(str(x)),
            reverse=True
        )

    def _known_rooms(self) -> List[str]:
        values = []

        for event in self._events():
            for key in ("room", "room_name", "location"):
                value = event.get(key)

                if value:
                    values.append(self.normalize_text(value))

        return sorted(
            self._unique(values),
            key=lambda x: len(str(x)),
            reverse=True
        )

    # =========================================================
    # EXTRACT DAY
    # =========================================================

    def extract_day(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_lower(query)

        patterns = [
            r"\b(monday|mon)\b",
            r"\b(tuesday|tue|tues)\b",
            r"\b(wednesday|wed)\b",
            r"\b(thursday|thu|thur|thurs)\b",
            r"\b(friday|fri)\b",
            r"\b(saturday|sat)\b",
            r"\b(sunday|sun)\b",
        ]

        mapping = {
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

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)

            if match:
                return mapping[match.group(1).casefold()]

        return None

    # =========================================================
    # EXTRACT SLOT
    # =========================================================

    def extract_slot(
        self,
        query: str
    ) -> Optional[int]:

        text = self.normalize_lower(query)

        patterns = [
            r"\bslot\s*[:#-]?\s*(\d+)\b",
            r"\bperiod\s*[:#-]?\s*(\d+)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)

            if match:
                return int(match.group(1))

        return None

    # =========================================================
    # TIME NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_time(value: Any) -> Optional[str]:
        if value is None:
            return None

        text = str(value).strip().casefold()

        if not text:
            return None

        text = text.replace(".", ":")

        text = re.sub(r"\s+", " ", text).strip()

        match = re.fullmatch(
            r"(\d{1,2})(?::(\d{1,2}))?\s*(am|pm)?",
            text,
            re.IGNORECASE
        )

        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3)

        if minute > 59:
            return None

        if ampm:
            if hour < 1 or hour > 12:
                return None

            if ampm.casefold() == "am":
                if hour == 12:
                    hour = 0
            else:
                if hour != 12:
                    hour += 12
        else:
            if hour > 23:
                return None

        return f"{hour:02d}:{minute:02d}"

    # =========================================================
    # EXTRACT TIME RANGE
    # =========================================================

    def extract_time_range(
        self,
        query: str
    ) -> Optional[Tuple[str, str]]:

        text = self.normalize_text(query)

        # Examples:
        # 9:15 to 11:15
        # 9 AM to 11 AM
        # 9:30 AM to 11:15 AM
        # 9 to 11
        #
        # The AM/PM marker can occur on either side.

        time_pattern = (
            r"(\d{1,2}(?::\d{1,2})?(?:\s*(?:AM|PM))?)"
        )

        patterns = [
            rf"\bfrom\s+{time_pattern}\s*(?:to|-)\s*{time_pattern}\b",
            rf"\b{time_pattern}\s*(?:to|-)\s*{time_pattern}\b",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if not match:
                continue

            start_raw = match.group(1)
            end_raw = match.group(2)

            start = self._normalize_time(start_raw)
            end = self._normalize_time(end_raw)

            if not start or not end:
                continue

            # If AM/PM is present only on the ending time, infer it
            # for a simple numeric starting time.
            if (
                not re.search(r"(?:am|pm)", start_raw, re.IGNORECASE)
                and re.search(r"(?:am|pm)", end_raw, re.IGNORECASE)
            ):
                end_ampm = re.search(
                    r"(am|pm)",
                    end_raw,
                    re.IGNORECASE
                )

                if end_ampm:
                    start_with_ampm = (
                        start_raw + " " + end_ampm.group(1)
                    )
                    start = self._normalize_time(start_with_ampm)

            start_minutes = (
                int(start[:2]) * 60
                + int(start[3:])
            )

            end_minutes = (
                int(end[:2]) * 60
                + int(end[3:])
            )

            if end_minutes <= start_minutes:
                continue

            return start, end

        return None

    # =========================================================
    # EXTRACT TEACHER
    # =========================================================

    def extract_teacher(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        # First use the actual teacher names from canonical events.
        # Longest names are checked first.
        for teacher in self._known_teachers():
            if re.search(
                rf"(?<!\w){re.escape(teacher)}(?!\w)",
                text,
                re.IGNORECASE
            ):
                return teacher

        # Generic "Dr. Name", "Mr. Name", "Ms. Name" fallback.
        patterns = [
            r"\bDr\.?\s+[A-Za-z][A-Za-z .'-]*?(?=\s+(?:is|was|teaches|teaching|free|busy|available|on|at|from|in|for)\b|[?,.]|$)",
            r"\bMr\.?\s+[A-Za-z][A-Za-z .'-]*?(?=\s+(?:is|was|teaches|teaching|free|busy|available|on|at|from|in|for)\b|[?,.]|$)",
            r"\bMrs\.?\s+[A-Za-z][A-Za-z .'-]*?(?=\s+(?:is|was|teaches|teaching|free|busy|available|on|at|from|in|for)\b|[?,.]|$)",
            r"\bMs\.?\s+[A-Za-z][A-Za-z .'-]*?(?=\s+(?:is|was|teaches|teaching|free|busy|available|on|at|from|in|for)\b|[?,.]|$)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                return self.normalize_text(match.group(0))

        return None

    # =========================================================
    # EXTRACT ROOM
    # =========================================================

    def extract_room(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        patterns = [
            r"\broom\s*#\s*([A-Za-z0-9_.\-]+)",
            r"\broom\s+([A-Za-z0-9_.\-]+)",
            r"\bclassroom\s+([A-Za-z0-9_.\-]+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

        for room in self._known_rooms():
            if re.search(
                rf"(?<!\w){re.escape(room)}(?!\w)",
                text,
                re.IGNORECASE
            ):
                return room

        return None

    # =========================================================
    # EXTRACT CLASS
    # =========================================================

    def extract_class(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        # 1. Explicit class/section wording.
        patterns = [
            r"\bclass\s+([A-Za-z0-9_.\-]+)",
            r"\bsection\s+([A-Za-z0-9_.\-]+)",
            r"\bclass\s*[:#-]\s*([A-Za-z0-9_.\-]+)",
            r"\bsection\s*[:#-]\s*([A-Za-z0-9_.\-]+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                return match.group(1)

        # 2. IMPORTANT:
        # Support:
        #   timetable of 3CS-D
        #   schedule of 3CS-D
        #   timetable for 3CS-D
        #   schedule for 3CS-D
        for pattern in [
            r"\b(?:timetable|schedule|routine)\s+(?:of|for)\s+([A-Za-z0-9_.\-]+)",
            r"\b(?:of|for)\s+([A-Za-z0-9_.\-]+)\s+(?:timetable|schedule|routine)\b",
        ]:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                candidate = match.group(1)

                # Do not mistake "Monday", etc. for a class.
                if candidate.casefold() not in {
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                }:
                    return candidate

        # 3. Match against actual canonical class names.
        for class_name in self._known_classes():
            if re.search(
                rf"(?<!\w){re.escape(class_name)}(?!\w)",
                text,
                re.IGNORECASE
            ):
                return class_name

        # 4. Common timetable class-code pattern.
        match = re.search(
            r"\b\d+[A-Za-z]{1,5}(?:[-_.][A-Za-z0-9]+)?\b",
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(0)

        return None

    # =========================================================
    # EXTRACT SUBJECT
    # =========================================================

    def extract_subject(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        patterns = [
            r"\bwho\s+teaches\s+(.+?)(?:\?|$)",
            r"\bfaculty\s+teaching\s+(.+?)(?:\?|$)",
            r"\bteachers?\s+teaching\s+(.+?)(?:\?|$)",
            r"\bwho\s+is\s+teaching\s+(.+?)(?:\?|$)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:
                subject = match.group(1).strip()

                # Remove trailing day/time wording if present.
                subject = re.split(
                    r"\s+\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                    subject,
                    maxsplit=1,
                    flags=re.IGNORECASE
                )[0]

                return subject.strip(" ?.")

        return None

    # =========================================================
    # DETECT INTENT
    # =========================================================

    def detect_intent(
        self,
        query: str
    ) -> str:

        text = self.normalize_lower(query)

        teacher = self.extract_teacher(query)
        class_name = self.extract_class(query)

        has_free = bool(
            re.search(
                r"\b(free|available|vacant)\b",
                text
            )
        )

        has_busy = bool(
            re.search(
                r"\b(busy|occupied)\b",
                text
            )
        )

        has_schedule = bool(
            re.search(
                r"\b(schedule|timetable|routine)\b",
                text
            )
        )

        # -----------------------------------------------------
        # FACULTY STATUS
        # -----------------------------------------------------

        if teacher and (has_free or has_busy):
            return "faculty_status"

        # -----------------------------------------------------
        # ROOM FREE
        # -----------------------------------------------------

        if (
            re.search(r"\b(room|classroom)\b", text)
            and has_free
        ):
            return "room_free"

        # -----------------------------------------------------
        # CLASS FREE
        # -----------------------------------------------------

        if (
            class_name
            and has_free
        ):
            return "class_free"

        if (
            re.search(r"\b(class|section)\b", text)
            and has_free
        ):
            return "class_free"

        # -----------------------------------------------------
        # FACULTY FREE
        # -----------------------------------------------------

        if (
            re.search(
                r"\b(faculty|faculties|teacher|teachers|professor|professors)\b",
                text
            )
            and has_free
        ):
            return "faculty_free"

        # General "who/which faculty is free" query.
        if (
            re.search(r"\b(who|which)\b", text)
            and has_free
            and not re.search(r"\b(room|classroom)\b", text)
        ):
            return "faculty_free"

        # -----------------------------------------------------
        # TEACHER SCHEDULE
        # -----------------------------------------------------

        if teacher and (
            has_schedule
            or re.search(r"\b(teaching|teach)\b", text)
        ):
            return "teacher_schedule"

        # -----------------------------------------------------
        # SUBJECT SEARCH
        # -----------------------------------------------------

        if re.search(
            r"\bwho\s+teaches\b",
            text
        ):
            return "subject_search"

        if re.search(
            r"\b(faculty|teachers?)\s+teaching\b",
            text
        ):
            return "subject_search"

        # -----------------------------------------------------
        # CLASS SCHEDULE
        # -----------------------------------------------------

        if class_name and has_schedule:
            return "class_schedule"

        # -----------------------------------------------------
        # ROOM STATUS
        # -----------------------------------------------------

        if (
            re.search(r"\b(room|classroom)\b", text)
            and (
                has_schedule
                or has_busy
                or re.search(r"\bstatus\b", text)
            )
        ):
            return "room_status"

        return "unknown"

    # =========================================================
    # FACULTY STATUS
    # =========================================================

    def execute_faculty_status(
        self,
        teacher: Optional[str],
        day: Optional[str],
        slot: Optional[int],
        time_range: Optional[Tuple[str, str]] = None
    ) -> List[Dict[str, Any]]:

        if not teacher:
            return []

        if (
            time_range
            and day
            and hasattr(
                self.engine,
                "faculty_status_for_period"
            )
        ):
            start_time, end_time = time_range

            try:
                result = self.engine.faculty_status_for_period(
                    teacher,
                    day,
                    start_time,
                    end_time
                )

                if isinstance(result, dict):
                    return [result]

                return self.result_to_list(result)

            except Exception:
                pass

        result = self.call_engine_method(
            "faculty_status",
            teacher=teacher,
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # FACULTY FREE
    # =========================================================

    def execute_faculty_free(
        self,
        day: Optional[str],
        slot: Optional[int],
        time_range: Optional[Tuple[str, str]] = None
    ) -> List[Dict[str, Any]]:

        if (
            time_range
            and day
            and hasattr(
                self.engine,
                "faculty_free_for_period"
            )
        ):
            start_time, end_time = time_range

            try:
                result = self.engine.faculty_free_for_period(
                    day,
                    start_time,
                    end_time
                )

                return self.result_to_list(result)

            except Exception:
                pass

        result = self.call_engine_method(
            "faculty_free_slots",
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # CLASS FREE
    # =========================================================

    def execute_class_free(
        self,
        day: Optional[str],
        slot: Optional[int]
    ) -> List[Dict[str, Any]]:

        result = self.call_engine_method(
            "class_free",
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # ROOM FREE
    # =========================================================

    def execute_room_free(
        self,
        room: Optional[str],
        day: Optional[str],
        slot: Optional[int]
    ) -> List[Dict[str, Any]]:

        # QueryEngine exposes room_free_slots(), not room_free().
        result = self.call_engine_method(
            "room_free_slots",
            room=room,
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # TEACHER SCHEDULE
    # =========================================================

    def execute_teacher_schedule(
        self,
        teacher: Optional[str],
        day: Optional[str]
    ) -> List[Dict[str, Any]]:

        if not teacher:
            return []

        result = self.call_engine_method(
            "teacher_schedule",
            teacher=teacher,
            day=day
        )

        return self.result_to_list(result)

    # =========================================================
    # CLASS SCHEDULE
    # =========================================================

    def execute_class_schedule(
        self,
        class_name: Optional[str],
        day: Optional[str],
        slot: Optional[int] = None
    ) -> List[Dict[str, Any]]:

        if not class_name:
            return []

        # QueryEngine.class_schedule supports day and slot.
        result = self.call_engine_method(
            "class_schedule",
            class_name=class_name,
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # ROOM STATUS
    # =========================================================

    def execute_room_status(
        self,
        room: Optional[str],
        day: Optional[str],
        slot: Optional[int]
    ) -> List[Dict[str, Any]]:

        result = self.call_engine_method(
            "room_status",
            room=room,
            day=day,
            slot=slot
        )

        return self.result_to_list(result)

    # =========================================================
    # SUBJECT SEARCH
    # =========================================================

    def execute_subject_search(
        self,
        subject: Optional[str]
    ) -> List[Dict[str, Any]]:

        if not subject:
            return []

        result = self.call_engine_method(
            "subject_search",
            subject=subject
        )

        return self.result_to_list(result)

    # =========================================================
    # EXECUTE QUERY
    # =========================================================

    def execute(
        self,
        query: str
    ) -> Dict[str, Any]:

        intent = self.detect_intent(query)

        teacher = self.extract_teacher(query)
        day = self.extract_day(query)
        slot = self.extract_slot(query)
        time_range = self.extract_time_range(query)

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        if intent == "unknown":
            return {
                "intent": "unknown",
                "success": False,
                "count": 0,
                "results": [],
                "teacher": teacher,
                "day": day,
                "slot": slot,
                "time_range": time_range,
                "message": (
                    "I could not understand the query. "
                    "Try asking about faculty, classes, "
                    "rooms, subjects, schedules, or free slots."
                )
            }

        # -----------------------------------------------------
        # FACULTY STATUS
        # -----------------------------------------------------

        if intent == "faculty_status":
            records = self.execute_faculty_status(
                teacher,
                day,
                slot,
                time_range
            )

            return {
                "intent": intent,
                "success": bool(records),
                "count": len(records),
                "results": records,
                "teacher": teacher,
                "day": day,
                "slot": slot,
                "time_range": time_range
            }

        # -----------------------------------------------------
        # FACULTY FREE
        # -----------------------------------------------------

        if intent == "faculty_free":
            records = self.execute_faculty_free(
                day,
                slot,
                time_range
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "day": day,
                "slot": slot,
                "time_range": time_range
            }

        # -----------------------------------------------------
        # CLASS FREE
        # -----------------------------------------------------

        if intent == "class_free":
            records = self.execute_class_free(
                day,
                slot
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "day": day,
                "slot": slot
            }

        # -----------------------------------------------------
        # ROOM FREE
        # -----------------------------------------------------

        if intent == "room_free":
            room = self.extract_room(query)

            records = self.execute_room_free(
                room,
                day,
                slot
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "room": room,
                "day": day,
                "slot": slot
            }

        # -----------------------------------------------------
        # TEACHER SCHEDULE
        # -----------------------------------------------------

        if intent == "teacher_schedule":
            records = self.execute_teacher_schedule(
                teacher,
                day
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "teacher": teacher,
                "day": day
            }

        # -----------------------------------------------------
        # CLASS SCHEDULE
        # -----------------------------------------------------

        if intent == "class_schedule":
            class_name = self.extract_class(query)

            records = self.execute_class_schedule(
                class_name,
                day,
                slot
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "class_name": class_name,
                "day": day,
                "slot": slot
            }

        # -----------------------------------------------------
        # ROOM STATUS
        # -----------------------------------------------------

        if intent == "room_status":
            room = self.extract_room(query)

            records = self.execute_room_status(
                room,
                day,
                slot
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "room": room,
                "day": day,
                "slot": slot
            }

        # -----------------------------------------------------
        # SUBJECT SEARCH
        # -----------------------------------------------------

        if intent == "subject_search":
            subject = self.extract_subject(query)

            records = self.execute_subject_search(
                subject
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "subject": subject
            }

        return {
            "intent": intent,
            "success": False,
            "count": 0,
            "results": [],
            "message": "No handler available for this query."
        }

    # =========================================================
    # ANSWER
    # =========================================================

    def answer(
        self,
        query: str
    ) -> str:

        result = self.execute(query)

        intent = result.get("intent")

        if intent == "unknown":
            return result.get(
                "message",
                "I could not understand the query."
            )

        # -----------------------------------------------------
        # FACULTY STATUS
        # -----------------------------------------------------

        if intent == "faculty_status":
            teacher = result.get("teacher")
            day = result.get("day")
            slot = result.get("slot")
            time_range = result.get("time_range")
            records = result.get("results", [])

            if not records:
                return (
                    f"No faculty status information found for "
                    f"{teacher}"
                    f"{' on ' + day if day else ''}."
                )

            data = records[0]

            if not isinstance(data, dict):
                return f"Status information found for {teacher}."

            status = str(
                data.get("status", "")
            ).casefold()

            query_lower = self.normalize_lower(query)

            asked_busy = (
                "busy" in query_lower
                or "occupied" in query_lower
            )

            asked_free = (
                "free" in query_lower
                or "available" in query_lower
            )

            # Time-range answer.
            if time_range:
                start_time, end_time = time_range

                if status == "free":
                    slots = data.get("slots", [])

                    if asked_busy:
                        return (
                            f"No, {teacher} is not busy on {day} "
                            f"from {start_time} to {end_time}. "
                            f"{teacher} is free during this period."
                        )

                    return (
                        f"Yes, {teacher} is free on {day} "
                        f"from {start_time} to {end_time}. "
                        f"Free slots: {slots}."
                    )

                if status == "busy":
                    if asked_free:
                        return (
                            f"No, {teacher} is not free on {day} "
                            f"from {start_time} to {end_time}. "
                            f"{teacher} is busy during this period."
                        )

                    return (
                        f"Yes, {teacher} is busy on {day} "
                        f"from {start_time} to {end_time}."
                    )

                return (
                    f"The status of {teacher} is unknown for {day} "
                    f"from {start_time} to {end_time}."
                )

            # Normal slot answer.
            slot_text = (
                f" in slot {slot}"
                if slot is not None
                else ""
            )

            if status == "free":
                if asked_busy:
                    return (
                        f"No, {teacher} is not busy on {day}"
                        f"{slot_text}. {teacher} is free."
                    )

                return (
                    f"Yes, {teacher} is free on {day}"
                    f"{slot_text}."
                )

            if status == "busy":
                if asked_free:
                    return (
                        f"No, {teacher} is not free on {day}"
                        f"{slot_text}. {teacher} is busy."
                    )

                return (
                    f"Yes, {teacher} is busy on {day}"
                    f"{slot_text}."
                )

            return f"Status of {teacher} could not be determined."

        # -----------------------------------------------------
        # FACULTY FREE
        # -----------------------------------------------------

        if intent == "faculty_free":
            records = result.get("results", [])
            day = result.get("day")
            time_range = result.get("time_range")

            if not records:
                return (
                    "No free faculty found"
                    f"{' on ' + day if day else ''}."
                )

            names = []

            for record in records:
                if not isinstance(record, dict):
                    continue

                teacher = record.get("teacher")

                if teacher:
                    names.append(str(teacher))

            names = self._unique(names)

            if names:
                if time_range:
                    return (
                        f"Free faculty on {day} from "
                        f"{time_range[0]} to {time_range[1]}: "
                        + ", ".join(names)
                    )

                return "Free faculty: " + ", ".join(names)

            return f"{len(records)} free faculty records found."

        # -----------------------------------------------------
        # CLASS FREE
        # -----------------------------------------------------

        if intent == "class_free":
            records = result.get("results", [])

            if not records:
                return "No free classes found."

            classes = []

            for record in records:
                if not isinstance(record, dict):
                    continue

                value = (
                    record.get("class_name")
                    or record.get("class")
                )

                if value:
                    classes.append(str(value))

            classes = self._unique(classes)

            if classes:
                return "Free classes: " + ", ".join(classes)

            return f"{len(records)} free class records found."

        # -----------------------------------------------------
        # ROOM FREE
        # -----------------------------------------------------

        if intent == "room_free":
            records = result.get("results", [])

            if not records:
                return "No free rooms found."

            rooms = []

            for record in records:
                if not isinstance(record, dict):
                    continue

                room = record.get("room")

                if room:
                    rooms.append(str(room))

            rooms = self._unique(rooms)

            if rooms:
                return "Free rooms: " + ", ".join(rooms)

            return f"{len(records)} free room records found."

        # -----------------------------------------------------
        # TEACHER SCHEDULE
        # -----------------------------------------------------

        if intent == "teacher_schedule":
            teacher = result.get("teacher")
            records = result.get("results", [])

            if not records:
                return f"No schedule found for {teacher}."

            return (
                f"{len(records)} schedule records found "
                f"for {teacher}."
            )

        # -----------------------------------------------------
        # CLASS SCHEDULE
        # -----------------------------------------------------

        if intent == "class_schedule":
            class_name = result.get("class_name")
            records = result.get("results", [])

            if not records:
                return (
                    f"No schedule found for {class_name}."
                )

            return (
                f"{len(records)} schedule records found "
                f"for {class_name}."
            )

        # -----------------------------------------------------
        # ROOM STATUS
        # -----------------------------------------------------

        if intent == "room_status":
            room = result.get("room")
            records = result.get("results", [])

            if not records:
                return (
                    f"No status information found "
                    f"for room {room}."
                )

            return (
                f"Status information found for room {room}."
            )

        # -----------------------------------------------------
        # SUBJECT SEARCH
        # -----------------------------------------------------

        if intent == "subject_search":
            subject = result.get("subject")
            records = result.get("results", [])

            if not records:
                return (
                    f"No faculty found teaching {subject}."
                )

            teachers = []

            for record in records:
                if not isinstance(record, dict):
                    continue

                teacher = record.get("teacher")

                if teacher:
                    teachers.append(str(teacher))

            teachers = self._unique(teachers)

            if teachers:
                return (
                    f"Faculty teaching {subject}: "
                    + ", ".join(teachers)
                )

            return f"{len(records)} records found."

        return "Query processed successfully."


__all__ = ["NaturalLanguageQuery"]
