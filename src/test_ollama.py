import ollama

response = ollama.chat(
    model="llama3.1:8b",
    messages=[
        {
            "role": "system",
            "content": "You are an HVAC controller. Reply ONLY with JSON."
        },
        {
            "role": "user",
            "content": """
Return exactly this structure:

{
  "setpoints": {
    "SPACE1-1": 24.5,
    "SPACE2-1": 25.0,
    "SPACE3-1": 24.8,
    "SPACE4-1": 26.2,
    "SPACE5-1": 25.4
  },
  "summary": "Testing JSON output."
}

Do not output anything except JSON.
"""
        }
    ]
)

print(response.message.content)