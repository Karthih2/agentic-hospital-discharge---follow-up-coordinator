"""Live model test: real extraction + real rewrite on the PRD sample, through the production code paths."""
import asyncio

from app.pipeline import extraction_agent, simplify_agent

SUMMARY = """Discharge date: 02 Nov 2026
1. Follow up with cardiologist in 2 weeks.
2. Tab. Metformin 500 mg twice daily for 30 days after food.
3. Fasting blood sugar test on Day 7.
4. Change wound dressing every 48 hours.
5. Seek immediate care if chest pain or breathlessness occurs.
6. Tab. Aspirin once daily. Continue as advised.
"""


async def main():
    out = await extraction_agent.extract(SUMMARY)
    print(f"extracted {len(out.items)} items, rejected {len(out.rejected)}")
    for i in out.items:
        print(" ", i.type, "|", i.source_line, "|", i.due_date_text, "|", i.confidence)
    care = next(i for i in out.items if i.type in ("care_instruction", "appointment"))
    simple, tr = await simplify_agent.simplify(care.source_line, "en")
    print("simple:", simple)
    print("translations:", tr)


asyncio.run(main())
