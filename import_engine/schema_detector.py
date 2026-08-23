"""
UNISCHED AI - Universal Schema / Dataset Detector

Automatically determines what kind of timetable-related dataset
has been imported.

Supported dataset types:

    TIMETABLE
        Actual scheduled timetable events containing Day + Slot
        and usually Teacher / Subject / Class / Room.

    CONTRACT
        Contract/class planning information such as:
            Teacher
            Subject
            Group
            Class
            Length
            Lessons/week
            Available classrooms
            Cycle
            Classrooms

        These records may legitimately have no Day or Slot.

    MIXED
        Dataset contains a mixture of scheduled and unscheduled
        records.

    UNKNOWN
        Dataset does not contain enough recognizable information.

This module does NOT modify imported records.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional


class SchemaDetector:
    """
    Detect the semantic type of imported timetable data.
    """

    TIMETABLE = "TIMETABLE"
    CONTRACT = "CONTRACT"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"

    # Common aliases used by different universities / software.
    FIELD_ALIASES = {
        "day": {
            "day",
            "date_day",
            "weekday",
            "week_day",
            "week day",
        },
        "slot": {
            "slot",
            "period",
            "period_no",
            "period_number",
            "slot_no",
            "slot_number",
            "lecture_no",
            "lecture_number",
        },
        "slot_time": {
            "slot_time",
            "time",
            "time_slot",
            "timing",
            "time_range",
            "period_time",
        },
        "teacher": {
            "teacher",
            "faculty",
            "faculty_name",
            "teacher_name",
            "professor",
            "instructor",
            "staff",
        },
        "subject": {
            "subject",
            "subject_name",
            "course",
            "course_name",
            "paper",
            "module",
        },
        "class_name": {
            "class",
            "class_name",
            "classroom_group",
            "section",
            "batch",
            "class_section",
        },
        "group_name": {
            "group",
            "group_name",
            "student_group",
            "lab_group",
        },
        "room": {
            "room",
            "room_name",
            "room_no",
            "room_number",
            "classroom",
            "classrooms",
            "location",
            "venue",
        },
        "lessons_per_week": {
            "lessons/week",
            "lessons_per_week",
            "lessons per week",
            "lectures/week",
            "lectures_per_week",
            "periods/week",
            "periods_per_week",
        },
        "length": {
            "length",
            "duration",
            "class_length",
            "period_length",
        },
        "available_classrooms": {
            "available classrooms",
            "available_classrooms",
            "available_rooms",
            "available_rooms",
        },
        "cycle": {
            "cycle",
            "week_cycle",
            "schedule_cycle",
        },
    }

    CONTRACT_FIELDS = {
        "lessons_per_week",
        "length",
        "available_classrooms",
        "cycle",
    }

    CORE_TIMETABLE_FIELDS = {
        "day",
        "slot",
    }

    SECONDARY_TIMETABLE_FIELDS = {
        "teacher",
        "subject",
        "class_name",
        "group_name",
        "room",
        "slot_time",
    }

    @staticmethod
    def _clean_key(value: Any) -> str:
        """
        Normalize a field name for comparison.
        """
        if value is None:
            return ""

        text = str(value).strip().lower()

        replacements = {
            "-": "_",
            "/": "_",
            ".": "",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = " ".join(text.split())

        return text

    @classmethod
    def canonical_field(cls, field_name: Any) -> Optional[str]:
        """
        Convert an arbitrary source column name into a canonical field.

        Examples:
            "Teacher Name" -> teacher
            "Lessons/week" -> lessons_per_week
            "Classrooms" -> room
            "Period No." -> slot
        """

        key = cls._clean_key(field_name)

        if not key:
            return None

        # Direct normalized aliases.
        for canonical, aliases in cls.FIELD_ALIASES.items():

            normalized_aliases = {
                cls._clean_key(alias)
                for alias in aliases
            }

            if key in normalized_aliases:
                return canonical

        # Additional fuzzy matching.
        compact = key.replace("_", "").replace(" ", "")

        if compact in {
            "teacher",
            "teachername",
            "faculty",
            "facultyname",
            "professor",
            "instructor",
        }:
            return "teacher"

        if compact in {
            "subject",
            "subjectname",
            "course",
            "coursename",
            "paper",
        }:
            return "subject"

        if compact in {
            "day",
            "weekday",
            "week_day",
        }:
            return "day"

        if compact in {
            "slot",
            "slotno",
            "slotnumber",
            "period",
            "periodno",
            "periodnumber",
        }:
            return "slot"

        if compact in {
            "time",
            "slottime",
            "timeslot",
            "timing",
        }:
            return "slot_time"

        if compact in {
            "class",
            "classname",
            "section",
            "batch",
        }:
            return "class_name"

        if compact in {
            "group",
            "groupname",
            "studentgroup",
            "labgroup",
        }:
            return "group_name"

        if compact in {
            "room",
            "roomno",
            "roomnumber",
            "roomname",
            "venue",
            "location",
        }:
            return "room"

        if compact in {
            "classrooms",
        }:
            return "room"

        if compact in {
            "length",
            "duration",
            "classlength",
        }:
            return "length"

        if compact in {
            "lessonsweek",
            "lessonsperweek",
            "lecturesweek",
            "lecturesperweek",
            "periodsweek",
            "periodsperweek",
        }:
            return "lessons_per_week"

        if compact in {
            "availableclassrooms",
            "availablerooms",
        }:
            return "available_classrooms"

        if compact in {
            "cycle",
            "weekcycle",
            "schedulecycle",
        }:
            return "cycle"

        return None

    @staticmethod
    def _has_value(value: Any) -> bool:
        """
        Determine whether a field contains meaningful data.
        """

        if value is None:
            return False

        if isinstance(value, str):
            text = value.strip().lower()

            if text in {
                "",
                "-",
                "--",
                "na",
                "n/a",
                "nan",
                "none",
                "null",
                "nil",
                "_",
            }:
                return False

        return True

    @classmethod
    def normalize_record_keys(
        cls,
        record: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert source-specific keys into canonical semantic keys.

        Unknown keys are ignored for detection but preserved separately
        by the importer itself.
        """

        normalized: Dict[str, Any] = {}

        for key, value in record.items():

            canonical = cls.canonical_field(key)

            if canonical is None:
                continue

            # If multiple source fields map to the same canonical field,
            # prefer the first meaningful value.
            if canonical not in normalized:
                normalized[canonical] = value
            elif not cls._has_value(normalized[canonical]):
                normalized[canonical] = value

        return normalized

    @classmethod
    def analyze_records(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze imported records and determine their dataset type.

        Returns a detailed diagnostic dictionary.
        """

        records = list(records)

        total = len(records)

        if total == 0:
            return {
                "dataset_type": cls.UNKNOWN,
                "confidence": 0.0,
                "total_records": 0,
                "fields": [],
                "canonical_fields": [],
                "statistics": {},
                "warnings": [
                    "Dataset contains no records."
                ],
                "reason": "No records available for analysis.",
            }

        normalized_records = [
            cls.normalize_record_keys(record)
            for record in records
        ]

        canonical_fields = set()

        for record in normalized_records:
            canonical_fields.update(record.keys())

        field_statistics: Dict[str, Dict[str, Any]] = {}

        for field in sorted(canonical_fields):

            populated = sum(
                1
                for record in normalized_records
                if cls._has_value(record.get(field))
            )

            percentage = (
                populated / total * 100
                if total
                else 0
            )

            field_statistics[field] = {
                "records_with_value": populated,
                "records_without_value": total - populated,
                "percentage": round(percentage, 2),
            }

        day_count = field_statistics.get(
            "day",
            {}
        ).get("records_with_value", 0)

        slot_count = field_statistics.get(
            "slot",
            {}
        ).get("records_with_value", 0)

        time_count = field_statistics.get(
            "slot_time",
            {}
        ).get("records_with_value", 0)

        teacher_count = field_statistics.get(
            "teacher",
            {}
        ).get("records_with_value", 0)

        subject_count = field_statistics.get(
            "subject",
            {}
        ).get("records_with_value", 0)

        class_count = field_statistics.get(
            "class_name",
            {}
        ).get("records_with_value", 0)

        group_count = field_statistics.get(
            "group_name",
            {}
        ).get("records_with_value", 0)

        room_count = field_statistics.get(
            "room",
            {}
        ).get("records_with_value", 0)

        contract_score = 0

        for field in cls.CONTRACT_FIELDS:

            count = field_statistics.get(
                field,
                {}
            ).get("records_with_value", 0)

            if count > 0:
                contract_score += 1

        # ------------------------------------------------------------
        # Determine scheduled-record population.
        # ------------------------------------------------------------

        scheduled_records = 0

        for record in normalized_records:

            has_day = cls._has_value(
                record.get("day")
            )

            has_slot = cls._has_value(
                record.get("slot")
            )

            has_time = cls._has_value(
                record.get("slot_time")
            )

            # A real timetable record normally has Day + Slot.
            # Some formats have Day + Time instead of numeric Slot.
            if (
                (has_day and has_slot)
                or
                (has_day and has_time)
            ):
                scheduled_records += 1

        scheduled_percentage = (
            scheduled_records / total * 100
        )

        # ------------------------------------------------------------
        # Determine contract-record population.
        # ------------------------------------------------------------

        contract_records = 0

        for record in normalized_records:

            has_teacher = cls._has_value(
                record.get("teacher")
            )

            has_subject = cls._has_value(
                record.get("subject")
            )

            has_contract_field = any(
                cls._has_value(record.get(field))
                for field in cls.CONTRACT_FIELDS
            )

            has_no_schedule = not (
                cls._has_value(record.get("day"))
                or cls._has_value(record.get("slot"))
                or cls._has_value(record.get("slot_time"))
            )

            if (
                has_teacher
                and has_subject
                and has_contract_field
                and has_no_schedule
            ):
                contract_records += 1

        contract_percentage = (
            contract_records / total * 100
        )

        # ------------------------------------------------------------
        # Classification.
        # ------------------------------------------------------------

        warnings: List[str] = []

        if day_count == 0:
            warnings.append(
                "Dataset does not contain Day information."
            )

        if slot_count == 0 and time_count == 0:
            warnings.append(
                "Dataset does not contain Slot or time information."
            )

        if (
            day_count == total
            and slot_count == total
        ):
            dataset_type = cls.TIMETABLE
            confidence = 0.98

            reason = (
                "Records consistently contain Day and Slot "
                "information."
            )

        elif (
            scheduled_percentage >= 80
            and (
                day_count > 0
                or slot_count > 0
                or time_count > 0
            )
        ):
            dataset_type = cls.TIMETABLE
            confidence = min(
                0.95,
                0.70 + scheduled_percentage / 400
            )

            reason = (
                "Most records contain timetable scheduling "
                "information."
            )

        elif (
            contract_percentage >= 60
            and scheduled_percentage < 20
        ):
            dataset_type = cls.CONTRACT
            confidence = min(
                0.97,
                0.65 + contract_percentage / 300
            )

            reason = (
                "Records contain contract/class planning "
                "fields but lack Day and Slot scheduling."
            )

        elif (
            scheduled_records > 0
            and contract_records > 0
        ):
            dataset_type = cls.MIXED
            confidence = 0.85

            reason = (
                "Dataset contains both scheduled timetable "
                "records and unscheduled contract/class records."
            )

        elif (
            day_count > 0
            or slot_count > 0
            or time_count > 0
        ):
            dataset_type = cls.MIXED
            confidence = 0.65

            reason = (
                "Dataset contains some scheduling information "
                "but its structure is inconsistent."
            )

        else:
            dataset_type = cls.UNKNOWN
            confidence = 0.30

            reason = (
                "Dataset does not contain enough recognizable "
                "timetable or contract information."
            )

        # Additional warnings.
        if day_count < total and day_count > 0:
            warnings.append(
                f"Only {day_count}/{total} records contain Day information."
            )

        if slot_count < total and slot_count > 0:
            warnings.append(
                f"Only {slot_count}/{total} records contain Slot information."
            )

        if (
            dataset_type == cls.CONTRACT
            and day_count == 0
            and slot_count == 0
        ):
            warnings.append(
                "This appears to be a contract/class dataset, "
                "not an actual timetable schedule."
            )

        return {
            "dataset_type": dataset_type,
            "confidence": round(confidence, 3),
            "total_records": total,

            "fields": sorted(
                {
                    str(key)
                    for record in records
                    for key in record.keys()
                }
            ),

            "canonical_fields": sorted(
                canonical_fields
            ),

            "statistics": {
                "day_records": day_count,
                "slot_records": slot_count,
                "slot_time_records": time_count,
                "teacher_records": teacher_count,
                "subject_records": subject_count,
                "class_records": class_count,
                "group_records": group_count,
                "room_records": room_count,

                "scheduled_records": scheduled_records,
                "scheduled_percentage": round(
                    scheduled_percentage,
                    2,
                ),

                "contract_records": contract_records,
                "contract_percentage": round(
                    contract_percentage,
                    2,
                ),

                "contract_field_count": contract_score,
            },

            "warnings": warnings,

            "reason": reason,
        }

    @classmethod
    def detect(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> str:
        """
        Simple API.

        Returns only the dataset type.
        """

        result = cls.analyze_records(records)

        return result["dataset_type"]

    @classmethod
    def is_timetable(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> bool:
        """
        Return True if the dataset is classified as TIMETABLE.
        """

        return cls.detect(records) == cls.TIMETABLE

    @classmethod
    def is_contract(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> bool:
        """
        Return True if the dataset is classified as CONTRACT.
        """

        return cls.detect(records) == cls.CONTRACT

    @classmethod
    def is_mixed(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> bool:
        """
        Return True if the dataset is classified as MIXED.
        """

        return cls.detect(records) == cls.MIXED

    @classmethod
    def print_report(
        cls,
        records: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Print a human-readable dataset analysis report.

        Returns the same dictionary generated by analyze_records().
        """

        result = cls.analyze_records(records)

        print("=" * 80)
        print("UNISCHED AI - UNIVERSAL DATASET DETECTOR")
        print("=" * 80)

        print(
            f"Dataset type : {result['dataset_type']}"
        )

        print(
            f"Confidence   : "
            f"{result['confidence'] * 100:.1f}%"
        )

        print(
            f"Records      : "
            f"{result['total_records']}"
        )

        print()
        print("CANONICAL FIELDS")
        print("-" * 80)

        for field in result["canonical_fields"]:
            print(f"  ✓ {field}")

        print()
        print("STATISTICS")
        print("-" * 80)

        stats = result["statistics"]

        for key, value in stats.items():
            print(
                f"  {key:<25}: {value}"
            )

        print()
        print("REASON")
        print("-" * 80)

        print(
            f"  {result['reason']}"
        )

        if result["warnings"]:

            print()
            print("WARNINGS")
            print("-" * 80)

            for warning in result["warnings"]:
                print(
                    f"  ! {warning}"
                )

        else:

            print()
            print("WARNINGS")
            print("-" * 80)
            print("  None")

        print()
        print("=" * 80)

        return result


if __name__ == "__main__":

    print(
        "SchemaDetector module loaded successfully."
    )

    print(
        "Use SchemaDetector.analyze_records(records)"
    )