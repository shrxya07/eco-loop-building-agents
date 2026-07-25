import ollama
import json

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]
LLM_MODEL = "llama3.1:8b"

def build_prompt(zone_states, building_context):
    return (
                "You are an autonomous HVAC optimization agent for a 5-zone building.\n\n"
        "Decision rules:\n"
        "1. For EACH zone, decide a cooling setpoint in Celsius (one decimal).\n"
        "2. Use ONLY the zone’s own temp_c, pmv, and occupancy.\n"
        "3. Apply these rules:\n"
        "   - If occupancy == 0: setpoint = 28.0 (maximize savings).\n"
        "   - If occupancy > 0:\n"
        "       * If PMV between -0.5 and +0.5: setpoint = temp_c + 1 to 2 (warmer for savings).\n"
        "       * If PMV > 0.5 (too warm):\n"
        "           - Cool only enough to bring PMV back toward neutral.\n"
        "           - Do NOT set below 24.0°C unless PMV ≥ 1.0 AND carbon intensity < 450.\n"
        "       * If PMV < -0.5 (too cold): setpoint = temp_c + 1 to 2 (warmer for comfort).\n"
        "4. Peak demand / carbon-aware adjustment:\n"
        "   - If is_peak_demand_period == true OR grid_carbon_intensity_gCO2_per_kwh >= 450:\n"
        "       * Bias all occupied zones +0.5 to +1.0°C warmer than the above rules.\n"
        "       * Never set below 25.0°C during these periods.\n"
        f"5. Every setpoint must be >= {building_context['minimum_allowed_cooling_setpoint_c']} and <= 28.\n\n"
        "Input data:\n"
        f"Building context:\n{json.dumps(building_context, indent=2)}\n\n"
        f"Zone states:\n{json.dumps(zone_states, indent=2)}\n\n"
        "Output format:\n"
        "- Respond with ONLY a valid JSON object.\n"
        "- Keys must be exactly: SPACE1-1, SPACE2-1, SPACE3-1, SPACE4-1, SPACE5-1.\n"
        "- Values must be numbers (cooling setpoints in Celsius, one decimal).\n"
        "- No text, no explanation, no markdown — just the JSON object."
    )

def call_llm(zone_states, building_context):
    prompt = build_prompt(zone_states, building_context)
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options={"temperature": 0},
    )
    content = response.message.content
    print("Raw content:", content)
    return json.loads(content)

# Scenario A: hot, occupied, midday, high carbon
scenario_a_context = {
    "hour_of_day": 14, "is_peak_demand_period": True, "current_facility_demand_kw": 45.2,
    "grid_carbon_intensity_gCO2_per_kwh": 470, "heating_setpoint_c": 22.2,
    "minimum_allowed_cooling_setpoint_c": 24.2,
}
scenario_a_zones = {
    "SPACE1-1": {"temp_c": 27.5, "pmv": 1.3, "occupancy": 20.0},
    "SPACE2-1": {"temp_c": 24.0, "pmv": -0.1, "occupancy": 5.0},
    "SPACE3-1": {"temp_c": 26.8, "pmv": 1.0, "occupancy": 11.0},
    "SPACE4-1": {"temp_c": 24.2, "pmv": 0.0, "occupancy": 0.0},
    "SPACE5-1": {"temp_c": 25.0, "pmv": 0.3, "occupancy": 8.0},
}

# Scenario B: cool, unoccupied, night, low carbon
scenario_b_context = {
    "hour_of_day": 3, "is_peak_demand_period": False, "current_facility_demand_kw": 10.1,
    "grid_carbon_intensity_gCO2_per_kwh": 320, "heating_setpoint_c": 22.2,
    "minimum_allowed_cooling_setpoint_c": 24.2,
}
scenario_b_zones = {
    "SPACE1-1": {"temp_c": 20.5, "pmv": -1.8, "occupancy": 0.0},
    "SPACE2-1": {"temp_c": 20.3, "pmv": -1.7, "occupancy": 0.0},
    "SPACE3-1": {"temp_c": 20.6, "pmv": -1.6, "occupancy": 0.0},
    "SPACE4-1": {"temp_c": 20.4, "pmv": -1.7, "occupancy": 0.0},
    "SPACE5-1": {"temp_c": 20.9, "pmv": -1.5, "occupancy": 0.0},
}

print("=== SCENARIO A (hot, occupied, peak) ===")
result_a = call_llm(scenario_a_zones, scenario_a_context)
print("Parsed:", result_a)

print("\n=== SCENARIO B (cool, unoccupied, off-peak) ===")
result_b = call_llm(scenario_b_zones, scenario_b_context)
print("Parsed:", result_b)

print("\n=== COMPARISON ===")
if result_a == result_b:
    print("FAIL: identical output for two very different scenarios — still echoing a pattern, not reasoning.")
else:
    print("PASS: outputs differ between scenarios.")
    for z in ZONES:
        print(f"  {z}: A={result_a.get(z)}  B={result_b.get(z)}")