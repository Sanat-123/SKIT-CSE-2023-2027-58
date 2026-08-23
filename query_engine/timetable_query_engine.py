"""
UniSched AI - Timetable Query Engine

Converts natural-language timetable questions into
FastTimetableIndex queries.

This layer does NOT parse PDFs/Excel/CSV.
It works on the already-built FastTimetableIndex.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class TimetableQueryEngine:
    """
    Natural-language query layer over FastTimetableIndex.
    """

    DAY_ALIASES = {
        "mon": "monday",
        "monday": "monday",

        "tue": "tuesday",
        "tues": "tuesday",
        "tuesday": "tuesday",

        "wed": "wednesday",
        "weds": "wednesday",
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

    def __init__(self, index):
        self.index = index

    # ------------------------------------------------------------------
    # BASIC HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _clean(text: Any) -> str:
        if text is None:
            return ""

        return " ".join(
            str(text).strip().split()
        )

    @classmethod
    def _normalize_day(cls, value: str) -> str:
        text = cls._clean(value).casefold()

        return cls.DAY_ALIASES.get(
            text,
            text,
        )

    @staticmethod
    def _extract_slot(query: str) -> Optional[int]:
        """
        Detect:

            slot 1
            slot-1
            period 1
            period-1
            p1
        """

        match = re.search(
            r"\b(?:slot|period|p)\s*[-:#]?\s*(\d+)\b",
            query,
            flags=re.IGNORECASE,
        )

        if match:
            return int(match.group(1))

        return None

    @classmethod
    def _extract_day(cls, query: str) -> Optional[str]:

        text = query.casefold()

        # Longest first avoids accidental partial matches.
        days = sorted(
            cls.DAY_ALIASES.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        )

        for alias, day in days:

            if re.search(
                rf"\b{re.escape(alias)}\b",
                text,
            ):
                return day

        return None

    def _find_teacher(
        self,
        query: str,
    ) -> Optional[str]:

        query_key = query.casefold()

        for teacher in self.index.teachers:

            if teacher.casefold() in query_key:
                return teacher

        # Try individual name components.
        for teacher in self.index.teachers:

            parts = teacher.split()

            meaningful_parts = [
                p.casefold().strip(".")
                for p in parts
                if len(p.strip(".")) >= 3
            ]

            if meaningful_parts:

                if all(
                    p in query_key
                    for p in meaningful_parts[-2:]
                ):
                    return teacher

        return None

    def _find_class(
        self,
        query: str,
    ) -> Optional[str]:

        query_key = query.casefold()

        for class_name in self.index.classes:

            if class_name.casefold() in query_key:
                return class_name

        return None

    def _find_room(
        self,
        query: str,
    ) -> Optional[str]:

        query_key = query.casefold()

        for room in self.index.rooms:

            if room.casefold() in query_key:
                return room

        return None

    def _find_subject(
        self,
        query: str,
    ) -> Optional[str]:

        query_key = query.casefold()

        # Prefer longest subject names.
        subjects = sorted(
            self.index.subjects,
            key=lambda x: len(x),
            reverse=True,
        )

        for subject in subjects:

            if subject.casefold() in query_key:
                return subject

        return None

    # ------------------------------------------------------------------
    # INTENT DETECTION
    # ------------------------------------------------------------------

    @staticmethod
    def _intent(query: str) -> str:

        text = query.casefold()

        # Free faculty
        if (
            "free faculty" in text
            or "faculty free" in text
            or "teachers free" in text
            or "teacher free" in text
            or "who is free" in text
            or "who are free" in text
        ):
            return "free_faculty"

        # Free classrooms
        if (
            "free room" in text
            or "free rooms" in text
            or "available room" in text
            or "available rooms" in text
            or "classroom free" in text
        ):
            return "free_rooms"

        # Free classes
        if (
            "free class" in text
            or "available class" in text
            or "which class is free" in text
        ):
            return "free_classes"

        # Teacher schedule
        if (
            "teacher schedule" in text
            or "faculty schedule" in text
            or "timetable of" in text
            or "schedule of" in text
        ):
            return "teacher_schedule"

        # Class schedule
        if (
            "class schedule" in text
            or "class timetable" in text
            or "timetable for class" in text
            or "schedule for class" in text
        ):
            return "class_schedule"

        # Room schedule
        if (
            "room schedule" in text
            or "room timetable" in text
            or "what is in room" in text
            or "what's in room" in text
        ):
            return "room_schedule"

        # Day + slot events
        if (
            "what is scheduled" in text
            or "what's scheduled" in text
            or "what is happening" in text
            or "classes in" in text
            or "events in" in text
        ):
            return "events_at"

        # Subject search
        if (
            "who teaches" in text
            or "who is teaching" in text
            or "find subject" in text
            or "search subject" in text
            or "subject" in text
        ):
            return "subject_search"

        # Direct teacher mention
        if self._contains_any_name(query, self.index.teachers):
            return "teacher_schedule"

        # Direct class mention
        if self._contains_any_name(query, self.index.classes):
            return "class_schedule"

        # Direct room mention
        if self._contains_any_name(query, self.index.rooms):
            return "room_schedule"

        return "unknown"

    @staticmethod
    def _contains_any_name(
        query: str,
        names,
    ) -> bool:

        text = query.casefold()

        return any(
            name.casefold() in text
            for name in names
        )

    # ------------------------------------------------------------------
    # QUERY EXECUTION
    # ------------------------------------------------------------------

    def query(
        self,
        user_query: str,
    ) -> Dict[str, Any]:

        query = self._clean(user_query)

        if not query:

            return {
                "success": False,
                "intent": "unknown",
                "message": "Please enter a timetable question.",
                "results": [],
            }

        intent = self._intent(query)

        day = self._extract_day(query)
        slot = self._extract_slot(query)

        # --------------------------------------------------------------
        # FREE FACULTY
        # --------------------------------------------------------------

        if intent == "free_faculty":

            if not day or slot is None:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "Please specify both day and slot. "
                        "Example: Who is free on Monday slot 2?"
                    ),
                    "results": [],
                }

            teacher = self._find_teacher(query)

            results = self.index.free_faculty(
                day,
                slot,
                teacher,
            )

            return {
                "success": True,
                "intent": intent,
                "day": day,
                "slot": slot,
                "results": results,
                "message": (
                    f"{len(results)} faculty member(s) "
                    f"are free on {day.title()}, slot {slot}."
                ),
            }

        # --------------------------------------------------------------
        # FREE ROOMS
        # --------------------------------------------------------------

        if intent == "free_rooms":

            if not day or slot is None:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "Please specify both day and slot. "
                        "Example: Which rooms are free on Monday slot 2?"
                    ),
                    "results": [],
                }

            results = self.index.free_rooms(
                day,
                slot,
            )

            return {
                "success": True,
                "intent": intent,
                "day": day,
                "slot": slot,
                "results": results,
                "message": (
                    f"{len(results)} room(s) are free "
                    f"on {day.title()}, slot {slot}."
                ),
            }

        # --------------------------------------------------------------
        # FREE CLASSES
        # --------------------------------------------------------------

        if intent == "free_classes":

            if not day or slot is None:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "Please specify both day and slot."
                    ),
                    "results": [],
                }

            results = self.index.free_classes(
                day,
                slot,
            )

            return {
                "success": True,
                "intent": intent,
                "day": day,
                "slot": slot,
                "results": results,
                "message": (
                    f"{len(results)} class(es) are free "
                    f"on {day.title()}, slot {slot}."
                ),
            }

        # --------------------------------------------------------------
        # TEACHER SCHEDULE
        # --------------------------------------------------------------

        if intent == "teacher_schedule":

            teacher = self._find_teacher(query)

            if not teacher:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "I could not identify the faculty member. "
                        "Please provide the teacher's name."
                    ),
                    "results": [],
                }

            results = self.index.teacher_schedule(
                teacher,
                day,
            )

            return {
                "success": True,
                "intent": intent,
                "teacher": teacher,
                "day": day,
                "results": results,
                "message": (
                    f"Found {len(results)} timetable event(s) "
                    f"for {teacher}."
                ),
            }

        # --------------------------------------------------------------
        # CLASS SCHEDULE
        # --------------------------------------------------------------

        if intent == "class_schedule":

            class_name = self._find_class(query)

            if not class_name:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "I could not identify the class. "
                        "Example: Show timetable for 3CS-A."
                    ),
                    "results": [],
                }

            results = self.index.class_schedule(
                class_name,
                day,
            )

            return {
                "success": True,
                "intent": intent,
                "class_name": class_name,
                "day": day,
                "results": results,
                "message": (
                    f"Found {len(results)} timetable event(s) "
                    f"for {class_name}."
                ),
            }

        # --------------------------------------------------------------
        # ROOM SCHEDULE
        # --------------------------------------------------------------

        if intent == "room_schedule":

            room = self._find_room(query)

            if not room:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "I could not identify the room."
                    ),
                    "results": [],
                }

            results = self.index.room_schedule(
                room,
                day,
            )

            return {
                "success": True,
                "intent": intent,
                "room": room,
                "day": day,
                "results": results,
                "message": (
                    f"Found {len(results)} event(s) "
                    f"for room {room}."
                ),
            }

        # --------------------------------------------------------------
        # EVENTS AT DAY + SLOT
        # --------------------------------------------------------------

        if intent == "events_at":

            if not day or slot is None:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "Please specify both day and slot. "
                        "Example: What is scheduled on Monday slot 2?"
                    ),
                    "results": [],
                }

            results = self.index.events_at(
                day,
                slot,
            )

            return {
                "success": True,
                "intent": intent,
                "day": day,
                "slot": slot,
                "results": results,
                "message": (
                    f"Found {len(results)} event(s) "
                    f"on {day.title()}, slot {slot}."
                ),
            }

        # --------------------------------------------------------------
        # SUBJECT SEARCH
        # --------------------------------------------------------------

        if intent == "subject_search":

            subject = self._find_subject(query)

            if not subject:

                return {
                    "success": False,
                    "intent": intent,
                    "message": (
                        "I could not identify the subject. "
                        "Please provide the subject name."
                    ),
                    "results": [],
                }

            results = self.index.subject_search(
                subject,
            )

            return {
                "success": True,
                "intent": intent,
                "subject": subject,
                "results": results,
                "message": (
                    f"Found {len(results)} event(s) "
                    f"for {subject}."
                ),
            }

        # --------------------------------------------------------------
        # UNKNOWN
        # --------------------------------------------------------------

        return {
            "success": False,
            "intent": "unknown",
            "message": (
                "I could not understand that timetable query.\n\n"
                "Try one of these:\n"
                "• Who is free on Monday slot 2?\n"
                "• Show Dr. Mehul Mahrishi's schedule.\n"
                "• Who teaches Operating Systems?\n"
                "• Show timetable for 3CS-A.\n"
                "• What is scheduled in room 301 on Monday?\n"
                "• Which rooms are free on Monday slot 3?"
            ),
            "results": [],
        }


# ----------------------------------------------------------------------
# HUMAN-READABLE FORMATTER
# ----------------------------------------------------------------------

def format_results(response: Dict[str, Any]) -> str:
    """
    Convert query-engine response into chatbot-friendly text.
    """

    if not response.get("success"):

        return response.get(
            "message",
            "Unable to process the query.",
        )

    results = response.get(
        "results",
        [],
    )

    lines = [
        response.get(
            "message",
            "Results:",
        ),
        "",
    ]

    if not results:

        lines.append("No matching records found.")

        return "\n".join(lines)

    for i, item in enumerate(
        results,
        start=1,
    ):

        teacher = item.get(
            "teacher",
            "",
        )

        day = item.get(
            "day",
            "",
        )

        slot = item.get(
            "slot",
            "",
        )

        slot_time = item.get(
            "slot_time",
            "",
        )

        subject = item.get(
            "subject",
            "",
        )

        room = item.get(
            "room",
            "",
        )

        class_name = item.get(
            "class_name",
            "",
        )

        parts = []

        if teacher:
            parts.append(
                f"Teacher: {teacher}"
            )

        if day:
            parts.append(
                f"Day: {day.title()}"
            )

        if slot is not None and slot != "":
            parts.append(
                f"Slot: {slot}"
            )

        if slot_time:
            parts.append(
                f"Time: {slot_time}"
            )

        if subject:
            parts.append(
                f"Subject: {subject}"
            )

        if room:
            parts.append(
                f"Room: {room}"
            )

        if class_name:
            parts.append(
                f"Class: {class_name}"
            )

        if not parts:
            parts.append(
                str(item)
            )

        lines.append(
            f"{i}. " + " | ".join(parts)
        )

    return "\n".join(lines)