"""
Safe, self-verifying patch for the confirmed faculty_free ->
faculty_free_slots method-name bug.

Does NOT touch query_engine.py, app.py, pdf_importer.py, or
canonical_event_matcher.py.

Refuses to make any change unless the exact expected block is
found exactly once in the file, so it cannot accidentally touch
"faculty_free_for_period", the "faculty_free" intent-name string
used elsewhere in the file, or anything else.

Run from your project root:

    python fix_faculty_free_slots.py
"""

import sys

PATH = "query_engine/natural_language_query.py"

OLD_BLOCK = (
    "self.call_engine_method(\n"
    "            \"faculty_free\",\n"
    "            day=day,\n"
    "            slot=slot\n"
    "        )"
)

NEW_BLOCK = (
    "self.call_engine_method(\n"
    "            \"faculty_free_slots\",\n"
    "            day=day,\n"
    "            slot=slot\n"
    "        )"
)

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

count = content.count(OLD_BLOCK)

if count == 0:
    print("PATTERN NOT FOUND.")
    print(
        "Your file's exact whitespace/indentation may differ "
        "slightly from what was pasted earlier. No changes "
        "made. Please show me the surrounding lines so I can "
        "adjust the pattern precisely, or apply the one-line "
        "change by hand: change the string \"faculty_free\" to "
        "\"faculty_free_slots\" ONLY inside the "
        "self.call_engine_method(...) call in "
        "execute_faculty_free() -- do not change any other "
        "occurrence of \"faculty_free\" in the file."
    )
    sys.exit(1)

if count > 1:
    print(
        f"SAFETY STOP: pattern found {count} times, expected "
        f"exactly 1. Refusing to change anything automatically "
        f"to avoid an unintended edit. Please show me the file "
        f"so I can pinpoint the exact one to change."
    )
    sys.exit(1)

content = content.replace(OLD_BLOCK, NEW_BLOCK)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Fix applied: exactly 1 occurrence changed.")
print('  "faculty_free"  ->  "faculty_free_slots"')
print("Nothing else in the file was modified.")