import sys, json, time, os
sys.path.insert(0, r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI
import ollama


IDF_FILE = r"C:\Users\Lalitha\eco_loop\models\working\5ZoneAirCooled.idf"
WEATHER_FILE = r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw"
OUTPUT_DIR = r"C:\Users\Lalitha\eco_loop\out\ai_loop"
os.makedirs(OUTPUT_DIR, exist_ok=True)
ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]
COOLING_SCHEDULES = {z: f"Clg-SetP-Sch-{i+1}" for i, z in enumerate(ZONES)}
LLM_CALL_INTERVAL_TIMESTEPS = 2
LLM_MODEL = "llama3.1:8b"

HEATING_SETPOINT_ASSUMED = 22.2   # keep in sync with guardrail
PEAK_HOURS = range(14, 18)        # 2pm-6pm, typical summer grid peak — adjust if you have real utility data

# Synthetic carbon-intensity profile (gCO2/kWh) by hour — placeholder until/unless you have a real grid API.
# Pattern: higher in evening (gas peaker plants), lower overnight (baseload/nuclear/wind).
CARBON_INTENSITY_BY_HOUR = {
    0:350, 1:340, 2:330, 3:320, 4:320, 5:330, 6:360, 7:400,
    8:430, 9:440, 10:430, 11:420, 12:410, 13:410, 14:430, 15:450,
    16:470, 17:480, 18:460, 19:440, 20:420, 21:400, 22:380, 23:360,
}
import csv as csv_module
COMPARISON_LOG_PATH = os.path.join(OUTPUT_DIR, "ai_loop_log.csv")
if os.path.exists(COMPARISON_LOG_PATH):
    os.remove(COMPARISON_LOG_PATH)
comparison_log_rows = []
api = EnergyPlusAPI()
state = api.state_manager.new_state()

handles = {"temp": {}, "pmv": {}, "occupancy": {}, "cooling_actuator": {}}
timestep_counter = 0
last_known_good_setpoints = {z: 24.0 for z in ZONES}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_cooling_setpoint",
            "description": "Set the cooling setpoint temperature for a specific zone. Must respect the minimum_allowed_cooling_setpoint_c given in the building context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zone": {"type": "string", "enum": ZONES},
                    "setpoint_celsius": {"type": "number", "description": "Cooling setpoint in Celsius, between 20 and 28, and must respect the building's minimum allowed cooling setpoint"}
                },
                "required": ["zone", "setpoint_celsius"]
            }
        }
    }
]

def get_handles(state):
    for z in ZONES:
        handles["temp"][z] = api.exchange.get_variable_handle(state, "Zone Air Temperature", z)
        handles["pmv"][z] = api.exchange.get_variable_handle(state, "Zone Thermal Comfort Fanger Model PMV", f"{z} PEOPLE 1")
        handles["occupancy"][z] = api.exchange.get_variable_handle(state, "Zone People Occupant Count", z)
        handles["cooling_actuator"][z] = api.exchange.get_actuator_handle(state, "Schedule:Compact", "Schedule Value", COOLING_SCHEDULES[z])
        for key, h in [("temp", handles["temp"][z]), ("pmv", handles["pmv"][z]),
                       ("occupancy", handles["occupancy"][z]), ("actuator", handles["cooling_actuator"][z])]:
            if h == -1:
                raise RuntimeError(f"Handle not found: {key} for {z}")
    print("All handles acquired successfully.")
    handles["facility_electricity"] = api.exchange.get_variable_handle(state, "Facility Total Electricity Demand Rate", "Whole Building")
    if handles["facility_electricity"] == -1:
        raise RuntimeError("Facility electricity demand handle not found")

MIN_DEADBAND = 2.0                 # degrees C between heating and cooling setpoints
HEATING_SETPOINT_ASSUMED = 22.2    # confirm this matches Htg-SetP-Sch in the working IDF

import csv
import os

GUARDRAIL_LOG_PATH = os.path.join(OUTPUT_DIR, "guardrail_events.csv")
MAX_SAFE_PMV = 1.5   # absolute PMV bound for occupied zones — beyond this is a real comfort violation

def log_guardrail_event(timestep, zone, reason, proposed, applied, zone_state):
    file_exists = os.path.isfile(GUARDRAIL_LOG_PATH)
    with open(GUARDRAIL_LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestep", "zone", "reason", "proposed_setpoint", "applied_setpoint",
                              "temp_c", "pmv", "occupancy"])
        writer.writerow([timestep, zone, reason, proposed, applied,
                          zone_state["temp_c"], zone_state["pmv"], zone_state["occupancy"]])

MAX_BASELINE_KW = 4.7   # from your baseline run
ENERGY_BIAS_WARMUP = 0.5  # degrees C to add when demand is too high

def guardrail(zone, setpoint, zone_state, timestep, building_context):
    MIN_SP, MAX_SP = 20.0, 28.0

    if not isinstance(setpoint, (int, float)) or not (MIN_SP <= setpoint <= MAX_SP):
        reason = "invalid_or_out_of_bounds"
        print(f"[GUARDRAIL] Rejected {zone} setpoint {setpoint!r} — {reason}, using last-known-good {last_known_good_setpoints[zone]}")
        log_guardrail_event(timestep, zone, reason, setpoint, last_known_good_setpoints[zone], zone_state)
        return last_known_good_setpoints[zone]

    min_allowed = HEATING_SETPOINT_ASSUMED + MIN_DEADBAND
    if setpoint < min_allowed:
        reason = "heating_deadband_violation"
        print(f"[GUARDRAIL] Rejected {zone} setpoint {setpoint} — {reason}, clamping to {min_allowed}")
        log_guardrail_event(timestep, zone, reason, setpoint, min_allowed, zone_state)
        return min_allowed

    # Comfort-aware check
    if zone_state["occupancy"] > 0 and abs(zone_state["pmv"]) > MAX_SAFE_PMV:
        moving_away_from_comfort = (
            (zone_state["pmv"] > 0 and setpoint > zone_state["temp_c"]) or
            (zone_state["pmv"] < 0 and setpoint < zone_state["temp_c"])
        )
        if moving_away_from_comfort:
            reason = "comfort_violation_occupied_zone"
            print(f"[GUARDRAIL] Rejected {zone} setpoint {setpoint} — {reason} "
                  f"(PMV={zone_state['pmv']}, occupied), holding at {last_known_good_setpoints[zone]}")
            log_guardrail_event(timestep, zone, reason, setpoint, last_known_good_setpoints[zone], zone_state)
            return last_known_good_setpoints[zone]

    

    return setpoint



def call_llm_for_decisions(zone_states, building_context):
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
    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            stream=False,
            options={
                "temperature": 0,
                "num_predict": 512,
                "num_ctx": 4096,
            },
        )
        content = response.message.content
        print(f"[DEBUG] Raw JSON content: {content}")
        parsed = json.loads(content)
        decisions = {}
        for z in ZONES:
            val = parsed.get(z)
            if val is not None:
                decisions[z] = float(val)
        return decisions
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return {}
def control_callback(state):
    global timestep_counter

    if not api.exchange.api_data_fully_ready(state):
        return

    if api.exchange.warmup_flag(state):
        return

    print(f"[DEBUG] timestep={timestep_counter}")

    if not handles["temp"]:
        get_handles(state)

    current_hour = api.exchange.hour(state)
    current_time = (
    api.exchange.day_of_month(state),
    api.exchange.hour(state),
    api.exchange.minutes(state),
)

    
    is_peak = current_hour in PEAK_HOURS
    carbon_intensity = CARBON_INTENSITY_BY_HOUR.get(current_hour, 400)
    facility_kw = round(
        api.exchange.get_variable_value(
            state,
            handles["facility_electricity"]
        ) / 1000,
        2,
    )

    zone_states = {}

    for z in ZONES:
        zone_states[z] = {
            "temp_c": round(api.exchange.get_variable_value(state, handles["temp"][z]), 2),
            "pmv": round(api.exchange.get_variable_value(state, handles["pmv"][z]), 2),
            "occupancy": api.exchange.get_variable_value(state, handles["occupancy"][z]),
        }

    building_context = {
        "hour_of_day": current_hour,
        "is_peak_demand_period": is_peak,
        "current_facility_demand_kw": facility_kw,
        "grid_carbon_intensity_gCO2_per_kwh": carbon_intensity,
        "heating_setpoint_c": HEATING_SETPOINT_ASSUMED,
        "minimum_allowed_cooling_setpoint_c": HEATING_SETPOINT_ASSUMED + MIN_DEADBAND,
    }

    if timestep_counter % LLM_CALL_INTERVAL_TIMESTEPS == 0:

        print("[DEBUG] About to call LLM")

        raw_decisions = call_llm_for_decisions(
            zone_states,
            building_context,
        )

        print("[DEBUG] Returned from LLM")

        for z in ZONES:
            proposed = raw_decisions.get(z)

            final = guardrail(
    z,
    proposed,
    zone_states[z],
    timestep_counter,
    building_context,   # <-- pass it in here
)

            last_known_good_setpoints[z] = final

            print(
                f"[{timestep_counter:04d}] "
                f"{z} | hour={current_hour} "
                f"| proposed={proposed} "
                f"| applied={final}"
            )

    for z in ZONES:
        api.exchange.set_actuator_value(
            state,
            handles["cooling_actuator"][z],
            last_known_good_setpoints[z],
        )
    row = {
    "callback": timestep_counter,
    "day": api.exchange.day_of_month(state),
    "hour": api.exchange.hour(state),
    "minute": api.exchange.minutes(state),
    "facility_kw": facility_kw,
}
    for z in ZONES:
        row[f"{z}_temp_c"] = zone_states[z]["temp_c"]
        row[f"{z}_pmv"] = zone_states[z]["pmv"]
        row[f"{z}_occupancy"] = zone_states[z]["occupancy"]
        row[f"{z}_setpoint_applied"] = last_known_good_setpoints[z]
    file_exists = os.path.isfile(COMPARISON_LOG_PATH)

    with open(COMPARISON_LOG_PATH, "a", newline="") as f:
       writer = csv_module.DictWriter(f, fieldnames=row.keys())

       if not file_exists:
          writer.writeheader()

       writer.writerow(row)
       f.flush()
       os.fsync(f.fileno())

    timestep_counter += 1

api.runtime.callback_end_zone_timestep_after_zone_reporting(state, control_callback)
print("Starting EnergyPlus simulation with LLM control loop...\n")
result = api.runtime.run_energyplus(state, ["-w", WEATHER_FILE, "-d", OUTPUT_DIR, IDF_FILE])
print("\nSimulation finished.")
print("Completed successfully." if result == 0 else f"EnergyPlus exited with code {result}")
api.state_manager.delete_state(state)