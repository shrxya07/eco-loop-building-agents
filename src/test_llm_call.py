import ollama
import json

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]

zone_states = {
    "SPACE1-1": {"temp_c": 24.5, "pmv": 0.1, "occupancy": 5},
    "SPACE2-1": {"temp_c": 23.1, "pmv": -0.4, "occupancy": 2},
    "SPACE3-1": {"temp_c": 25.8, "pmv": 0.9, "occupancy": 8},
    "SPACE4-1": {"temp_c": 22.9, "pmv": -0.6, "occupancy": 0},
    "SPACE5-1": {"temp_c": 24.0, "pmv": 0.0, "occupancy": 12},
}
building_context = {
    "hour_of_day": 15,
    "is_peak_demand_period": True,
    "current_facility_demand_kw": 12.4,
    "grid_carbon_intensity_gCO2_per_kwh": 450,
    "heating_setpoint_c": 22.2,
    "minimum_allowed_cooling_setpoint_c": 24.2,
}

prompt = (
    "You are an HVAC optimization agent for a 5-zone building.\n\n"
    f"Building context:\n{json.dumps(building_context, indent=2)}\n\n"
    f"Zone states:\n{json.dumps(zone_states, indent=2)}\n\n"
    "Decide a cooling setpoint (Celsius, one decimal) for EACH zone based on ITS OWN temp_c, pmv, and occupancy above.\n"
    "Different zones have different conditions, so their setpoints should generally differ too.\n"
    "If a zone's PMV is already between -0.5 and 0.5 (comfortable), pick a setpoint 1-2C WARMER than the current temp_c to save energy, rather than the coolest option.\n"
    f"Every setpoint must be >= {building_context['minimum_allowed_cooling_setpoint_c']} and <= 28.\n\n"
    "Respond with ONLY a JSON object mapping each zone name to a number — no explanation, no markdown, no example text.\n"
    "The keys must be exactly: SPACE1-1, SPACE2-1, SPACE3-1, SPACE4-1, SPACE5-1"
)

response = ollama.chat(
    model="llama3.1:8b",
    messages=[{"role": "user", "content": prompt}],
    format="json",
    stream=False,
    options={"temperature": 0, "num_predict": 512, "num_ctx": 4096},
)

print(repr(response.message.content))
