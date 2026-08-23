from database.knowledge_loader import KnowledgeLoader
from engine.phrase_generator import PhraseGenerator
from engine.universal_matcher import UniversalMatcher


class EntityExtractor:

    THRESHOLDS = {
        "teachers": 82,
        "subjects": 92,
        "rooms": 95,
        "classes": 95,
        "groups": 95
    }

    # Words that commonly appear in natural-language questions
    # but should NOT be treated as timetable entities.
    QUESTION_WORDS = {
        "who",
        "what",
        "which",
        "where",
        "when",
        "why",
        "how",
        "tell",
        "show",
        "give",
        "find",
        "please",
        "me",
        "is",
        "are",
        "the",
        "of",
        "for",
        "to",
        "from",
        "on",
        "at",
        "in",
        "and",
        "or",

        # Hinglish / Hindi conversational words
        "ka",
        "ke",
        "ki",
        "kya",
        "hai",
        "hain",
        "batao",
        "bataiye",
        "bataye",
        "sir",
        "madam",
        "maam",
        "ji"
    }

    def __init__(self):

        self.knowledge = KnowledgeLoader.load()

    # ---------------------------------------------------------
    # Remove conversational words
    # ---------------------------------------------------------

    @staticmethod
    def clean_tokens(tokens):

        cleaned = []

        for token in tokens:

            word = token.lower().strip()

            if not word:
                continue

            if word in EntityExtractor.QUESTION_WORDS:
                continue

            cleaned.append(word)

        return cleaned

    # ---------------------------------------------------------
    # Extract
    # ---------------------------------------------------------

    def extract(self, tokens):

        # First remove conversational/question words.
        cleaned_tokens = self.clean_tokens(tokens)

        if not cleaned_tokens:

            return {
                "teachers": [],
                "subjects": [],
                "rooms": [],
                "classes": [],
                "groups": []
            }

        phrases = PhraseGenerator.generate(
            cleaned_tokens,
            max_length=4
        )

        candidates = {
            "teachers": [],
            "subjects": [],
            "rooms": [],
            "classes": [],
            "groups": []
        }

        # -----------------------------------------------------
        # Generate candidates
        # -----------------------------------------------------

        for phrase in phrases:

            text = phrase["text"].strip()

            if len(text) < 3:
                continue

            for entity_type in candidates:

                threshold = self.THRESHOLDS[entity_type]

                result = UniversalMatcher.find_by_type(
                    text,
                    self.knowledge[entity_type],
                    threshold
                )

                if result is None:
                    continue

                candidates[entity_type].append({
                    "value": result["value"],
                    "confidence": result["confidence"],
                    "start": phrase["start"],
                    "end": phrase["end"],
                    "length": phrase["end"] - phrase["start"],
                    "text": text
                })

        # -----------------------------------------------------
        # Select best candidate for each type
        # -----------------------------------------------------

        entities = {
            "teachers": [],
            "subjects": [],
            "rooms": [],
            "classes": [],
            "groups": []
        }

        for entity_type, values in candidates.items():

            if not values:
                continue

            # Prefer:
            # 1. Highest confidence
            # 2. Longer phrase
            # 3. Earlier phrase
            values.sort(
                key=lambda x: (
                    -x["confidence"],
                    -x["length"],
                    x["start"]
                )
            )

            best = values[0]

            entities[entity_type].append({
                "value": best["value"],
                "confidence": best["confidence"]
            })

        return entities