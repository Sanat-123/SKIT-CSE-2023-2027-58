from rapidfuzz import process, fuzz

from engine.normalizer import Normalizer


class UniversalMatcher:
    """
    Universal Entity Matcher

    Features:
    ----------
    1. Exact matching
    2. Normalized matching
    3. Prefix matching
    4. Fuzzy matching
    5. Handles titles such as:
           Dr
           Dr.
           Mr
           Mr.
           Ms
           Ms.
           Sir
           Madam
    6. Handles common spelling mistakes
           mehul maharshi
           mehul maharsi
           mehul mahrishi
    7. Handles partial teacher names
           mehul
           mehul sir
           mehul maharshi sir
    8. Prevents bad fuzzy matches for very short queries
    9. Supports Unicode/Hindi text without incorrectly mapping it
    """

    # ---------------------------------------------------------
    # TITLE / COURTESY WORDS
    # ---------------------------------------------------------

    TITLES = {
        "dr",
        "dr.",
        "mr",
        "mr.",
        "mrs",
        "mrs.",
        "ms",
        "ms.",
        "prof",
        "prof.",
        "sir",
        "madam",
        "mam",
        "maam"
    }

    # ---------------------------------------------------------
    # COMMON WORDS THAT SHOULD NOT PARTICIPATE IN ENTITY
    # MATCHING
    # ---------------------------------------------------------

    IGNORE_WORDS = {
        "sir",
        "madam",
        "mam",
        "maam",
        "teacher",
        "faculty",
        "professor",
        "prof",
        "ji"
    }

    # ---------------------------------------------------------
    # PUBLIC METHOD
    # ---------------------------------------------------------

    @staticmethod
    def find(query, knowledge, threshold=85):

        if not query:
            return None

        best = None

        for entity_type, entities in knowledge.items():

            result = UniversalMatcher.find_by_type(
                query,
                entities,
                threshold
            )

            if result is None:
                continue

            if (
                best is None
                or result["confidence"] > best["confidence"]
            ):
                best = {
                    "type": entity_type,
                    "value": result["value"],
                    "confidence": result["confidence"]
                }

        return best

    # ---------------------------------------------------------
    # REMOVE TITLES / COURTESY WORDS
    # ---------------------------------------------------------

    @staticmethod
    def clean_query(query):

        if not query:
            return ""

        words = query.strip().split()

        cleaned = []

        for word in words:

            normalized = word.lower().strip(".,!?")

            if normalized in UniversalMatcher.TITLES:
                continue

            if normalized in UniversalMatcher.IGNORE_WORDS:
                continue

            cleaned.append(word)

        return " ".join(cleaned)

    # ---------------------------------------------------------
    # CHECK IF TEXT CONTAINS UNICODE
    # ---------------------------------------------------------

    @staticmethod
    def contains_non_ascii(text):

        if not text:
            return False

        return any(ord(ch) > 127 for ch in text)

    # ---------------------------------------------------------
    # BASIC NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_query(query):

        if not query:
            return ""

        query = UniversalMatcher.clean_query(query)

        if not query:
            return ""

        return Normalizer.normalize_for_match(query)

    # ---------------------------------------------------------
    # TOKEN NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def normalize_tokens(text):

        normalized = UniversalMatcher.normalize_query(text)

        if not normalized:
            return []

        return normalized.split()

    # ---------------------------------------------------------
    # TOKEN OVERLAP
    # ---------------------------------------------------------

    @staticmethod
    def token_similarity(query, entity):

        query_tokens = UniversalMatcher.normalize_tokens(query)
        entity_tokens = UniversalMatcher.normalize_tokens(entity)

        if not query_tokens or not entity_tokens:
            return 0

        scores = []

        for q in query_tokens:

            best_score = 0

            for e in entity_tokens:

                score = fuzz.ratio(q, e)

                if score > best_score:
                    best_score = score

            scores.append(best_score)

        return sum(scores) / len(scores)

    # ---------------------------------------------------------
    # EXACT TOKEN MATCH
    # ---------------------------------------------------------

    @staticmethod
    def all_query_tokens_present(query, entity):

        query_tokens = UniversalMatcher.normalize_tokens(query)
        entity_tokens = UniversalMatcher.normalize_tokens(entity)

        if not query_tokens:
            return False

        if not entity_tokens:
            return False

        for q in query_tokens:

            matched = False

            for e in entity_tokens:

                if q == e:
                    matched = True
                    break

                # Small spelling error
                if fuzz.ratio(q, e) >= 88:
                    matched = True
                    break

            if not matched:
                return False

        return True

    # ---------------------------------------------------------
    # MAIN MATCHER
    # ---------------------------------------------------------

    @staticmethod
    def find_by_type(query, entities, threshold=88):

        if not query or not entities:
            return None

        query = query.strip()

        # -----------------------------------------------------
        # IMPORTANT:
        # Do NOT perform ASCII fuzzy matching on Hindi/Unicode.
        #
        # This prevents:
        #
        #     मेहुल -> Lata Lalit
        #
        # which was happening previously.
        #
        # -----------------------------------------------------

        query_has_unicode = UniversalMatcher.contains_non_ascii(query)

        # -----------------------------------------------------
        # CLEAN QUERY
        # -----------------------------------------------------

        cleaned_query = UniversalMatcher.clean_query(query)

        if not cleaned_query:
            return None

        # -----------------------------------------------------
        # BUILD NORMALIZED ENTITY LOOKUP
        # -----------------------------------------------------

        normalized_entities = {}

        for entity in entities:

            normalized = UniversalMatcher.normalize_query(entity)

            if normalized:
                normalized_entities[normalized] = entity

        # -----------------------------------------------------
        # NORMALIZE USER QUERY
        # -----------------------------------------------------

        normalized_query = UniversalMatcher.normalize_query(
            cleaned_query
        )

        if not normalized_query:
            return None

        # -----------------------------------------------------
        # STEP 1
        # EXACT MATCH
        # -----------------------------------------------------

        if normalized_query in normalized_entities:

            return {
                "value": normalized_entities[normalized_query],
                "confidence": 100.0
            }

        # -----------------------------------------------------
        # STEP 2
        # PREFIX MATCH
        #
        # Example:
        #
        # mehul
        #
        # matches:
        #
        # Dr. Mehul Mahrishi
        # -----------------------------------------------------

        prefix_matches = []

        for normalized, original in normalized_entities.items():

            if normalized.startswith(normalized_query):

                prefix_matches.append(original)

        if len(prefix_matches) == 1:

            return {
                "value": prefix_matches[0],
                "confidence": 98.0
            }

        elif len(prefix_matches) > 1:

            # Prefer the shortest entity.
            best = min(prefix_matches, key=len)

            return {
                "value": best,
                "confidence": 97.0
            }

        # -----------------------------------------------------
        # STEP 3
        # TOKEN BASED MATCH
        #
        # Example:
        #
        # mehul maharshi
        #
        # should match:
        #
        # Dr. Mehul Mahrishi
        #
        # even though spelling is slightly different.
        # -----------------------------------------------------

        best_entity = None
        best_score = 0

        for entity in entities:

            score = UniversalMatcher.token_similarity(
                cleaned_query,
                entity
            )

            if score > best_score:

                best_score = score
                best_entity = entity

        # Strong token match
        if best_entity is not None:

            # Require stronger confidence for short queries.
            query_tokens = UniversalMatcher.normalize_tokens(
                cleaned_query
            )

            if len(query_tokens) == 1:

                if len(query_tokens[0]) < 4:

                    minimum_score = 95

                else:

                    minimum_score = 90

            else:

                minimum_score = 86

            if best_score >= minimum_score:

                return {
                    "value": best_entity,
                    "confidence": round(best_score, 2)
                }

        # -----------------------------------------------------
        # STEP 4
        # FUZZY MATCH
        # -----------------------------------------------------

        # Do not fuzzy-match Unicode queries against English
        # entity names.
        #
        # Otherwise Hindi words may accidentally become English
        # teacher names.
        #
        if query_has_unicode:

            return None

        # -----------------------------------------------------
        # FUZZY MATCH USING RAPIDFUZZ
        # -----------------------------------------------------

        fuzzy = process.extractOne(
            normalized_query,
            normalized_entities.keys(),
            scorer=fuzz.WRatio,
            score_cutoff=threshold
        )

        if fuzzy:

            normalized_value = fuzzy[0]

            score = fuzzy[1]

            # Additional protection against bad short matches.
            query_length = len(
                normalized_query.replace(" ", "")
            )

            if query_length <= 3 and score < 96:

                return None

            if query_length <= 5 and score < 90:

                return None

            return {
                "value": normalized_entities[normalized_value],
                "confidence": round(score, 2)
            }

        return None

    # ---------------------------------------------------------
    # FIND ALL
    # ---------------------------------------------------------

    @staticmethod
    def find_all(tokens, knowledge, threshold=85):

        results = {}

        for token in tokens:

            entity = UniversalMatcher.find(
                token,
                knowledge,
                threshold
            )

            if entity is None:
                continue

            entity_type = entity["type"]

            if entity_type not in results:

                results[entity_type] = []

            # Prevent duplicates
            already_exists = any(
                item["value"] == entity["value"]
                for item in results[entity_type]
            )

            if not already_exists:

                results[entity_type].append(entity)

        return results