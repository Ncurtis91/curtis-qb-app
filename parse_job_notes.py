"""
parse_job_notes.py — Convert natural language job notes into structured estimate line items

Loads constants.json for pricing, calls Claude API to extract and price each item.
Returns a list of line items ready for create_estimate.py.

Usage:
    from parse_job_notes import parse_job_notes
    items, unknowns = parse_job_notes("180ft perimeter stucco 2 coats, pressure wash, 4 carriage lights")

    Standalone test:
    python parse_job_notes.py
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

CONSTANTS_FILE = Path(__file__).parent / "constants.json"
MODEL = "claude-haiku-4-5-20251001"  # fast + cheap for parsing


def _load_constants() -> dict:
    return json.loads(CONSTANTS_FILE.read_text())


def _build_system_prompt(constants: dict) -> str:
    return f"""You are an estimating assistant for Curtis Painting and Remodeling.

Your job is to parse natural language job notes and return a structured JSON list of line items for a customer-facing estimate.

## Pricing Constants
{json.dumps(constants, indent=2)}

## Rules
1. Apply constants silently — never ask about them, just calculate.
2. Sqft = perimeter × wall height. Use stated height; default to 9.5ft if not given.
3. Line item types:
   - "hourly": use when work is billed by time (labor tasks, repairs, prep work)
     Required fields: type, task (clear customer-facing description), hours (your best estimate)
   - "flat": use when there's a known constant price or an explicit price stated
     Required fields: type, description (clear customer-facing description), amount
4. Material costs are NEVER shown to the customer — absorbed internally. Do not include them as line items.
5. Stucco is ALWAYS priced as a single application (spray and backroll). Never assume or add a second coat — ignore any mention of "2 coats" unless a "color change" item is explicitly present (not yet defined). Customer description is always "Exterior painting - stucco".
6. If a quantity isn't stated for a flat-rate item, assume 1.
7. If something cannot be priced from constants and no price was given, add it to the "unknowns" list with a note.
8. Descriptions should be clean and professional (suitable for a customer to read).

## Output Format
Return ONLY valid JSON in this exact structure — no explanation, no markdown:
{{
  "customer": "name if mentioned, else null",
  "line_items": [
    {{"type": "flat", "description": "Exterior painting - stucco, 2 coats", "amount": 2821.50}},
    {{"type": "flat", "description": "Pressure wash", "amount": 400.00}},
    {{"type": "flat", "description": "Carriage light service (4)", "amount": 400.00}},
    {{"type": "hourly", "task": "Remove caulk from 2 windows", "hours": 4}}
  ],
  "unknowns": [
    "Trim color not specified — confirm before finalizing"
  ],
  "internal_notes": "Stucco: 180ft x 9.5ft = 1710 sqft @ $1.65 = $2,821.50. Pressure wash included."
}}"""


def parse_job_notes(notes: str) -> tuple[list[dict], list[str]]:
    """
    Parse natural language job notes into line items.

    Returns:
        (line_items, unknowns)
        line_items — list of dicts ready for create_estimate()
        unknowns   — list of strings describing items that couldn't be priced
    """
    constants = _load_constants()
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_build_system_prompt(constants),
        messages=[{"role": "user", "content": notes}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed = json.loads(raw)
    return parsed.get("line_items", []), parsed.get("unknowns", []), parsed.get("customer"), parsed.get("internal_notes", "")


def preview_estimate(notes: str) -> None:
    """Print a formatted preview of the parsed estimate — for confirmation before pushing to QBO."""
    print(f"\nParsing: \"{notes}\"\n")

    line_items, unknowns, customer, internal_notes = parse_job_notes(notes)

    if customer:
        print(f"  Customer: {customer}")
    print()

    total = 0.0
    print("  LINE ITEMS (customer-facing):")
    print("  " + "-" * 50)
    for item in line_items:
        if item["type"] == "hourly":
            from create_estimate import LABOR_RATE
            amount = item["hours"] * LABOR_RATE
            total += amount
            print(f"  [hourly] {item['task']}")
            print(f"           Est - {item['hours']} hrs × ${LABOR_RATE:.0f}/hr = ${amount:.2f}")
        else:
            total += item["amount"]
            print(f"  [flat]   {item['description']} — ${item['amount']:,.2f}")

    print("  " + "-" * 50)
    print(f"  TOTAL: ${total:,.2f}\n")

    if internal_notes:
        print(f"  Internal: {internal_notes}\n")

    if unknowns:
        print("  NEEDS CLARIFICATION:")
        for u in unknowns:
            print(f"    ? {u}")
        print()


# --- Standalone test ---

if __name__ == "__main__":
    tests = [
        "Smith job. 180ft perimeter stucco 2 coats, pressure wash, 4 carriage lights, 2 side doors, shutters x6",
        "Jones exterior. 220ft perimeter stucco, soffit and fascia with gutters 180ft, 2 car garage, front door",
        "rust spots 2hrs labor to oil prime, 2 windows need caulk scraped and redone 4hrs",
    ]

    for notes in tests:
        preview_estimate(notes)
        print("=" * 60)
