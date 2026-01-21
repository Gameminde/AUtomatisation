"""Quick test for Gemini API key."""
import requests

API_KEY = "AIzaSyCLGlGfiHgkI84eHlg8iQNQ9b7FThVv6u0"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

payload = {
    "contents": [{"parts": [{"text": "Say hello in French"}]}],
    "generationConfig": {"maxOutputTokens": 50}
}

try:
    print("Testing Gemini API key...")
    resp = requests.post(URL, json=payload, timeout=30)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            print(f"✅ SUCCESS! Response: {text}")
        else:
            print("⚠️ No candidates in response")
    else:
        print(f"❌ ERROR: {resp.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out (30s)")
except Exception as e:
    print(f"❌ Exception: {e}")
