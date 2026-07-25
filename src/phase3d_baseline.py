import sys
sys.path.insert(0, r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI

# This is a BASELINE run: it does NOT modify any setpoints via the Runtime API.
# The IDF's own Clg-SetP-Sch-1..5 / DualSetPoint-1..5 objects run exactly as
# authored, untouched. We only use the Runtime API here to log zone state and
# facility electricity demand each timestep, for comparison against the AI-loop
# run's CSV. No actuators are set at all in this script.

IDF_FILE = r"C:\Users\Lalitha\eco_loop\models\working\5ZoneAirCooled.idf"
WEATHER_FILE = r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw"
OUTPUT_DIR = r"C:\Users\Lalitha\eco_loop\out\baseline"
ZONES = ["SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1"]

import os
import csv
os.makedirs(OUTPUT_DIR, exist_ok=True)
LOG_PATH = os.path.join(OUTPUT_DIR, "baseline_log.csv")

api = EnergyPlusAPI()
state = api.state_manager.new_state()

handles = {"temp": {}, "pmv": {}, "occupancy": {}, "facility_electricity": None}
timestep_counter = 0
log_rows = []

def get_handles(state):
    for z in ZONES:
        handles["temp"][z] = api.exchange.get_variable_handle(state, "Zone Air Temperature", z)
        handles["pmv"][z] = api.exchange.get_variable_handle(state, "Zone Thermal Comfort Fanger Model PMV", f"{z} PEOPLE 1")
        handles["occupancy"][z] = api.exchange.get_variable_handle(state, "Zone People Occupant Count", z)
        for key, h in [("temp", handles["temp"][z]), ("pmv", handles["pmv"][z]), ("occupancy", handles["occupancy"][z])]:
            if h == -1:
                raise RuntimeError(f"Handle not found: {key} for {z}")
    handles["facility_electricity"] = api.exchange.get_variable_handle(state, "Facility Total Electricity Demand Rate", "Whole Building")
    if handles["facility_electricity"] == -1:
        raise RuntimeError("Facility electricity demand handle not found")
    print("All handles acquired successfully (baseline, read-only).")

def log_callback(state):
    global timestep_counter
    if not api.exchange.api_data_fully_ready(state):
        return
    if api.exchange.warmup_flag(state):
        return
    if handles["facility_electricity"] is None:
        get_handles(state)
   

    facility_kw = round(api.exchange.get_variable_value(state, handles["facility_electricity"]) / 1000, 3)
    row = {
    "callback": timestep_counter,
    "day": api.exchange.day_of_month(state),
    "hour": api.exchange.hour(state),
    "minute": api.exchange.minutes(state),
    "facility_kw": facility_kw,
}
    for z in ZONES:
        row[f"{z}_temp_c"] = round(api.exchange.get_variable_value(state, handles["temp"][z]), 2)
        row[f"{z}_pmv"] = round(api.exchange.get_variable_value(state, handles["pmv"][z]), 2)
        row[f"{z}_occupancy"] = api.exchange.get_variable_value(state, handles["occupancy"][z])
    log_rows.append(row)

    if timestep_counter % 100 == 0:
        print(f"[BASELINE {timestep_counter:05d}] facility_kw={facility_kw}")

    timestep_counter += 1

api.runtime.callback_end_zone_timestep_after_zone_reporting(state, log_callback)
print("Starting BASELINE EnergyPlus simulation (static schedules, no LLM, no actuation)...\n")
result = api.runtime.run_energyplus(state, ["-w", WEATHER_FILE, "-d", OUTPUT_DIR, IDF_FILE])
print("\nBaseline simulation finished.")
print("Completed successfully." if result == 0 else f"EnergyPlus exited with code {result}")

if log_rows:
    with open(LOG_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        writer.writeheader()
        writer.writerows(log_rows)
    print(f"Wrote {len(log_rows)} rows to {LOG_PATH}")

api.state_manager.delete_state(state)
