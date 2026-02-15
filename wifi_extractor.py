
import subprocess
import re
import os

def get_wifi_passwords():
    print("⚡ ENI'S WI-FI KEY DUMP ⚡")
    print("-" * 30)
    
    profiles_data = []
    
    try:
        # Get all profiles
        output = subprocess.check_output(["netsh", "wlan", "show", "profiles"]).decode("utf-8", errors="ignore")
        profiles = re.findall(r"All User Profile\s*:\s(.*)", output)
        
        for profile in profiles:
            profile = profile.strip()
            try:
                # Get details for each profile
                profile_info = subprocess.check_output(
                    ["netsh", "wlan", "show", "profile", profile, "key=clear"]
                ).decode("utf-8", errors="ignore")
                
                # Extract password
                password_match = re.search(r"Key Content\s*:\s(.*)", profile_info)
                
                if password_match:
                    password = password_match.group(1).strip()
                    print(f"📡 SSID: {profile:<20} | 🔑 KEY: {password}")
                    profiles_data.append({"ssid": profile, "password": password})
                else:
                    print(f"📡 SSID: {profile:<20} | 🔒 KEY: <Not Found/Open>")
            
            except subprocess.CalledProcessError:
                print(f"❌ Could not retrieve details for {profile}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

    print("-" * 30)
    print(f"✨ Found {len(profiles_data)} keys.")

if __name__ == "__main__":
    get_wifi_passwords()
