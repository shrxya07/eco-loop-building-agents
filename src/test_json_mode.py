import ollama
import json

response = ollama.chat(
    model='llama3.1:8b',
    messages=[
        {'role': 'user', 'content': 'Respond with ONLY JSON, no other text: {"a": 1, "b": 2}'}
    ],
    format='json',
    options={'temperature': 0},
)

print("Raw content:", response.message.content)

try:
    parsed = json.loads(response.message.content)
    print("Parsed successfully:", parsed)
except Exception as e:
    print("Failed to parse JSON:", e)