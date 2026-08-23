


"""Fast indexed timetable query layer for UniSched AI.

Build the indexes once after timetable parsing/canonical matching.
Queries then use dictionary/set lookups instead of scanning every event.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import re


class FastTimetableIndex:
    """Hash-based indexes over canonical timetable events."""

    def __init__(self, events: Optional[Iterable[Dict[str, Any]]] = None):
        self.clear()
        if events:
            self.build(events)

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).replace("\xa0", " ").strip().split())

    @classmethod
    def _key_text(cls, value: Any) -> str:
        return cls._text(value).casefold()

    @staticmethod
    def _day(value: Any) -> str:
        text = " ".join(str(value or "").strip().split()).casefold()
        return {
            "mo": "monday", "mon": "monday", "monday": "monday",
            "tu": "tuesday", "tue": "tuesday", "tues": "tuesday", "tuesday": "tuesday",
            "we": "wednesday", "wed": "wednesday", "weds": "wednesday", "wednesday": "wednesday",
            "th": "thursday", "thu": "thursday", "thur": "thursday",
            "thurs": "thursday", "thursday": "thursday",
            "fr": "friday", "fri": "friday", "friday": "friday",
            "sa": "saturday", "sat": "saturday", "saturday": "saturday",
            "su": "sunday", "sun": "sunday", "sunday": "sunday",
        }.get(text, text)

    @staticmethod
    def _slot(value: Any) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            pass

        text = str(value).strip()
        match = re.search(
            r"(?:slot|period|p)\s*[-:_]?\s*(\d+)",
            text,
            re.IGNORECASE,
        )
        if match:
            return int(match.group(1))

        match = re.fullmatch(r"(\d+)(?:\.0+)?", text)
        return int(match.group(1)) if match else None

    def clear(self) -> None:
        self.events: List[Dict[str, Any]] = []

        self.by_day_slot: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
        self.by_teacher: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.by_teacher_day: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        self.by_subject: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.by_class: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.by_room: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        self.busy_teachers: Dict[Tuple[str, int], Set[str]] = defaultdict(set)
        self.busy_classes: Dict[Tuple[str, int], Set[str]] = defaultdict(set)
        self.busy_rooms: Dict[Tuple[str, int], Set[str]] = defaultdict(set)

        self.teachers: Set[str] = set()
        self.classes: Set[str] = set()
        self.rooms: Set[str] = set()
        self.subjects: Set[str] = set()

    @staticmethod
    def _event_key(event: Dict[str, Any]) -> Tuple[str, ...]:
        def norm(value: Any) -> str:
            return " ".join(str(value or "").strip().split()).casefold()

        return (
            norm(event.get("day")),
            str(event.get("slot") or ""),
            norm(event.get("slot_time")),
            norm(event.get("teacher")),
            norm(event.get("subject")),
            norm(event.get("room")),
            norm(event.get("class_name", event.get("class"))),
            norm(event.get("group_name")),
        )

    def build(self, events: Iterable[Dict[str, Any]]) -> None:
        self.clear()
        seen: Set[Tuple[str, ...]] = set()

        for original in events:
            if not isinstance(original, dict):
                continue

            event = dict(original)
            day = self._day(event.get("day"))
            slot = self._slot(event.get("slot"))
            event["day"] = day
            event["slot"] = slot

            key = self._event_key(event)
            if key in seen:
                continue
            seen.add(key)

            self.events.append(event)

            teacher = self._key_text(event.get("teacher"))
            subject = self._key_text(event.get("subject"))
            class_name = self._key_text(
                event.get("class_name", event.get("class"))
            )
            room = self._key_text(event.get("room"))

            teacher_display = self._text(event.get("teacher"))
            class_display = self._text(
                event.get("class_name", event.get("class"))
            )
            room_display = self._text(event.get("room"))

            if teacher:
                self.teachers.add(teacher_display)
                self.by_teacher[teacher].append(event)

            if subject:
                self.subjects.add(self._text(event.get("subject")))
                self.by_subject[subject].append(event)

            if class_name:
                self.classes.add(class_display)
                self.by_class[class_name].append(event)

            if room:
                self.rooms.add(room_display)
                self.by_room[room].append(event)

            if day and slot is not None:
                pair = (day, slot)
                self.by_day_slot[pair].append(event)

                if teacher:
                    self.busy_teachers[pair].add(teacher)

                if class_name:
                    self.busy_classes[pair].add(class_name)

                if room:
                    self.busy_rooms[pair].add(room)

                if teacher:
                    self.by_teacher_day[(teacher, day)].append(event)

    def summary(self) -> Dict[str, int]:
        return {
            "events": len(self.events),
            "teachers": len(self.teachers),
            "subjects": len(self.subjects),
            "classes": len(self.classes),
            "rooms": len(self.rooms),
            "day_slot_keys": len(self.by_day_slot),
        }

    def events_at(self, day: str, slot: int) -> List[Dict[str, Any]]:
        return list(self.by_day_slot.get((self._day(day), int(slot)), []))

    def teacher_schedule(
        self, teacher: str, day: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        key = self._key_text(teacher)
        if day:
            return list(self.by_teacher_day.get((key, self._day(day)), []))
        return list(self.by_teacher.get(key, []))

    def subject_search(self, subject: str) -> List[Dict[str, Any]]:
        query = self._key_text(subject)
        if not query:
            return []

        exact = self.by_subject.get(query)
        if exact:
            return list(exact)

        results: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, ...]] = set()

        for key, events in self.by_subject.items():
            if query in key:
                for event in events:
                    ek = self._event_key(event)
                    if ek not in seen:
                        seen.add(ek)
                        results.append(event)

        return results

    def class_schedule(
        self, class_name: str, day: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        key = self._key_text(class_name)
        events = self.by_class.get(key, [])

        if day:
            wanted = self._day(day)
            return [e for e in events if e.get("day") == wanted]

        return list(events)

    def room_schedule(
        self, room: str, day: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        key = self._key_text(room)
        events = self.by_room.get(key, [])

        if day:
            wanted = self._day(day)
            return [e for e in events if e.get("day") == wanted]

        return list(events)

    def free_faculty(
        self, day: str, slot: int, teacher: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return free faculty using set-based availability lookup."""
        pair = (self._day(day), int(slot))
        busy = self.busy_teachers.get(pair, set())

        if teacher:
            teacher_key = self._key_text(teacher)
            if teacher_key in busy:
                return []
            return [{
                "teacher": self._text(teacher),
                "day": pair[0],
                "slot": pair[1],
            }]

        return [
            {"teacher": name, "day": pair[0], "slot": pair[1]}
            for name in sorted(self.teachers, key=str.casefold)
            if self._key_text(name) not in busy
        ]

    def free_classes(self, day: str, slot: int) -> List[Dict[str, Any]]:
        pair = (self._day(day), int(slot))
        busy = self.busy_classes.get(pair, set())

        return [
            {"class_name": name, "day": pair[0], "slot": pair[1]}
            for name in sorted(self.classes, key=str.casefold)
            if self._key_text(name) not in busy
        ]

    def free_rooms(self, day: str, slot: int) -> List[Dict[str, Any]]:
        pair = (self._day(day), int(slot))
        busy = self.busy_rooms.get(pair, set())

        return [
            {"room": name, "day": pair[0], "slot": pair[1]}
            for name in sorted(self.rooms, key=str.casefold)
            if self._key_text(name) not in busy
        ]