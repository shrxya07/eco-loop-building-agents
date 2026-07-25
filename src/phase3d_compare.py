import csv

BASELINE_PATH = r"C:\Users\Lalitha\eco_loop\out\baseline\baseline_log.csv"
AI_LOOP_PATH = r"C:\Users\Lalitha\eco_loop\out\ai_loop\ai_loop_log.csv"

def load_facility_kw(path):
    values = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            values.append(float(row["facility_kw"]))
    return values

def load_pmv_stats(path, zones=("SPACE1-1", "SPACE2-1", "SPACE3-1", "SPACE4-1", "SPACE5-1")):
    """Average absolute PMV across all zones/timesteps where occupancy > 0 (comfort only matters when occupied)."""
    abs_pmvs = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for z in zones:
                occ_key = f"{z}_occupancy"
                pmv_key = f"{z}_pmv"
                if occ_key in row and pmv_key in row:
                    occ = float(row[occ_key])
                    if occ > 0:
                        abs_pmvs.append(abs(float(row[pmv_key])))
    return abs_pmvs

# --- Energy comparison ---
baseline_kw = load_facility_kw(BASELINE_PATH)
ai_loop_kw = load_facility_kw(AI_LOOP_PATH)

baseline_avg_kw = sum(baseline_kw) / len(baseline_kw)
ai_loop_avg_kw = sum(ai_loop_kw) / len(ai_loop_kw)

# Convert average kW over the period to approximate total kWh, using each
# dataset's own timestep count and a shared 7-day window assumption.
# (Timestep length may differ slightly between runs due to warmup boundary
# differences, so we normalize by treating avg_kW * 7 days * 24 h as the
# comparable annualized/period energy proxy rather than summing raw rows.)
HOURS_IN_PERIOD = 7 * 24
baseline_kwh_est = baseline_avg_kw * HOURS_IN_PERIOD
ai_loop_kwh_est = ai_loop_avg_kw * HOURS_IN_PERIOD

pct_savings = (baseline_kwh_est - ai_loop_kwh_est) / baseline_kwh_est * 100

print("=== ENERGY COMPARISON (July 1-7) ===")
print(f"Baseline:  {len(baseline_kw)} rows | avg facility demand = {baseline_avg_kw:.3f} kW | est. energy = {baseline_kwh_est:.1f} kWh")
print(f"AI-loop:   {len(ai_loop_kw)} rows | avg facility demand = {ai_loop_avg_kw:.3f} kW | est. energy = {ai_loop_kwh_est:.1f} kWh")
print(f"\n% Energy Savings (AI vs Baseline): {pct_savings:.1f}%")

# --- Comfort comparison ---
baseline_pmv = load_pmv_stats(BASELINE_PATH)
ai_loop_pmv = load_pmv_stats(AI_LOOP_PATH)

print("\n=== COMFORT COMPARISON (occupied timesteps only) ===")
if baseline_pmv:
    print(f"Baseline:  avg |PMV| = {sum(baseline_pmv)/len(baseline_pmv):.3f} | max |PMV| = {max(baseline_pmv):.3f} | n={len(baseline_pmv)}")
else:
    print("Baseline: no occupied-timestep PMV data found (check column names).")
if ai_loop_pmv:
    print(f"AI-loop:   avg |PMV| = {sum(ai_loop_pmv)/len(ai_loop_pmv):.3f} | max |PMV| = {max(ai_loop_pmv):.3f} | n={len(ai_loop_pmv)}")
else:
    print("AI-loop: no occupied-timestep PMV data found (check column names).")

print("\n(Lower avg |PMV| = closer to neutral comfort. ASHRAE-55 typically treats |PMV| <= 0.5 as comfortable.)")