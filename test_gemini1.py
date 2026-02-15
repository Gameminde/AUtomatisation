import requests
import json

API_KEY = "AIzaSyAd-JwUAJuX6cw6mHW_yA4q0uG73Sc1d7M"

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"


payload = {"contents": [{"parts": [{"text": "Dis bonjour en une phrase courte."}]}]}

headers = {"Content-Type": "application/json"}

response = requests.post(url, headers=headers, data=json.dumps(payload))

print("Status code:", response.status_code)
print("Response:")
print(response.text)
