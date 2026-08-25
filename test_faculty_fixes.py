from faculty_chatbot import FacultyAIChatbot

bot = FacultyAIChatbot()
e = bot.query_engine

print("\n=== 1. DIRECT NAME VARIANTS ===")
for name in [
    "Mr. Nitin Goyal",
    "Mr.Nitin Goyal",
    "Mr Nitin Goyal",
    "Nitin Goyal",
]:
    result = e.faculty_status(name, "Monday", 2)
    print(f"{name!r} -> {result.get('status')}")

print("\n=== 2. SPECIFIC FACULTY TIME RANGE ===")
queries = [
    "Is Mr. Nitin Goyal free on Monday from 9:15 to 11:15?",
    "Is Mr.Nitin Goyal free on Monday from 9:15 to 11:15?",
    "Is Mr Nitin Goyal free on Monday from 9:15 to 11:15?",
    "Is Nitin Goyal free on Monday from 9:15 to 11:15?",
]
for q in queries:
    print(f"\nQUERY: {q}")
    print(bot.process_query(q))

print("\n=== 3. GENERAL FACULTY TIME RANGE ===")
q = "Who is free on Monday from 9:15 to 11:15?"
print(f"QUERY: {q}")
print(bot.process_query(q))

print("\n=== 4. DIRECT PERIOD ENGINE ===")
print(e.faculty_status_for_period(
    "Mr. Nitin Goyal", "Monday", "09:15", "11:15"
))