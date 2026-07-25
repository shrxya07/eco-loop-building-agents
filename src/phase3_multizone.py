import sys
sys.path.insert(0, r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI

IDF_FILE = r"C:\Users\Lalitha\eco_loop\models\working\5ZoneAirCooled.idf"
WEATHER_FILE = r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw"
OUTPUT_DIR = r"C:\Users\Lalitha\eco_loop\out"

ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]
COOLING_SCHEDULES = {
    "SPACE1-1": "Clg-SetP-Sch-1",
    "SPACE2-1": "Clg-SetP-Sch-2",
    "SPACE3-1": "Clg-SetP-Sch-3",
    "SPACE4-1": "Clg-SetP-Sch-4",
    "SPACE5-1": "Clg-SetP-Sch-5",
}


api = EnergyPlusAPI()
state = api.state_manager.new_state()

handles = {}
zone_data = {}
zone_decisions = {}
timestep_counter = 0

def get_handles(s):
    for zone in ZONES:
        handles[zone] = {
            "temp": api.exchange.get_variable_handle(s, "Zone Air Temperature", zone),
            "pmv": api.exchange.get_variable_handle(s, "Zone Thermal Comfort Fanger Model PMV", zone + " PEOPLE 1"),
            "occupancy": api.exchange.get_variable_handle(s, "Zone People Occupant Count", zone),
            "cooling": api.exchange.get_actuator_handle(s, "Schedule:Compact", "Schedule Value", COOLING_SCHEDULES[zone]),
        }
        if handles[zone]["temp"] == -1:
            raise RuntimeError(f"Temp handle not found for {zone}")
        if handles[zone]["pmv"] == -1:
            raise RuntimeError(f"PMV handle not found for {zone}")
        if handles[zone]["occupancy"] == -1:
            raise RuntimeError(f"Occupancy handle not found for {zone}")
        if handles[zone]["cooling"] == -1:
            raise RuntimeError(f"Cooling actuator not found for {zone}")
    print("All handles acquired successfully.")

def get_zone_state(zone):
    return {
        "zone": zone,
        "temp_c": round(zone_data[zone]["temp"], 2),
        "pmv": round(zone_data[zone]["pmv"], 2),
        "occupancy": int(zone_data[zone]["occupancy"]),
    }

def get_all_zones_state():
    return {zone: get_zone_state(zone) for zone in ZONES}

def set_cooling_setpoint(zone, value):
    api.exchange.set_actuator_value(state, handles[zone]["cooling"], value)
    return {"zone": zone, "setpoint": value}

def control_callback(s):
    global timestep_counter
    if not api.exchange.api_data_fully_ready(s):
        return
    if not handles:
        get_handles(s)

    for zone in ZONES:
        zone_data[zone] = {
            "temp": api.exchange.get_variable_value(s, handles[zone]["temp"]),
            "pmv": api.exchange.get_variable_value(s, handles[zone]["pmv"]),
            "occupancy": api.exchange.get_variable_value(s, handles[zone]["occupancy"]),
        }

    for zone in ZONES:
        pmv = zone_data[zone]["pmv"]
        occ = zone_data[zone]["occupancy"]

        if occ == 0:
            setpoint = 26
            decision = "Energy Saving"
        elif pmv < -0.7:
            setpoint = 27
            decision = "Occupants Cold"
        elif pmv < -0.3:
            setpoint = 26
            decision = "Slightly Cold"
        elif pmv > 0.8:
            setpoint = 22
            decision = "Very Warm"
        elif pmv > 0.3:
            setpoint = 23.5
            decision = "Slightly Warm"
        else:
            setpoint = 24.5
            decision = "Comfort OK"

        set_cooling_setpoint(zone, setpoint)
        zone_decisions[zone] = {"setpoint": setpoint, "decision": decision}

    timestep_counter += 1
    if timestep_counter % 20 == 0:
        state_snapshot = get_all_zones_state()
        print(f"[{timestep_counter:04d}]", state_snapshot, "| Decisions:", zone_decisions)

api.runtime.callback_after_predictor_after_hvac_managers(state, control_callback)
print("Starting EnergyPlus simulation...\n")
result = api.runtime.run_energyplus(state, ["-w", WEATHER_FILE, "-d", OUTPUT_DIR, IDF_FILE])
print("Completed successfully." if result == 0 else f"Exited with code {result}")
api.state_manager.delete_state(state)