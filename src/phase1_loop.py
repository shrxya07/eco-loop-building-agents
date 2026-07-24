import sys
sys.path.insert(0, r"C:\EnergyPlusV26-1-0")

from pyenergyplus.api import EnergyPlusAPI

api = EnergyPlusAPI()
state = api.state_manager.new_state()

handles = {"temp": None, "cool_sched": None}

def on_timestep(state):
    if handles["temp"] is None:
        if not api.exchange.api_data_fully_ready(state):
            return
        handles["temp"] = api.exchange.get_variable_handle(
            state, "Zone Air Temperature", "SPACE1-1")
        handles["cool_sched"] = api.exchange.get_actuator_handle(
            state, "Schedule:Compact", "Schedule Value", "Clg-SetP-Sch")

        if handles["temp"] == -1 or handles["cool_sched"] == -1:
            print("ERROR: handle not found — check exact names/case in IDF")
            return
        print("Handles acquired successfully.")

    current_temp = api.exchange.get_variable_value(state, handles["temp"])
    print(f"SPACE1-1 temp: {current_temp:.2f} C")

    new_setpoint = 23.0 if current_temp > 24 else 26.0
    api.exchange.set_actuator_value(state, handles["cool_sched"], new_setpoint)

api.runtime.callback_after_predictor_after_hvac_managers(state, on_timestep)

api.runtime.run_energyplus(state, [
    "-w", r"C:\EnergyPlusV26-1-0\WeatherData\USA_CO_Golden-NREL.724666_TMY3.epw",
    "-d", r"C:\Users\Lalitha\eco_loop\out",
    r"C:\EnergyPlusV26-1-0\ExampleFiles\5ZoneAirCooled.idf"
])