import re


class QueryNormalizer:
    """
    Normalizes English + Hinglish natural-language queries.

    The goal is NOT to translate Hindi completely.
    It only removes common Hinglish conversational words
    and converts common query patterns into a form that
    the existing NLP pipeline can understand.
    """

    # ---------------------------------------------------------
    # COMMON HINGLISH / CONVERSATIONAL WORDS
    # ---------------------------------------------------------

    HINGLISH_WORDS = {
        "ka",
        "ke",
        "ki",
        "ko",
        "me",
        "mein",
        "mai",
        "par",
        "pe",
        "se",
        "hai",
        "hain",
        "kya",
        "kaun",
        "kon",
        "batao",
        "btao",
        "bataye",
        "bataiye",
        "dikhao",
        "dikhaye",
        "chahiye",
        "milega",
        "milega",
        "milenge",
        "kahan",
        "kaha",
        "kab",
        "kis",
        "kisne",
        "wala",
        "wale",
        "wali",
        "sir",
        "mam",
        "maam",
        "ji"
    }

    # ---------------------------------------------------------
    # WORD REPLACEMENTS
    #
    # These words are converted into English equivalents when
    # useful for intent detection.
    # ---------------------------------------------------------

    REPLACEMENTS = {

        # Hinglish → English

        "ka": "of",
        "ke": "of",
        "ki": "of",

        "kya": "what",
        "kaun": "who",
        "kon": "who",

        "batao": "show",
        "btao": "show",
        "bataye": "show",
        "bataiye": "show",

        "dikhao": "show",
        "dikhaye": "show",

        "kahan": "where",
        "kaha": "where",

        "kisne": "who",

        # Common spelling variations

        "timetable": "timetable",
        "time-table": "timetable",
        "time table": "timetable",

        "faculty": "faculty",
        "faculties": "faculty",

        "teachers": "teacher",
        "teaches": "teach"
    }

    # ---------------------------------------------------------
    # REMOVE COURTESY WORDS
    # ---------------------------------------------------------

    COURTESY_WORDS = {
        "sir",
        "mam",
        "maam",
        "ji"
    }

    # ---------------------------------------------------------
    # NORMALIZE
    # ---------------------------------------------------------

    @staticmethod
    def normalize(query):

        if not query:
            return ""

        # Lowercase
        query = query.lower().strip()

        # Remove punctuation except useful characters
        query = re.sub(
            r"[?!,;:]+",
            " ",
            query
        )

        # Normalize whitespace
        query = re.sub(
            r"\s+",
            " ",
            query
        ).strip()

        return query

    # ---------------------------------------------------------
    # CONVERT HINGLISH
    # ---------------------------------------------------------

    @staticmethod
    def normalize_hinglish(query):

        query = QueryNormalizer.normalize(query)

        if not query:
            return ""

        words = query.split()

        result = []

        for word in words:

            # Keep faculty names / entities.
            # Only replace known conversational words.
            replacement = QueryNormalizer.REPLACEMENTS.get(
                word
            )

            if replacement:

                result.append(replacement)

            else:

                result.append(word)

        return " ".join(result)

    # ---------------------------------------------------------
    # REMOVE CONVERSATIONAL WORDS
    # ---------------------------------------------------------

    @staticmethod
    def remove_hinglish_fillers(query):

        if not query:
            return ""

        words = query.split()

        result = []

        for word in words:

            if word in QueryNormalizer.HINGLISH_WORDS:
                continue

            result.append(word)

        return " ".join(result)

    # ---------------------------------------------------------
    # FINAL QUERY
    # ---------------------------------------------------------

    @staticmethod
    def process(query):

        query = QueryNormalizer.normalize(query)

        if not query:
            return ""

        query = QueryNormalizer.normalize_hinglish(query)

        return query.strip()