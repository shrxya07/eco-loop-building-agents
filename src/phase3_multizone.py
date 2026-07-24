import sys
sys.path.insert(0, r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI

IDF_FILE = r"C:\Users\Lalitha\eco_loop\models\working\5ZoneAirCooled.idf"
WEATHER_FILE = r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw"
OUTPUT_DIR = r"C:\Users\Lalitha\eco_loop\out"

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]
COOLING_SCHEDULE = "Clg-SetP-Sch"  # NOTE: shared across all zones in this stock file

api = EnergyPlusAPI()
state = api.state_manager.new_state()

handles = {}  # will hold {zone: {"temp": h, "pmv": h}} plus "cooling": h
zone_data = {}  # live state, updated every timestep — this is what tools read from
timestep_counter = 0

def get_handles(s):
    for zone in ZONES:
        handles[zone] = {
            "temp": api.exchange.get_variable_handle(s, "Zone Air Temperature", zone),
            "pmv": api.exchange.get_variable_handle(s, "Zone Thermal Comfort Fanger Model PMV", zone + " PEOPLE 1"),
        }
        if handles[zone]["temp"] == -1:
            raise RuntimeError(f"Temp handle not found for {zone}")
        if handles[zone]["pmv"] == -1:
            raise RuntimeError(f"PMV handle not found for {zone} — check People object name matches '{zone} PEOPLE 1'")
    handles["cooling"] = api.exchange.get_actuator_handle(s, "Schedule:Compact", "Schedule Value", COOLING_SCHEDULE)
    if handles["cooling"] == -1:
        raise RuntimeError("Cooling schedule handle not found")
    print("All handles acquired successfully.")

# ---------- TOOLS ----------

def get_zone_state(zone):
    """Tool: read current temp + PMV for one zone."""
    return {
        "zone": zone,
        "temp_c": round(zone_data[zone]["temp"], 2),
        "pmv": round(zone_data[zone]["pmv"], 2),
    }

def get_all_zones_state():
    """Tool: read current state for all zones at once."""
    return {zone: get_zone_state(zone) for zone in ZONES}

def set_cooling_setpoint(value):
    """Tool: write a new cooling setpoint (shared schedule — affects all zones in this stock building)."""
    api.exchange.set_actuator_value(state, handles["cooling"], value)
    return {"status": "ok", "new_setpoint": value}

# ---------- CONTROL LOOP ----------

def control_callback(s):
    global timestep_counter
    if not api.exchange.api_data_fully_ready(s):
        return
    if not handles:
        get_handles(s)

    # update live zone_data every timestep
    for zone in ZONES:
        zone_data[zone] = {
            "temp": api.exchange.get_variable_value(s, handles[zone]["temp"]),
            "pmv": api.exchange.get_variable_value(s, handles[zone]["pmv"]),
        }

    # HARDCODED rule for now (Phase 4 replaces this with the LLM's decision)
    avg_temp = sum(z["temp"] for z in zone_data.values()) / len(zone_data)
    if avg_temp > 24.5:
        set_cooling_setpoint(23.0)
    elif avg_temp < 23.5:
        set_cooling_setpoint(26.0)
    else:
        set_cooling_setpoint(24.0)

    timestep_counter += 1
    if timestep_counter % 20 == 0:
        state_snapshot = get_all_zones_state()
        print(f"[{timestep_counter:04d}]", state_snapshot)

api.runtime.callback_after_predictor_after_hvac_managers(state, control_callback)
print("Starting EnergyPlus simulation...\n")
result = api.runtime.run_energyplus(state, ["-w", WEATHER_FILE, "-d", OUTPUT_DIR, IDF_FILE])
print("Completed successfully." if result == 0 else f"Exited with code {result}")
api.state_manager.delete_state(state)