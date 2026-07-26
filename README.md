# EcoLoop: Autonomous Building Energy Optimization using EnergyPlus and Local LLMs

## Overview

EcoLoop is an autonomous building energy management system developed for the Honeywell AI-Powered Smart Building Optimization Hackathon.

The project combines EnergyPlus, the EnergyPlus Runtime API, a locally hosted Large Language Model (Llama 3.1 through Ollama), and Python to create a closed-loop control system capable of continuously optimizing HVAC cooling setpoints while maintaining occupant thermal comfort.

Unlike conventional Building Management Systems that rely on fixed schedules or rule-based logic, EcoLoop evaluates live building telemetry during simulation, reasons over current operating conditions using an LLM, validates every recommendation through deterministic guardrails, and injects approved control actions back into the running EnergyPlus simulation.

The project demonstrates autonomous HVAC optimization while providing complete runtime transparency through an interactive monitoring dashboard.

---

## Problem Statement

Commercial buildings often operate using static HVAC schedules that cannot adapt to changing occupancy, comfort requirements, or energy demand.

The objective of this project is to build an autonomous control system capable of:

- Monitoring building operating conditions in real time
- Maintaining occupant thermal comfort
- Reducing building energy consumption
- Making autonomous HVAC decisions without human intervention
- Providing transparent explanations for every control action

---

## System Architecture

The system follows a closed-loop autonomous control architecture.

```
                EnergyPlus Simulation
                        │
                        ▼
            Runtime Telemetry Collection
                        │
                        ▼
             Python Processing Layer
                        │
                        ▼
        Local LLM (Llama 3.1 via Ollama)
                        │
                        ▼
          Guardrail Validation Layer
                        │
                        ▼
        Cooling Setpoint Actuation
                        │
                        ▼
          EnergyPlus Runtime API
                        │
                        ▼
              Live Dashboard
                        ▲
                        │
              Continuous Feedback Loop
```

---

## Key Features

- EnergyPlus Runtime API integration
- Autonomous HVAC cooling setpoint optimization
- Local LLM inference using Ollama
- Deterministic guardrail validation
- Baseline vs AI energy comparison
- Live digital twin visualization
- Runtime decision explanation panel
- Facility power timeline
- Thermal comfort monitoring using Fanger PMV
- Structured telemetry logging
- Interactive Streamlit dashboard

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Building Simulation | EnergyPlus 26.1 |
| Runtime API | pyenergyplus |
| AI Model | Llama 3.1 8B |
| LLM Runtime | Ollama |
| Programming Language | Python |
| Dashboard | Streamlit |
| Visualization | Plotly |
| Data Processing | Pandas |
| Logging | CSV |

---

## Repository Structure

```
EcoLoop/

├── dashboard/
│   ├── app.py
│   └── assets/
│
├── src/
│   ├── phase3a_llm_loop.py
│   ├── phase3d_compare.py
│   └── test_*.py
│
├── models/
│   ├── baseline/
│   └── ai/
│
├── out/
│   ├── baseline/
│   └── ai_loop/
│
├── docs/
│
├── README.md
└── requirements.txt
```

---

## Control Pipeline

During every control cycle the system performs the following sequence:

1. Read live EnergyPlus zone telemetry.
2. Assemble building and zone context.
3. Send the current state to the local LLM.
4. Generate cooling setpoint recommendations.
5. Validate every recommendation using deterministic guardrails.
6. Apply approved setpoints through the EnergyPlus Runtime API.
7. Log telemetry and decisions.
8. Update the monitoring dashboard.

---

## Dashboard

The dashboard provides live insight into the autonomous controller.

It includes:

- Energy savings KPIs
- Cost savings estimation
- Carbon reduction estimation
- Comfort statistics
- AI controller reasoning
- Building digital twin
- Zone operating conditions
- Baseline comparison
- Runtime telemetry
- Facility power timeline

---

## Results

Evaluation was performed using the standard EnergyPlus 5ZoneAirCooled commercial reference building.

Current proof-of-concept results:

| Metric | Result |
|---------|---------|
| Energy Reduction | 5.7% |
| Energy Saved | 205.1 kWh |
| Estimated Cost Saved | $24.61 |
| Estimated CO₂ Reduction | 82.0 kg |
| Comfort Maintained | 85.4% |

---

## Safety Mechanisms

All LLM-generated control actions are validated before execution.

The guardrail layer enforces:

- Cooling setpoint limits
- Heating deadband protection
- Occupied comfort protection
- Invalid response rejection
- Last known safe setpoint fallback

This prevents unsafe or unrealistic HVAC control actions from reaching the simulation.

---

## Running the Project

### Prerequisites

- Python 3.11+
- EnergyPlus 26.1
- Ollama
- Llama 3.1 8B model

### Install

```bash
pip install -r requirements.txt
```

### Start Ollama

```bash
ollama serve
```

### Run the Autonomous Controller

```bash
python src/phase3a_llm_loop.py
```

### Launch the Dashboard

```bash
streamlit run dashboard/app.py
```

---

## Future Improvements

Future work may include:

- Native MCP tool calling
- Live electricity tariff integration
- Real-time weather forecasts
- Grid carbon intensity APIs
- Reinforcement learning controllers
- Multi-building optimization
- Occupancy prediction
- Cloud deployment
- BACnet integration for physical Building Management Systems

---

## Authors

Shreya Mahesh

Developed for the Honeywell AI-Powered Smart Building Optimization Hackathon.