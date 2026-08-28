import re
from typing import Optional, Tuple, List, Dict, Any


class NaturalLanguageQuery:

    def __init__(self, engine):
        self.engine = engine

    # =========================================================
    # BASIC NORMALIZATION
    # =========================================================

    @staticmethod
    def normalize_lower(text: str) -> str:
        if not text:
            return ""

        return " ".join(
            str(text).strip().lower().split()
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        if not text:
            return ""

        return " ".join(
            str(text).strip().split()
        )

    @staticmethod
    def normalize_day(
        day: Optional[str]
    ) -> Optional[str]:

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

        return days.get(day, day)

    @staticmethod
    def normalize_slot(
        slot: Optional[int]
    ) -> Optional[int]:

        if slot is None:
            return None

        try:
            slot = int(slot)

            if 1 <= slot <= 8:
                return slot

        except Exception:
            pass

        return None

    # =========================================================
    # TEACHER NAME NORMALIZATION
    # =========================================================

    @staticmethod
    def _normalize_teacher_name(
        name: str
    ) -> str:

        if not name:
            return ""

        name = str(name).strip()

        name = re.sub(
            r"\s+",
            " ",
            name
        )

        return name

    normalize_teacher_name = _normalize_teacher_name

    # =========================================================
    # GET KNOWN TEACHERS
    # =========================================================

    def get_known_teachers(self) -> List[str]:

        teachers = set()

        possible_attributes = [
            "records",
            "data",
            "events",
            "canonical_records"
        ]

        for attribute in possible_attributes:

            try:

                data = getattr(
                    self.engine,
                    attribute,
                    None
                )

                if not data:
                    continue

                if isinstance(data, dict):
                    iterable = data.values()
                else:
                    iterable = data

                for record in iterable:

                    if not isinstance(record, dict):
                        continue

                    teacher = (
                        record.get("teacher")
                        or record.get("faculty")
                        or record.get("faculty_name")
                        or record.get("teacher_name")
                    )

                    if teacher:

                        teacher = (
                            self.normalize_teacher_name(
                                teacher
                            )
                        )

                        if teacher:
                            teachers.add(teacher)

            except Exception:
                pass

        # -----------------------------------------------------
        # Try matcher data
        # -----------------------------------------------------

        try:

            matcher = getattr(
                self.engine,
                "matcher",
                None
            )

            if matcher:

                data = getattr(
                    matcher,
                    "records",
                    None
                )

                if data:

                    for record in data:

                        if not isinstance(record, dict):
                            continue

                        teacher = record.get(
                            "teacher"
                        )

                        if teacher:

                            teacher = (
                                self.normalize_teacher_name(
                                    teacher
                                )
                            )

                            if teacher:
                                teachers.add(teacher)

        except Exception:
            pass

        return sorted(
            teachers,
            key=lambda x: x.lower()
        )

    # =========================================================
    # EXTRACT TEACHER
    # =========================================================

    def extract_teacher(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        if not text:
            return None

        lowered = text.lower()

        # -----------------------------------------------------
        # Exact known teacher names
        # -----------------------------------------------------

        known_teachers = self.get_known_teachers()

        if known_teachers:

            matches = []

            for teacher in known_teachers:

                teacher_clean = (
                    self.normalize_teacher_name(
                        teacher
                    )
                )

                if not teacher_clean:
                    continue

                teacher_lower = teacher_clean.lower()

                # Exact complete teacher name
                if teacher_lower in lowered:

                    matches.append(
                        teacher_clean
                    )

                    continue

                # -------------------------------------------------
                # Allow user to omit title
                # -------------------------------------------------

                without_title = re.sub(
                    r"^(dr|mr|mrs|ms|prof)\.?\s+",
                    "",
                    teacher_clean,
                    flags=re.IGNORECASE
                )

                without_title = without_title.strip()

                if (
                    without_title
                    and without_title.lower() in lowered
                ):

                    matches.append(
                        teacher_clean
                    )

            if matches:

                return max(
                    matches,
                    key=len
                )

        # -----------------------------------------------------
        # Generic faculty-title pattern
        # -----------------------------------------------------

        pattern = re.compile(
            r"\b(?:Dr\.?|Mr\.?|Mrs\.?|Ms\.?|Prof\.?)\s+"
            r"[A-Za-z][A-Za-z.\-']*"
            r"(?:\s+[A-Za-z][A-Za-z.\-']*){1,6}",
            re.IGNORECASE
        )

        match = pattern.search(text)

        if match:

            return self.normalize_teacher_name(
                match.group(0)
            )

        return None

    # =========================================================
    # EXTRACT DAY
    # =========================================================

    def extract_day(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_lower(query)

        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday"
        ]

        abbreviations = {
            "mon": "monday",
            "tue": "tuesday",
            "tues": "tuesday",
            "wed": "wednesday",
            "thu": "thursday",
            "thur": "thursday",
            "thurs": "thursday",
            "fri": "friday",
            "sat": "saturday",
            "sun": "sunday",
        }

        for day in days:

            if re.search(
                rf"\b{day}\b",
                text
            ):

                return day

        for short, full in abbreviations.items():

            if re.search(
                rf"\b{short}\b",
                text
            ):

                return full

        return None

    # =========================================================
    # EXTRACT SLOT
    # =========================================================

    @classmethod
    def extract_slot(
        cls,
        query: str
    ) -> Optional[int]:

        text = cls.normalize_lower(query)

        patterns = [

            r"\bslot\s*([1-8])\b",

            r"\bperiod\s*([1-8])\b",

            r"\bperiod\s+([1-8])\b",

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text
            )

            if match:

                return int(
                    match.group(1)
                )

        return None

    # =========================================================
    # TIME CONVERSION
    # =========================================================

    @staticmethod
    def _normalize_time(
        hour: str,
        minute: str,
        ampm: Optional[str] = None
    ) -> Optional[str]:

        try:

            h = int(hour)
            m = int(minute)

            if h < 0 or h > 23:
                return None

            if m < 0 or m > 59:
                return None

            if ampm:

                ampm = ampm.lower()

                if ampm == "pm" and h < 12:
                    h += 12

                if ampm == "am" and h == 12:
                    h = 0

            return f"{h:02d}:{m:02d}"

        except Exception:

            return None

    # =========================================================
    # EXTRACT TIME RANGE
    #
    # Supports:
    #
    # 9 to 11
    # 9-11
    # 9 until 11
    # 9 till 11
    #
    # 9:00 to 11:00
    # 9.00 to 11.00
    #
    # 9 AM to 11 AM
    # 9:00 AM to 11:00 AM
    # 9 AM - 11:30 AM
    #
    # Also:
    #
    # 9:15 to 11:15
    # 09:15 to 11:15
    # =========================================================

    @classmethod
    def extract_time_range(
        cls,
        query: str
    ) -> Optional[Tuple[str, str]]:

        text = cls.normalize_lower(query)

        if not text:
            return None

        pattern = re.compile(
            r"\b"
            r"(\d{1,2})"
            r"(?:[:.](\d{2}))?"
            r"\s*"
            r"(am|pm)?"
            r"\s*"
            r"(?:to|-|until|till|between)"
            r"\s*"
            r"(\d{1,2})"
            r"(?:[:.](\d{2}))?"
            r"\s*"
            r"(am|pm)?"
            r"\b",
            re.IGNORECASE
        )

        match = pattern.search(text)

        if not match:
            return None

        start_hour = match.group(1)
        start_minute = match.group(2) or "00"
        start_ampm = match.group(3)

        end_hour = match.group(4)
        end_minute = match.group(5) or "00"
        end_ampm = match.group(6)

        # -----------------------------------------------------
        # If AM/PM appears on only one side,
        # apply it to both sides.
        #
        # Example:
        #
        # 9 AM to 11
        #
        # becomes:
        #
        # 9 AM to 11 AM
        # -----------------------------------------------------

        if start_ampm and not end_ampm:

            end_ampm = start_ampm

        elif end_ampm and not start_ampm:

            start_ampm = end_ampm

        start = cls._normalize_time(
            start_hour,
            start_minute,
            start_ampm
        )

        end = cls._normalize_time(
            end_hour,
            end_minute,
            end_ampm
        )

        if not start or not end:
            return None

        # -----------------------------------------------------
        # End must be after start
        # -----------------------------------------------------

        start_minutes = (
            int(start[:2]) * 60
            + int(start[3:])
        )

        end_minutes = (
            int(end[:2]) * 60
            + int(end[3:])
        )

        if end_minutes <= start_minutes:
            return None

        return (
            start,
            end
        )

    # =========================================================
    # EXTRACT ROOM
    # =========================================================

    def extract_room(
        self,
        query: str
    ) -> Optional[str]:

        text = self.normalize_text(query)

        patterns = [

            r"\broom\s*#\s*([A-Za-z0-9\-]+)",

            r"\broom\s+([A-Za-z0-9\-]+)",

            r"\bclassroom\s+([A-Za-z0-9\-]+)",

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:

                return match.group(1)

        return None

    # =========================================================
    # EXTRACT CLASS
    # =========================================================
def extract_class(
    self,
    query: str
) -> Optional[str]:

    text = self.normalize_text(query)

    patterns = [

        # class 3CS-D
        r"\bclass\s+([A-Za-z0-9_.\-]+)",

        # section 3CS-D
        r"\bsection\s+([A-Za-z0-9_.\-]+)",

        # timetable of 3CS-D
        r"\btimetable\s+of\s+([A-Za-z0-9_.\-]+)",

        # schedule of 3CS-D
        r"\bschedule\s+of\s+([A-Za-z0-9_.\-]+)",

        # timetable for 3CS-D
        r"\btimetable\s+for\s+([A-Za-z0-9_.\-]+)",

        # schedule for 3CS-D
        r"\bschedule\s+for\s+([A-Za-z0-9_.\-]+)",

        # timetable 3CS-D
        r"\btimetable\s+([A-Za-z0-9_.\-]+)",

        # schedule 3CS-D
        r"\bschedule\s+([A-Za-z0-9_.\-]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return match.group(1)

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

            r"\bteachers\s+teaching\s+(.+?)(?:\?|$)",

        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE
            )

            if match:

                return match.group(1).strip()

        return None

    # =========================================================
    # DETECT INTENT
    # =========================================================

    def detect_intent(
        self,
        query: str
    ) -> str:

        text = self.normalize_lower(
            query
        )

        teacher = self.extract_teacher(
            query
        )

        # -----------------------------------------------------
        # FACULTY STATUS
        # -----------------------------------------------------

        if teacher and (
            "free" in text
            or "available" in text
            or "busy" in text
            or "occupied" in text
        ):

            return "faculty_status"

        # -----------------------------------------------------
        # FACULTY FREE
        # -----------------------------------------------------

        if (
            (
                "faculty" in text
                or "teacher" in text
                or "professor" in text
            )
            and
            (
                "free" in text
                or "available" in text
            )
        ):

            return "faculty_free"

        # -----------------------------------------------------
        # ROOM FREE
        # -----------------------------------------------------

        if (
            (
                "room" in text
                or "classroom" in text
            )
            and
            (
                "free" in text
                or "available" in text
            )
        ):

            return "room_free"

        # -----------------------------------------------------
        # CLASS FREE
        # -----------------------------------------------------

        if (
            (
                "class" in text
                or "section" in text
            )
            and
            (
                "free" in text
                or "available" in text
            )
        ):

            return "class_free"

        # -----------------------------------------------------
        # TEACHER SCHEDULE
        # -----------------------------------------------------

        if teacher and (
            "schedule" in text
            or "timetable" in text
            or "teaching" in text
            or "teach" in text
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

        if (
            "faculty teaching" in text
            or "teachers teaching" in text
        ):

            return "subject_search"

        # -----------------------------------------------------
        # CLASS SCHEDULE
        # -----------------------------------------------------

        class_name = self.extract_class(
            query
        )

        if class_name and (
            "schedule" in text
            or "timetable" in text
            or "classes" in text
        ):

            return "class_schedule"

        # -----------------------------------------------------
        # ROOM STATUS
        # -----------------------------------------------------

        if (
            (
                "room" in text
                or "classroom" in text
            )
            and
            (
                "schedule" in text
                or "occupied" in text
                or "busy" in text
            )
        ):

            return "room_status"

        # -----------------------------------------------------
        # GENERIC FACULTY FREE
        # -----------------------------------------------------

        if (
            ("who" in text or "which" in text)
            and
            (
                "free" in text
                or "available" in text
            )
            and
            "room" not in text
            and
            "classroom" not in text
            and
            "class" not in text
            and
            "section" not in text
        ):

            return "faculty_free"

        return "unknown"

    # =========================================================
    # CALL ENGINE METHOD
    # =========================================================

    def call_engine_method(
        self,
        method_name: str,
        **kwargs
    ):

        method = getattr(
            self.engine,
            method_name,
            None
        )

        if not method:
            return []

        try:

            return method(
                **kwargs
            )

        except TypeError:

            try:

                if method_name == "faculty_status":

                    return method(
                        kwargs.get("teacher"),
                        kwargs.get("day"),
                        kwargs.get("slot")
                    )

                return method()

            except Exception:

                return []

        except Exception:

            return []

    # =========================================================
    # RESULT TO LIST
    # =========================================================

    @staticmethod
    def result_to_list(
        result
    ) -> List[Dict[str, Any]]:

        if result is None:
            return []

        if isinstance(
            result,
            list
        ):

            return result

        if isinstance(
            result,
            tuple
        ):

            return list(result)

        if isinstance(
            result,
            dict
        ):

            # -------------------------------------------------
            # Period methods return:
            #
            # {
            #     "results": [...]
            # }
            #
            # We must extract that list instead of returning
            # the entire wrapper as one record.
            # -------------------------------------------------

            if isinstance(
                result.get("results"),
                list
            ):

                return result["results"]

            return [result]

        return []

    # =========================================================
    # FACULTY STATUS
    # =========================================================

    def execute_faculty_status(
        self,
        teacher: Optional[str],
        day: Optional[str],
        slot: Optional[int],
        time_range: Optional[
            Tuple[str, str]
        ] = None
    ) -> List[Dict[str, Any]]:

        if not teacher:
            return []

        # -----------------------------------------------------
        # TIME RANGE QUERY
        # -----------------------------------------------------

        if (
            time_range
            and hasattr(
                self.engine,
                "faculty_status_for_period"
            )
            and day
        ):

            start_time, end_time = time_range

            try:

                result = (
                    self.engine.faculty_status_for_period(
                        teacher,
                        day,
                        start_time,
                        end_time
                    )
                )

                # Keep the complete status dictionary.
                if isinstance(
                    result,
                    dict
                ):

                    return [result]

                return self.result_to_list(
                    result
                )

            except Exception:

                pass

        # -----------------------------------------------------
        # NORMAL SLOT QUERY
        # -----------------------------------------------------

        result = self.call_engine_method(
            "faculty_status",
            teacher=teacher,
            day=day,
            slot=slot
        )

        return self.result_to_list(
            result
        )

    # =========================================================
    # FACULTY FREE
    # =========================================================

    def execute_faculty_free(
        self,
        day: Optional[str],
        slot: Optional[int],
        time_range: Optional[
            Tuple[str, str]
        ] = None
    ) -> List[Dict[str, Any]]:

        # -----------------------------------------------------
        # TIME RANGE QUERY
        # -----------------------------------------------------

        if (
            time_range
            and hasattr(
                self.engine,
                "faculty_free_for_period"
            )
            and day
        ):

            try:

                start_time, end_time = time_range

                result = (
                    self.engine.faculty_free_for_period(
                        day,
                        start_time,
                        end_time
                    )
                )

                return self.result_to_list(
                    result
                )

            except Exception:

                pass

        # -----------------------------------------------------
        # NORMAL FACULTY-FREE QUERY
        # -----------------------------------------------------

        result = self.call_engine_method(
            "faculty_free_slots",
            day=day,
            slot=slot
        )

        return self.result_to_list(
            result
        )

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

        return self.result_to_list(
            result
        )

    # =========================================================
    # ROOM FREE
    # =========================================================

    def execute_room_free(
        self,
        room: Optional[str],
        day: Optional[str],
        slot: Optional[int]
    ) -> List[Dict[str, Any]]:

        result = self.call_engine_method(
            "room_free",
            room=room,
            day=day,
            slot=slot
        )

        return self.result_to_list(
            result
        )

    # =========================================================
    # TEACHER SCHEDULE
    # =========================================================

    def execute_teacher_schedule(
        self,
        teacher: Optional[str],
        day: Optional[str]
    ) -> List[Dict[str, Any]]:

        result = self.call_engine_method(
            "teacher_schedule",
            teacher=teacher,
            day=day
        )

        return self.result_to_list(
            result
        )

    # =========================================================
    # CLASS SCHEDULE
    # =========================================================

    def execute_class_schedule(
        self,
        class_name: Optional[str],
        day: Optional[str]
    ) -> List[Dict[str, Any]]:

        result = self.call_engine_method(
            "class_schedule",
            class_name=class_name,
            day=day
        )

        return self.result_to_list(
            result
        )

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

        return self.result_to_list(
            result
        )

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

        return self.result_to_list(
            result
        )

    # =========================================================
    # EXECUTE QUERY
    # =========================================================

    def execute(
        self,
        query: str
    ) -> Dict[str, Any]:

        intent = self.detect_intent(
            query
        )

        teacher = self.extract_teacher(
            query
        )

        day = self.extract_day(
            query
        )

        slot = self.extract_slot(
            query
        )

        time_range = self.extract_time_range(
            query
        )

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        if intent == "unknown":

            return {
                "intent": "unknown",
                "success": False,
                "count": 0,
                "results": [],
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

            room = self.extract_room(
                query
            )

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

            class_name = self.extract_class(
                query
            )

            records = self.execute_class_schedule(
                class_name,
                day
            )

            return {
                "intent": intent,
                "success": True,
                "count": len(records),
                "results": records,
                "class_name": class_name,
                "day": day
            }

        # -----------------------------------------------------
        # ROOM STATUS
        # -----------------------------------------------------

        if intent == "room_status":

            room = self.extract_room(
                query
            )

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

            subject = self.extract_subject(
                query
            )

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

        # -----------------------------------------------------
        # FALLBACK
        # -----------------------------------------------------

        return {
            "intent": intent,
            "success": False,
            "count": 0,
            "results": [],
            "message": (
                "No handler available for this query."
            )
        }

    # =========================================================
    # ANSWER
    # =========================================================

    def answer(
        self,
        query: str
    ) -> str:

        result = self.execute(
            query
        )

        intent = result.get(
            "intent"
        )

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        if intent == "unknown":

            return result.get(
                "message",
                "I could not understand the query."
            )

        # =====================================================
        # FACULTY STATUS
        # =====================================================

        if intent == "faculty_status":

            teacher = result.get(
                "teacher"
            )

            day = result.get(
                "day"
            )

            time_range = result.get(
                "time_range"
            )

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    f"No faculty status information "
                    f"found for {teacher}"
                    f"{' on ' + day if day else ''}."
                )

            data = records[0]

            status = str(
                data.get(
                    "status",
                    ""
                )
            ).lower()

            query_lower = self.normalize_lower(
                query
            )

            asked_busy = (
                "busy" in query_lower
                or "occupied" in query_lower
            )

            asked_free = (
                "free" in query_lower
                or "available" in query_lower
            )

            # =================================================
            # TIME RANGE
            # =================================================

            if time_range:

                start_time = time_range[0]
                end_time = time_range[1]

                if status == "free":

                    slots = data.get(
                        "slots",
                        []
                    )

                    if asked_busy:

                        return (
                            f"No, {teacher} is not busy on "
                            f"{day} from {start_time} to "
                            f"{end_time}. "
                            f"{teacher} is free during this period."
                        )

                    return (
                        f"Yes, {teacher} is free on "
                        f"{day} from {start_time} to "
                        f"{end_time}. "
                        f"Free slots: {slots}."
                    )

                if status == "busy":

                    if asked_free:

                        return (
                            f"No, {teacher} is not free on "
                            f"{day} from {start_time} to "
                            f"{end_time}. "
                            f"{teacher} is busy during this period."
                        )

                    return (
                        f"Yes, {teacher} is busy on "
                        f"{day} from {start_time} to "
                        f"{end_time}."
                    )

                return (
                    f"The status of {teacher} is unknown "
                    f"for {day} from {start_time} to "
                    f"{end_time}."
                )

            # =================================================
            # NORMAL SLOT QUERY
            # =================================================

            slot = result.get(
                "slot"
            )

            if status == "free":

                if asked_busy:

                    return (
                        f"No, {teacher} is not busy on "
                        f"{day}"
                        f"{' in slot ' + str(slot) if slot else ''}. "
                        f"{teacher} is free."
                    )

                return (
                    f"Yes, {teacher} is free on "
                    f"{day}"
                    f"{' in slot ' + str(slot) if slot else ''}."
                )

            if status == "busy":

                if asked_free:

                    return (
                        f"No, {teacher} is not free on "
                        f"{day}"
                        f"{' in slot ' + str(slot) if slot else ''}. "
                        f"{teacher} is busy."
                    )

                return (
                    f"Yes, {teacher} is busy on "
                    f"{day}"
                    f"{' in slot ' + str(slot) if slot else ''}."
                )

            return (
                f"Status of {teacher} could not be determined."
            )

        # =====================================================
        # FACULTY FREE
        # =====================================================

        if intent == "faculty_free":

            records = result.get(
                "results",
                []
            )

            day = result.get(
                "day"
            )

            time_range = result.get(
                "time_range"
            )

            if not records:

                return (
                    f"No free faculty found"
                    f"{' on ' + day if day else ''}."
                )

            names = []

            for record in records:

                if not isinstance(
                    record,
                    dict
                ):
                    continue

                teacher = record.get(
                    "teacher"
                )

                if teacher:

                    names.append(
                        str(teacher)
                    )

            if names:

                if time_range:

                    return (
                        f"Free faculty on {day} "
                        f"from {time_range[0]} to "
                        f"{time_range[1]}: "
                        + ", ".join(names)
                    )

                return (
                    "Free faculty: "
                    + ", ".join(names)
                )

            return (
                f"{len(records)} free faculty records found."
            )

        # =====================================================
        # CLASS FREE
        # =====================================================

        if intent == "class_free":

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    "No free classes found."
                )

            return (
                f"{len(records)} free class records found."
            )

        # =====================================================
        # ROOM FREE
        # =====================================================

        if intent == "room_free":

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    "No free rooms found."
                )

            rooms = []

            for record in records:

                if not isinstance(
                    record,
                    dict
                ):
                    continue

                room = record.get(
                    "room"
                )

                if room:

                    rooms.append(
                        str(room)
                    )

            if rooms:

                return (
                    "Free rooms: "
                    + ", ".join(rooms)
                )

            return (
                f"{len(records)} free room records found."
            )

        # =====================================================
        # TEACHER SCHEDULE
        # =====================================================

        if intent == "teacher_schedule":

            teacher = result.get(
                "teacher"
            )

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    f"No schedule found for {teacher}."
                )

            return (
                f"{len(records)} schedule records found "
                f"for {teacher}."
            )

        # =====================================================
        # CLASS SCHEDULE
        # =====================================================

        if intent == "class_schedule":

            class_name = result.get(
                "class_name"
            )

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    f"No schedule found for "
                    f"{class_name}."
                )

            return (
                f"{len(records)} schedule records found "
                f"for {class_name}."
            )

        # =====================================================
        # ROOM STATUS
        # =====================================================

        if intent == "room_status":

            room = result.get(
                "room"
            )

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    f"No status information found "
                    f"for room {room}."
                )

            return (
                f"Status information found for room "
                f"{room}."
            )

        # =====================================================
        # SUBJECT SEARCH
        # =====================================================

        if intent == "subject_search":

            subject = result.get(
                "subject"
            )

            records = result.get(
                "results",
                []
            )

            if not records:

                return (
                    f"No faculty found teaching "
                    f"{subject}."
                )

            teachers = []

            for record in records:

                if not isinstance(
                    record,
                    dict
                ):
                    continue

                teacher = record.get(
                    "teacher"
                )

                if teacher:

                    teachers.append(
                        str(teacher)
                    )

            if teachers:

                return (
                    f"Faculty teaching {subject}: "
                    + ", ".join(teachers)
                )

            return (
                f"{len(records)} records found."
            )

        # =====================================================
        # FALLBACK
        # =====================================================

        return (
            "Query processed successfully."
        )