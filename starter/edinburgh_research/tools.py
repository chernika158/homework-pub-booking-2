"""Ex5 tools. Four tools the agent uses to research an Edinburgh booking.

Each tool:
  1. Reads its fixture from sample_data/ (DO NOT modify the fixtures).
  2. Logs its arguments and output into _TOOL_CALL_LOG (see integrity.py).
  3. Returns a ToolResult with success=True/False, output=dict, summary=str.

The grader checks for:
  * Correct parallel_safe flags (reads True, generate_flyer False).
  * Every tool's results appear in _TOOL_CALL_LOG.
  * Tools fail gracefully on missing fixtures or bad inputs (ToolError,
    not RuntimeError).
"""

from __future__ import annotations

import json
from pathlib import Path

from sovereign_agent.tools.registry import ToolError
from starter.edinburgh_research.integrity import record_tool_call

from sovereign_agent.session.directory import Session
from sovereign_agent.tools.registry import ToolRegistry, ToolResult, _RegisteredTool

_SAMPLE_DATA = Path(__file__).parent / "sample_data"


# ---------------------------------------------------------------------------
# TODO 1 — venue_search  ✓
# ---------------------------------------------------------------------------
def venue_search(near: str, party_size: int, budget_max_gbp: int = 1000) -> ToolResult:
    """Search for Edinburgh venues near <near> that can seat the party.

    Reads sample_data/venues.json. Filters by:
      * open_now == True
      * area contains <near> (case-insensitive substring match)
      * seats_available_evening >= party_size
      * hire_fee_gbp + min_spend_gbp <= budget_max_gbp

    Returns a ToolResult with:
      output: {"near": ..., "party_size": ..., "results": [<venue dicts>], "count": int}
      summary: "venue_search(<near>, party=<N>): <count> result(s)"

    MUST call record_tool_call(...) before returning so the integrity
    check can see what data was produced.
    """
    fixture = _SAMPLE_DATA / "venues.json"
    if not fixture.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"venues.json not found at {fixture}")

    venues = json.loads(fixture.read_text())

    results = [
        v for v in venues
        if v.get("open_now") is True
        and near.lower() in v.get("area", "").lower()
        and v.get("seats_available_evening", 0) >= party_size
        and (v.get("hire_fee_gbp", 0) + v.get("min_spend_gbp", 0)) <= budget_max_gbp
    ]

    output = {
        "near": near,
        "party_size": party_size,
        "results": results,
        "count": len(results),
    }
    record_tool_call(
        "venue_search",
        {"near": near, "party_size": party_size, "budget_max_gbp": budget_max_gbp},
        output,
    )
    return ToolResult(
        success=True,
        output=output,
        summary=f"venue_search({near}, party={party_size}): {len(results)} result(s)",
    )


# ---------------------------------------------------------------------------
# TODO 2 — get_weather  ✓
# ---------------------------------------------------------------------------
def get_weather(city: str, date: str) -> ToolResult:
    """Look up the scripted weather for <city> on <date> (YYYY-MM-DD).

    Reads sample_data/weather.json. Returns:
      output: {"city": str, "date": str, "condition": str, "temperature_c": int, ...}
      summary: "get_weather(<city>, <date>): <condition>, <temp>C"

    If the city or date is not in the fixture, return success=False with
    a clear ToolError (SA_TOOL_INVALID_INPUT). Do NOT raise.

    MUST call record_tool_call(...) before returning.
    """
    fixture = _SAMPLE_DATA / "weather.json"
    if not fixture.exists():
        raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"weather.json not found at {fixture}")

    data = json.loads(fixture.read_text())
    args = {"city": city, "date": date}

    # weather.json keys are lowercase (e.g. "edinburgh", "glasgow")
    city_data = data.get(city) or data.get(city.lower())
    if city_data is None:
        output = {"error": f"City '{city}' not in fixture"}
        record_tool_call("get_weather", args, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"get_weather({city}, {date}): city not found",
        )

    day = city_data.get(date)
    if day is None:
        output = {"error": f"Date '{date}' not found for {city}"}
        record_tool_call("get_weather", args, output)
        return ToolResult(
            success=False,
            output=output,
            summary=f"get_weather({city}, {date}): date not found",
        )

    # Spread the full day dict so all fields (precip_mm, wind_kph, …) are logged
    output = {"city": city, "date": date, **day}
    record_tool_call("get_weather", args, output)
    return ToolResult(
        success=True,
        output=output,
        summary=f"get_weather({city}, {date}): {day['condition']}, {day['temperature_c']}C",
    )


# ---------------------------------------------------------------------------
# TODO 3 — calculate_cost  ✓
# ---------------------------------------------------------------------------
def calculate_cost(
    venue_id: str,
    party_size: int,
    duration_hours: int,
    catering_tier: str = "bar_snacks",
) -> ToolResult:
    """Compute the total cost for a booking.

    Formula:
      base_per_head = base_rates_gbp_per_head[catering_tier]
      venue_mult    = venue_modifiers[venue_id]
      subtotal      = base_per_head * venue_mult * party_size * max(1, duration_hours)
      service       = subtotal * service_charge_percent / 100
      total         = subtotal + service + venue's (hire_fee_gbp + min_spend_gbp)
      deposit       = per deposit_policy thresholds

    Deposit policy (from catering.json):
      total < 300   → 0
      300–1000      → 20 % of total
      > 1000        → 30 % of total

    Returns:
      output: {
        "venue_id": str,
        "party_size": int,
        "duration_hours": int,
        "catering_tier": str,
        "subtotal_gbp": int,
        "service_gbp": int,
        "total_gbp": int,
        "deposit_required_gbp": int,
      }
      summary: "calculate_cost(<venue>, <party>): total £<N>, deposit £<M>"

    MUST call record_tool_call(...) before returning.
    """
    cat_fixture = _SAMPLE_DATA / "catering.json"
    ven_fixture = _SAMPLE_DATA / "venues.json"
    for f in (cat_fixture, ven_fixture):
        if not f.exists():
            raise ToolError("SA_TOOL_DEPENDENCY_MISSING", f"{f.name} not found")

    cat = json.loads(cat_fixture.read_text())
    venues = json.loads(ven_fixture.read_text())

    if catering_tier not in cat["base_rates_gbp_per_head"]:
        raise ToolError("SA_TOOL_INVALID_INPUT", f"Unknown catering_tier '{catering_tier}'")

    if venue_id not in cat["venue_modifiers"]:
        raise ToolError("SA_TOOL_INVALID_INPUT", f"No modifier for venue_id '{venue_id}'")

    venue = next((v for v in venues if v["id"] == venue_id), None)
    if venue is None:
        raise ToolError("SA_TOOL_INVALID_INPUT", f"venue_id '{venue_id}' not found in venues.json")

    base_per_head = cat["base_rates_gbp_per_head"][catering_tier]   # e.g. 18
    venue_mult    = cat["venue_modifiers"][venue_id]                 # e.g. 1.0
    svc_pct       = cat["service_charge_percent"]                    # 10
    hire_and_min  = venue["hire_fee_gbp"] + venue["min_spend_gbp"]  # e.g. 0 + 200 = 200

    subtotal = int(base_per_head * venue_mult * party_size * max(1, duration_hours))
    service  = int(subtotal * svc_pct / 100)
    total    = subtotal + service + hire_and_min

    # Deposit policy thresholds from catering.json (string-keyed, parsed manually)
    policy = cat["deposit_policy"]
    if total < 300:
        # "under_gbp_300": "no_deposit_required"
        deposit = 0
    elif total <= 1000:
        # "gbp_300_to_1000": "deposit_20_percent"
        deposit = int(total * 20 / 100)
    else:
        # "over_gbp_1000": "deposit_30_percent"
        deposit = int(total * 30 / 100)

    args = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
    }
    output = {
        "venue_id": venue_id,
        "party_size": party_size,
        "duration_hours": duration_hours,
        "catering_tier": catering_tier,
        "subtotal_gbp": subtotal,
        "service_gbp": service,
        "total_gbp": total,
        "deposit_required_gbp": deposit,
    }
    record_tool_call("calculate_cost", args, output)
    return ToolResult(
        success=True,
        output=output,
        summary=f"calculate_cost({venue_id}, {party_size}): total £{total}, deposit £{deposit}",
    )


# ---------------------------------------------------------------------------
# TODO 4 — generate_flyer  ✓
# ---------------------------------------------------------------------------
def generate_flyer(session: Session, event_details: dict) -> ToolResult:
    """Produce an HTML flyer and write it to workspace/flyer.html.

    event_details is expected to contain at least:
      venue_name, venue_address, date, time, party_size, condition,
      temperature_c, total_gbp, deposit_required_gbp

    Write a self-contained HTML flyer (inline CSS, no external assets).
    Tag every key fact with data-testid="<n>" so the integrity check
    can parse it.

    Returns:
      output: {"path": "workspace/flyer.html", "bytes_written": int}
      summary: "generate_flyer: wrote <path> (<N> chars)"

    MUST call record_tool_call(...) before returning — the integrity
    check compares the flyer's contents against earlier tool outputs.

    IMPORTANT: this tool MUST be registered with parallel_safe=False
    because it writes a file.
    """
    path = session.workspace_dir / "flyer.html"
    d = event_details

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Edinburgh Event Flyer</title>
  <style>
    body {{
      font-family: Georgia, serif;
      max-width: 620px;
      margin: 2rem auto;
      padding: 0 1.5rem;
      color: #222;
      background: #fafafa;
    }}
    article {{
      border: 2px solid #2c4a6e;
      border-radius: 6px;
      padding: 2rem;
      background: #fff;
    }}
    h1 {{
      margin: 0 0 1.5rem;
      font-size: 1.6rem;
      color: #2c4a6e;
      border-bottom: 1px solid #ddd;
      padding-bottom: .75rem;
    }}
    dl {{
      display: grid;
      grid-template-columns: 9rem 1fr;
      gap: .6rem 1rem;
      margin: 0;
    }}
    dt {{ font-weight: bold; color: #555; }}
    dd {{ margin: 0; }}
    .section-head {{
      grid-column: 1 / -1;
      margin-top: 1rem;
      font-size: .85rem;
      text-transform: uppercase;
      letter-spacing: .05em;
      color: #888;
      border-top: 1px solid #eee;
      padding-top: .75rem;
    }}
  </style>
</head>
<body>
<article data-testid="flyer">
  <h1 data-testid="event-title">Edinburgh Private Event</h1>
  <dl>
    <dt class="section-head">Venue</dt>
    <dt>Name</dt>       <dd data-testid="venue-name">{d.get('venue_name', '')}</dd>
    <dt>Address</dt>    <dd data-testid="venue-address">{d.get('venue_address', '')}</dd>

    <dt class="section-head">Event</dt>
    <dt>Date</dt>       <dd data-testid="event-date">{d.get('date', '')}</dd>
    <dt>Time</dt>       <dd data-testid="event-time">{d.get('time', '')}</dd>
    <dt>Guests</dt>     <dd data-testid="party-size">{d.get('party_size', '')}</dd>
    <dt>Catering</dt>   <dd data-testid="catering-tier">{d.get('catering_tier', '')}</dd>
    <dt>Duration</dt>   <dd data-testid="duration-hours">{d.get('duration_hours', '')} hours</dd>

    <dt class="section-head">Weather</dt>
    <dt>Condition</dt>  <dd data-testid="condition">{d.get('condition', '')}</dd>
    <dt>Temperature</dt><dd data-testid="temperature">{d.get('temperature_c', '')}°C</dd>

    <dt class="section-head">Cost</dt>
    <dt>Total</dt>      <dd data-testid="total-cost">£{d.get('total_gbp', '')}</dd>
    <dt>Deposit</dt>    <dd data-testid="deposit">£{d.get('deposit_required_gbp', '')}</dd>
  </dl>
</article>
</body>
</html>"""

    path.write_text(html, encoding="utf-8")

    output = {"path": "workspace/flyer.html", "bytes_written": len(html)}
    record_tool_call("generate_flyer", {"event_details": event_details}, output)
    return ToolResult(
        success=True,
        output=output,
        summary=f"generate_flyer: wrote workspace/flyer.html ({len(html)} chars)",
    )


# ---------------------------------------------------------------------------
# Registry builder — DO NOT MODIFY the name, signature, or registration calls.
# The grader imports and calls this to pick up your tools.
# ---------------------------------------------------------------------------
def build_tool_registry(session: Session) -> ToolRegistry:
    """Build a session-scoped tool registry with all four Ex5 tools plus
    the sovereign-agent builtins (read_file, write_file, list_files,
    handoff_to_structured, complete_task).

    DO NOT change the tool names — the tests and grader call them by name.
    """
    from sovereign_agent.tools.builtin import make_builtin_registry

    reg = make_builtin_registry(session)

    # venue_search
    reg.register(
        _RegisteredTool(
            name="venue_search",
            description="Search Edinburgh venues by area, party size, and max budget.",
            fn=venue_search,
            parameters_schema={
                "type": "object",
                "properties": {
                    "near": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "budget_max_gbp": {"type": "integer", "default": 1000},
                },
                "required": ["near", "party_size"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"near": "Haymarket", "party_size": 6, "budget_max_gbp": 800},
                    "output": {"count": 1, "results": [{"id": "haymarket_tap"}]},
                }
            ],
        )
    )

    # get_weather
    reg.register(
        _RegisteredTool(
            name="get_weather",
            description="Get scripted weather for a city on a YYYY-MM-DD date.",
            fn=get_weather,
            parameters_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["city", "date"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # read-only
            examples=[
                {
                    "input": {"city": "Edinburgh", "date": "2026-04-25"},
                    "output": {"condition": "cloudy", "temperature_c": 12},
                }
            ],
        )
    )

    # calculate_cost
    reg.register(
        _RegisteredTool(
            name="calculate_cost",
            description="Compute total cost and deposit for a booking.",
            fn=calculate_cost,
            parameters_schema={
                "type": "object",
                "properties": {
                    "venue_id": {"type": "string"},
                    "party_size": {"type": "integer"},
                    "duration_hours": {"type": "integer"},
                    "catering_tier": {
                        "type": "string",
                        "enum": ["drinks_only", "bar_snacks", "sit_down_meal", "three_course_meal"],
                        "default": "bar_snacks",
                    },
                },
                "required": ["venue_id", "party_size", "duration_hours"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=True,  # pure compute, no shared state
            examples=[
                {
                    "input": {
                        "venue_id": "haymarket_tap",
                        "party_size": 6,
                        "duration_hours": 3,
                    },
                    "output": {"total_gbp": 540, "deposit_required_gbp": 0},
                }
            ],
        )
    )

    # generate_flyer — parallel_safe=False because it writes a file
    def _flyer_adapter(event_details: dict) -> ToolResult:
        return generate_flyer(session, event_details)

    reg.register(
        _RegisteredTool(
            name="generate_flyer",
            description="Write an HTML flyer for the event to workspace/flyer.html.",
            fn=_flyer_adapter,
            parameters_schema={
                "type": "object",
                "properties": {"event_details": {"type": "object"}},
                "required": ["event_details"],
            },
            returns_schema={"type": "object"},
            is_async=False,
            parallel_safe=False,  # writes a file — MUST be False
            examples=[
                {
                    "input": {
                        "event_details": {
                            "venue_name": "Haymarket Tap",
                            "date": "2026-04-25",
                            "party_size": 6,
                        }
                    },
                    "output": {"path": "workspace/flyer.html"},
                }
            ],
        )
    )

    return reg


__all__ = [
    "build_tool_registry",
    "venue_search",
    "get_weather",
    "calculate_cost",
    "generate_flyer",
]