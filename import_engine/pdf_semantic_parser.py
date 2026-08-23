"""
==========================================================
UNISCHED AI - PDF SEMANTIC PARSER
==========================================================

Purpose
-------
Convert raw timetable cell text into structured semantic
fields without replacing the existing PDFImporter.

Important design principle
--------------------------
A short uppercase token is NOT automatically a faculty code.

For example:

    OS III 301 MKB

should NOT become:

    teacher = OS

Instead, the parser first identifies:

    subject candidate
    room
    class
    possible faculty code

Faculty resolution is performed only when there is enough
evidence.

Architecture:

PDF
 ↓
PDFImporter
 ↓
PDFSemanticParser
 ↓
UniversalNormalizer
 ↓
Canonical Event Matcher
 ↓
Query Engine

==========================================================
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple


class PDFSemanticParser:
    """
    Semantic parser for raw timetable records.

    This class is intentionally conservative.

    It tries to extract:
        - subject
        - teacher
        - teacher_code
        - room
        - class_name
        - group_name

    It does not blindly guess faculty names.
    """

    # ======================================================
    # DAYS
    # ======================================================

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

    # ======================================================
    # ROOM PATTERNS
    # ======================================================

    ROOM_PATTERNS = [
        # 301
        re.compile(
            r"^\d{3,4}$"
        ),

        # A-301 / B-204
        re.compile(
            r"^[A-Za-z]{1,8}-\d{2,4}$",
            re.IGNORECASE,
        ),

        # CSE-301
        re.compile(
            r"^[A-Za-z]{2,10}-\d{1,4}$",
            re.IGNORECASE,
        ),

        # 7F:EE-Lab13
        re.compile(
            r"^[A-Za-z0-9]+:[A-Za-z0-9_-]+$",
            re.IGNORECASE,
        ),

        # Lab13 / Room301
        re.compile(
            r"^(?:lab|room|rm)\s*[-:]?\s*\d+$",
            re.IGNORECASE,
        ),
    ]

    # ======================================================
    # CLASS PATTERNS
    # ======================================================

    CLASS_PATTERNS = [
        # 3CSA
        re.compile(
            r"^\d+[A-Za-z]{2,10}$"
        ),

        # 3CS-A
        re.compile(
            r"^\d+[A-Za-z]{2,10}-[A-Za-z0-9]+$"
        ),

        # 3CS A
        re.compile(
            r"^\d+[A-Za-z]{2,10}\s+[A-Za-z0-9]+$"
        ),

        # CSE-3A
        re.compile(
            r"^[A-Za-z]{2,10}-\d+[A-Za-z0-9]+$"
        ),

        # CSE 3A
        re.compile(
            r"^[A-Za-z]{2,10}\s+\d+[A-Za-z0-9]+$"
        ),
    ]

    # ======================================================
    # GROUP PATTERNS
    # ======================================================

    GROUP_PATTERNS = [
        re.compile(
            r"^group\s*\d+$",
            re.IGNORECASE,
        ),

        re.compile(
            r"^grp\s*\d+$",
            re.IGNORECASE,
        ),

        re.compile(
            r"^g\d+$",
            re.IGNORECASE,
        ),
    ]

    # ======================================================
    # FACULTY CODE PATTERN
    # ======================================================

    FACULTY_CODE_PATTERN = re.compile(
        r"^[A-Za-z]{2,5}$"
    )

    # ======================================================
    # SUBJECT-LIKE TOKENS
    # ======================================================

    #
    # These are common academic abbreviations that must
    # NEVER automatically become faculty codes.
    #
    # This is intentionally generic rather than tied to
    # individual faculty names.
    #

    SUBJECT_CODE_BLOCKLIST = {
        "OS",
        "DBMS",
        "CN",
        "COA",
        "TOC",
        "DAA",
        "DSA",
        "AI",
        "ML",
        "NLP",
        "SE",
        "PM",
        "DE",
        "DM",
        "DMCT",
        "WC",
        "FOB",
        "FODS",
        "IOT",
        "OOPS",
        "JAVA",
        "PYTHON",
        "C",
        "CPP",
        "CSE",
        "ECE",
        "EEE",
        "LAB",
        "T",
        "P",
        "THEORY",
        "PRACTICAL",
        "PROJECT",
        "AUDIT",
        "COURSE",
    }

    # ======================================================
    # CONSTRUCTOR
    # ======================================================

    def __init__(
        self,
        records: Optional[
            Iterable[Dict[str, Any]]
        ] = None,
    ) -> None:

        self.records = (
            list(records)
            if records is not None
            else []
        )

        # Full faculty names discovered from imported data.
        self.known_teachers: set[str] = set()

        # Known classes.
        self.known_classes: set[str] = set()

        # Known rooms.
        self.known_rooms: set[str] = set()

        # Known subjects.
        self.known_subjects: set[str] = set()

        # Tokens observed inside known subject names.
        # Prevents values such as IAI or III from being
        # misclassified as unknown faculty codes.
        self.known_subject_tokens: set[str] = set()

        # Explicit location aliases learned from room fields.
        self.location_aliases: Dict[str, str] = {}

        # Alias -> teacher.
        self.faculty_aliases: Dict[
            str,
            str,
        ] = {}

        # Teacher -> aliases.
        self.teacher_aliases: Dict[
            str,
            set[str],
        ] = defaultdict(set)

        if self.records:
            self.build_knowledge_base(
                self.records
            )

    # ======================================================
    # TEXT CLEANING
    # ======================================================

    @staticmethod
    def clean_text(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        text = str(value)

        text = (
            text
            .replace("\n", " ")
            .replace("\r", " ")
            .replace("\t", " ")
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()

    # ======================================================
    # DAY
    # ======================================================

    @classmethod
    def normalize_day(
        cls,
        value: Any,
    ) -> str:

        text = cls.clean_text(
            value
        ).lower()

        if not text:
            return ""

        return cls.DAY_ALIASES.get(
            text,
            text,
        )

    # ======================================================
    # SLOT
    # ======================================================

    @staticmethod
    def normalize_slot(
        value: Any,
    ) -> Optional[int]:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        patterns = [
            r"^(?:slot|period|p)\s*[-:]?\s*(\d+)$",
            r"^(\d+)(?:\.0)?$",
        ]

        for pattern in patterns:

            match = re.match(
                pattern,
                text,
                re.IGNORECASE,
            )

            if match:

                try:
                    return int(
                        match.group(1)
                    )
                except (
                    ValueError,
                    IndexError,
                ):
                    return None

        try:

            number = float(text)

            if number.is_integer():

                return int(number)

        except ValueError:

            pass

        return None

    # ======================================================
    # ROOM DETECTION
    # ======================================================

    @classmethod
    def looks_like_room(
        cls,
        value: Any,
    ) -> bool:

        text = cls.clean_text(
            value
        )

        if not text:
            return False

        for pattern in cls.ROOM_PATTERNS:

            if pattern.match(text):

                return True

        return False

    # ======================================================
    # CLASS DETECTION
    # ======================================================

    @classmethod
    def looks_like_class(
        cls,
        value: Any,
    ) -> bool:

        text = cls.clean_text(
            value
        )

        if not text:
            return False

        for pattern in cls.CLASS_PATTERNS:

            if pattern.match(text):

                return True

        return False

    # ======================================================
    # GROUP DETECTION
    # ======================================================

    @classmethod
    def looks_like_group(
        cls,
        value: Any,
    ) -> bool:

        text = cls.clean_text(
            value
        )

        if not text:
            return False

        for pattern in cls.GROUP_PATTERNS:

            if pattern.match(text):

                return True

        return False

    # ======================================================
    # FACULTY CODE DETECTION
    # ======================================================

    @classmethod
    def looks_like_faculty_code(
        cls,
        value: Any,
    ) -> bool:

        text = cls.clean_text(
            value
        )

        if not text:
            return False

        if not cls.FACULTY_CODE_PATTERN.match(
            text
        ):
            return False

        upper = text.upper()

        # Academic abbreviations must not be
        # automatically interpreted as faculty.
        if upper in cls.SUBJECT_CODE_BLOCKLIST:
            return False

        return True

    # ======================================================
    # TEACHER NAME DETECTION
    # ======================================================

    @classmethod
    def looks_like_teacher_name(
        cls,
        value: Any,
    ) -> bool:

        text = cls.clean_text(
            value
        )

        if not text:
            return False

        lowered = text.lower()

        prefixes = (
            "dr.",
            "dr ",
            "mr.",
            "mr ",
            "mrs.",
            "mrs ",
            "ms.",
            "ms ",
            "prof.",
            "prof ",
            "professor ",
        )

        if lowered.startswith(
            prefixes
        ):
            return True

        words = re.findall(
            r"[A-Za-z]+",
            text,
        )

        return len(words) >= 2

    # ======================================================
    # TOKENIZATION
    # ======================================================

    @classmethod
    def tokenize_cell(
        cls,
        value: Any,
    ) -> List[str]:

        text = cls.clean_text(
            value
        )

        if not text:
            return []

        return [
            token
            for token in text.split()
            if token
        ]

    # ======================================================
    # GENERATE FACULTY ALIASES
    # ======================================================

    @classmethod
    def generate_teacher_aliases(
        cls,
        teacher: str,
    ) -> set[str]:
        """
        Generate candidate aliases from a faculty name.

        Example:

            Dr. Mehul Mahrishi

        may generate:

            MM

        These are candidates only.
        """

        aliases: set[str] = set()

        text = cls.clean_text(
            teacher
        )

        if not text:
            return aliases

        text = re.sub(
            r"^(dr|mr|mrs|ms|prof|professor)\.?\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        words = re.findall(
            r"[A-Za-z]+",
            text,
        )

        if len(words) < 2:
            return aliases

        initials = "".join(
            word[0].upper()
            for word in words
            if word
        )

        if len(initials) >= 2:

            aliases.add(
                initials
            )

        first_last = (
            words[0][0]
            + words[-1][0]
        ).upper()

        if len(first_last) >= 2:

            aliases.add(
                first_last
            )

        return aliases

    # ======================================================
    # KNOWLEDGE BASE
    # ======================================================

    def build_knowledge_base(
        self,
        records: Iterable[
            Dict[str, Any]
        ],
    ) -> None:

        # Reset collections so this method can safely
        # be called again.
        self.known_teachers.clear()
        self.known_classes.clear()
        self.known_rooms.clear()
        self.known_subjects.clear()
        self.known_subject_tokens.clear()
        self.location_aliases.clear()

        self.faculty_aliases.clear()
        self.teacher_aliases.clear()

        for record in records:

            teacher = self.clean_text(
                record.get(
                    "teacher",
                    "",
                )
            )

            class_name = self.clean_text(
                record.get(
                    "class_name",
                    "",
                )
            )

            room = self.clean_text(
                record.get(
                    "room",
                    "",
                )
            )

            subject = self.clean_text(
                record.get(
                    "subject",
                    "",
                )
            )

            if teacher:
                self.known_teachers.add(
                    teacher
                )

            if class_name:
                self.known_classes.add(
                    class_name
                )

            if room:
                self.known_rooms.add(
                    room
                )

            if subject:
                self.known_subjects.add(
                    subject
                )
                for token in self.tokenize_cell(subject):
                    cleaned_token = token.strip(",;|").upper()
                    if cleaned_token:
                        self.known_subject_tokens.add(cleaned_token)

        # --------------------------------------------------
        # Learn location aliases only from explicit room fields.
        # Never infer a room from subject text.
        # --------------------------------------------------
        for room in self.known_rooms:
            normalized_room = self.clean_text(room)
            if not normalized_room:
                continue

            self.location_aliases[normalized_room.upper()] = normalized_room

            room_tokens = self.tokenize_cell(normalized_room)
            if len(room_tokens) >= 2:
                first = room_tokens[0].strip(",;|")
                if first and len(first) >= 2:
                    key = first.upper()
                    if key not in self.known_subject_tokens:
                        self.location_aliases[key] = normalized_room

        # --------------------------------------------------
        # Build aliases.
        #
        # We do NOT automatically trust every generated
        # alias. We only register aliases that do not
        # conflict with obvious subject codes.
        # --------------------------------------------------

        for teacher in self.known_teachers:

            aliases = (
                self.generate_teacher_aliases(
                    teacher
                )
            )

            for alias in aliases:

                if (
                    alias.upper()
                    in self.SUBJECT_CODE_BLOCKLIST
                ):
                    continue

                self.faculty_aliases[
                    alias.upper()
                ] = teacher

                self.teacher_aliases[
                    teacher
                ].add(
                    alias.upper()
                )

    # ======================================================
    # FIND KNOWN LOCATION ALIAS
    # ======================================================

    def extract_known_location(
        self,
        tokens: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        """Extract only locations explicitly learned from room fields."""
        if not tokens or not self.location_aliases:
            return None, list(tokens)

        aliases = sorted(
            self.location_aliases.items(),
            key=lambda item: len(self.tokenize_cell(item[0])),
            reverse=True,
        )

        upper_tokens = [
            self.clean_text(token).strip(",;|").upper()
            for token in tokens
        ]

        for alias, canonical in aliases:
            alias_tokens = [
                self.clean_text(token).strip(",;|").upper()
                for token in self.tokenize_cell(alias)
            ]
            if not alias_tokens:
                continue

            width = len(alias_tokens)
            for start in range(0, len(upper_tokens) - width + 1):
                if upper_tokens[start:start + width] == alias_tokens:
                    return canonical, tokens[:start] + tokens[start + width:]

        return None, list(tokens)

    # ======================================================
    # FIND ROOM
    # ======================================================

    @classmethod
    def extract_room(
        cls,
        tokens: List[str],
    ) -> Tuple[
        Optional[str],
        List[str],
    ]:

        room = None
        remaining = []

        for token in tokens:

            cleaned = (
                token
                .strip()
                .strip(",;|")
            )

            if (
                room is None
                and cls.looks_like_room(
                    cleaned
                )
            ):

                room = cleaned

            else:

                remaining.append(
                    token
                )

        return room, remaining

    # ======================================================
    # FIND CLASS
    # ======================================================

    @classmethod
    def extract_class(
        cls,
        tokens: List[str],
    ) -> Tuple[
        Optional[str],
        List[str],
    ]:

        class_name = None
        remaining = []

        for token in tokens:

            cleaned = (
                token
                .strip()
                .strip(",;|")
            )

            if (
                class_name is None
                and cls.looks_like_class(
                    cleaned
                )
            ):

                class_name = cleaned

            else:

                remaining.append(
                    token
                )

        return class_name, remaining

    # ======================================================
    # FIND KNOWN FACULTY ALIAS
    # ======================================================

    def extract_known_faculty(
        self,
        tokens: List[str],
    ) -> Tuple[
        Optional[str],
        List[str],
    ]:

        teacher = None
        remaining = []

        for token in tokens:

            cleaned = (
                token
                .strip()
                .strip(",;|")
            )

            upper = cleaned.upper()

            if (
                teacher is None
                and upper
                in self.faculty_aliases
            ):

                teacher = (
                    self.faculty_aliases[
                        upper
                    ]
                )

            else:

                remaining.append(
                    token
                )

        return teacher, remaining

    # ======================================================
    # FIND POSSIBLE FACULTY CODE
    # ======================================================

    def extract_possible_faculty_code(
        self,
        tokens: List[str],
    ) -> Tuple[
        Optional[str],
        List[str],
    ]:
        """
        Detect a possible faculty abbreviation.

        IMPORTANT:
        This does not mean the token is definitely faculty.

        A token is considered only if:
            - it is alphabetic
            - it is short
            - it is not a blocked academic code
            - it appears toward the END of the cell

        This positional rule is important because timetable
        formats frequently use:

            SUBJECT ROOM FACULTY

        or:

            SUBJECT FACULTY CLASS
        """

        if not tokens:

            return None, []

        remaining = list(
            tokens
        )

        # Search from right to left because faculty
        # abbreviations commonly occur after the subject.
        for index in range(
            len(tokens) - 1,
            -1,
            -1,
        ):

            token = (
                tokens[index]
                .strip()
                .strip(",;|")
            )

            if not token:
                continue

            upper = token.upper()

            # Already known faculty alias.
            if upper in self.faculty_aliases:

                return (
                    self.faculty_aliases[
                        upper
                    ],
                    tokens[:index]
                    + tokens[index + 1:],
                )

            # Unknown abbreviation.
            # If it is already observed inside a known subject,
            # preserve it as subject text instead of inventing
            # a faculty code.
            if (
                self.looks_like_faculty_code(token)
                and upper not in self.known_subject_tokens
            ):

                # Only accept a candidate if it occurs
                # after at least one other token.
                if index > 0:

                    return (
                        upper,
                        tokens[:index]
                        + tokens[index + 1:],
                    )

        return None, remaining

    # ======================================================
    # GROUP
    # ======================================================

    @classmethod
    def extract_group(
        cls,
        tokens: List[str],
    ) -> Tuple[
        Optional[str],
        List[str],
    ]:

        group = None
        remaining = []

        for token in tokens:

            if (
                group is None
                and cls.looks_like_group(
                    token
                )
            ):

                group = token

            else:

                remaining.append(
                    token
                )

        return group, remaining

    # ======================================================
    # SUBJECT CLEANING
    # ======================================================

    @classmethod
    def clean_subject(
        cls,
        tokens: List[str],
    ) -> str:

        if not tokens:

            return ""

        return " ".join(
            token.strip(
                ",;|"
            )
            for token in tokens
            if token.strip(
                ",;|"
            )
        ).strip()

    # ======================================================
    # PARSE CELL
    # ======================================================

    def parse_cell(
        self,
        cell_value: Any,
        existing_record: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        record = dict(
            existing_record or {}
        )

        raw = self.clean_text(
            cell_value
        )

        # --------------------------------------------------
        # Preserve raw source text.
        # --------------------------------------------------

        if not record.get(
            "raw_text"
        ):

            record["raw_text"] = raw

        # --------------------------------------------------
        # Empty cell.
        # --------------------------------------------------

        if not raw:

            return record

        tokens = self.tokenize_cell(
            raw
        )

        # --------------------------------------------------
        # Existing fields.
        # --------------------------------------------------

        teacher = self.clean_text(
            record.get(
                "teacher",
                "",
            )
        )

        subject = self.clean_text(
            record.get(
                "subject",
                "",
            )
        )

        room = self.clean_text(
            record.get(
                "room",
                "",
            )
        )

        class_name = self.clean_text(
            record.get(
                "class_name",
                "",
            )
        )

        group_name = self.clean_text(
            record.get(
                "group_name",
                "",
            )
        )

        # --------------------------------------------------
        # STEP 1 - ROOM / LOCATION
        # --------------------------------------------------

        if not room:

            known_location, remaining = (
                self.extract_known_location(tokens)
            )

            if known_location:
                room = known_location
                tokens = remaining
            else:
                room, tokens = (
                    self.extract_room(
                        tokens
                    )
                )

        # --------------------------------------------------
        # STEP 2 - CLASS
        # --------------------------------------------------

        if not class_name:

            class_name, tokens = (
                self.extract_class(
                    tokens
                )
            )

        # --------------------------------------------------
        # STEP 3 - GROUP
        # --------------------------------------------------

        if not group_name:

            group_name, tokens = (
                self.extract_group(
                    tokens
                )
            )

        # --------------------------------------------------
        # STEP 4 - KNOWN FACULTY
        # --------------------------------------------------

        if not teacher:

            known_teacher, tokens = (
                self.extract_known_faculty(
                    tokens
                )
            )

            if known_teacher:

                teacher = known_teacher

        # --------------------------------------------------
        # STEP 5 - POSSIBLE FACULTY CODE
        # --------------------------------------------------

        teacher_code = (
            self.clean_text(
                record.get(
                    "teacher_code",
                    "",
                )
            )
        )

        if not teacher_code:

            candidate, remaining = (
                self.extract_possible_faculty_code(
                    tokens
                )
            )

            if candidate:

                # If candidate resolves to a known teacher,
                # store the full name.
                if (
                    candidate.upper()
                    in self.faculty_aliases
                ):

                    teacher = (
                        self.faculty_aliases[
                            candidate.upper()
                        ]
                    )

                    teacher_code = (
                        candidate.upper()
                    )

                    tokens = remaining

                else:

                    # Keep it as an unresolved code.
                    # Do not call it a full teacher name.
                    teacher_code = (
                        candidate
                    )

                    tokens = remaining

        # --------------------------------------------------
        # STEP 6 - SUBJECT
        # --------------------------------------------------

        if not subject:

            subject = self.clean_subject(
                tokens
            )

        # --------------------------------------------------
        # STEP 7 - STORE
        # --------------------------------------------------

        record["subject"] = subject
        record["teacher"] = teacher
        record["teacher_code"] = teacher_code
        record["room"] = room or ""
        record["class_name"] = (
            class_name or ""
        )
        record["group_name"] = (
            group_name or ""
        )

        return record

    # ======================================================
    # PARSE RECORD
    # ======================================================

    def parse_record(
        self,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = dict(
            record
        )

        # Normalize day.
        result["day"] = (
            self.normalize_day(
                result.get(
                    "day",
                    "",
                )
            )
        )

        # Normalize slot.
        result["slot"] = (
            self.normalize_slot(
                result.get(
                    "slot"
                )
            )
        )

        # --------------------------------------------------
        # Decide what text should be parsed.
        #
        # Prefer raw_text because it contains the complete
        # timetable cell.
        # --------------------------------------------------

        raw_text = self.clean_text(
            result.get(
                "raw_text",
                "",
            )
        )

        if raw_text:

            result = self.parse_cell(
                raw_text,
                result,
            )

        return result

    # ======================================================
    # PARSE ALL RECORDS
    # ======================================================

    def parse_records(
        self,
        records: Iterable[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:

        records = list(
            records
        )

        self.records = records

        # Build known faculty/class/room information
        # BEFORE semantic parsing.
        self.build_knowledge_base(
            records
        )

        parsed = []

        for record in records:

            try:

                parsed_record = (
                    self.parse_record(
                        record
                    )
                )

                parsed.append(
                    parsed_record
                )

            except Exception:

                # Robustness requirement:
                # one malformed cell must never stop
                # the complete timetable.
                parsed.append(
                    dict(record)
                )

        return parsed

    # ======================================================
    # DISCOVER POSSIBLE FACULTY CODES
    # ======================================================

    def discover_unknown_aliases(
        self,
        records: Iterable[
            Dict[str, Any]
        ],
    ) -> Dict[str, int]:

        counter = Counter()

        for record in records:

            raw = self.clean_text(
                record.get(
                    "raw_text",
                    "",
                )
            )

            tokens = self.tokenize_cell(
                raw
            )

            for token in tokens:

                cleaned = (
                    token
                    .strip()
                    .strip(",;|")
                )

                if self.looks_like_faculty_code(
                    cleaned
                ):

                    counter[
                        cleaned.upper()
                    ] += 1

        return dict(
            counter.most_common()
        )

    # ======================================================
    # SUMMARY
    # ======================================================

    def summary(
        self,
        records: Iterable[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        records = list(
            records
        )

        def unique_nonempty(
            key: str,
        ) -> set[str]:

            return {
                self.clean_text(
                    record.get(
                        key,
                        "",
                    )
                )
                for record in records
                if self.clean_text(
                    record.get(
                        key,
                        "",
                    )
                )
            }

        return {
            "records": len(
                records
            ),
            "teachers": len(
                unique_nonempty(
                    "teacher"
                )
            ),
            "teacher_codes": len(
                unique_nonempty(
                    "teacher_code"
                )
            ),
            "subjects": len(
                unique_nonempty(
                    "subject"
                )
            ),
            "classes": len(
                unique_nonempty(
                    "class_name"
                )
            ),
            "rooms": len(
                unique_nonempty(
                    "room"
                )
            ),
            "groups": len(
                unique_nonempty(
                    "group_name"
                )
            ),
            "faculty_aliases": len(
                self.faculty_aliases
            ),
        }


# ==========================================================
# CONVENIENCE FUNCTION
# ==========================================================

def parse_pdf_records(
    records: Iterable[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:

    parser = PDFSemanticParser(
        records
    )

    return parser.parse_records(
        records
    )


# ==========================================================
# STANDALONE TEST
# ==========================================================

if __name__ == "__main__":

    print("=" * 80)

    print(
        "UNISCHED AI - PDF SEMANTIC PARSER TEST"
    )

    print("=" * 80)

    print()
    print(
        "This test does not modify project data."
    )

    print()

    parser = PDFSemanticParser()

    examples = [
        "Project/Spoken-Latex IAI 7CSA",
        "OS III 301 MKB",
        "WC JPV 5CSA",
        "SE&PM 301 ArS",
        "DE Lab 7F:EE-Lab13",
        "Audit Course SS APJ Seminar Hall RG",
    ]

    for example in examples:

        result = parser.parse_cell(
            example
        )

        print()
        print(
            f"INPUT: {example}"
        )

        print(
            f"  Subject      : "
            f"{result.get('subject', '')}"
        )

        print(
            f"  Teacher      : "
            f"{result.get('teacher', '')}"
        )

        print(
            f"  Teacher Code : "
            f"{result.get('teacher_code', '')}"
        )

        print(
            f"  Room         : "
            f"{result.get('room', '')}"
        )

        print(
            f"  Class        : "
            f"{result.get('class_name', '')}"
        )

        print(
            f"  Group        : "
            f"{result.get('group_name', '')}"
        )

    print()
    print("=" * 80)

    print(
        "SEMANTIC PARSER TEST COMPLETED"
    )

    print("=" * 80)