"""Quick diagnostic script to test reverse geocoding end-to-end."""
import urllib.request
import json
import ssl
import traceback
import sys

lat, lon = 16.6646, 74.2095

print(f"[TEST] Testing Nominatim reverse geocode for: ({lat}, {lon})")
print(f"[TEST] Python version: {sys.version}")

url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
headers = {"User-Agent": "SmartEmergencyAlertSystem/1.0 (sunildabhole6@gmail.com)"}

print(f"[TEST] URL: {url}")
print(f"[TEST] Headers: {headers}")

try:
    req = urllib.request.Request(url, headers=headers)
    context = ssl._create_unverified_context()
    
    print("[TEST] Sending request...")
    with urllib.request.urlopen(req, timeout=10.0, context=context) as response:
        print(f"[TEST] HTTP Status: {response.status}")
        raw_data = response.read().decode("utf-8")
        data = json.loads(raw_data)
        
        print(f"\n[TEST] === RAW RESPONSE ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
        address = data.get("address", {})
        display_name = data.get("display_name", "N/A")
        
        print(f"\n[TEST] === PARSED FIELDS ===")
        print(f"  display_name: {display_name}")
        print(f"  road:          {address.get('road')}")
        print(f"  suburb:        {address.get('suburb')}")
        print(f"  neighbourhood: {address.get('neighbourhood')}")
        print(f"  village:       {address.get('village')}")
        print(f"  town:          {address.get('town')}")
        print(f"  city:          {address.get('city')}")
        print(f"  county:        {address.get('county')}")
        print(f"  state:         {address.get('state')}")
        print(f"  postcode:      {address.get('postcode')}")
        print(f"  country:       {address.get('country')}")
        
        # Test our mapping logic
        landmark = address.get("suburb") or address.get("neighbourhood")
        city = address.get("city") or address.get("town") or address.get("village")
        state = address.get("state")
        postal_code = address.get("postcode")
        
        print(f"\n[TEST] === MAPPED OUTPUT ===")
        print(f"  landmark:     {landmark}")
        print(f"  city:         {city}")
        print(f"  state:        {state}")
        print(f"  postal_code:  {postal_code}")
        print(f"  full_address: {display_name}")
        
        if not landmark and not city:
            print("\n[WARNING] Both landmark and city are None!")
            print("  Available address keys:", list(address.keys()))
            # Try extended fallbacks
            road = address.get("road")
            county = address.get("county")
            print(f"  Extended fallback -> road: {road}, county: {county}")

except Exception as e:
    print(f"\n[TEST] === EXCEPTION ===")
    print(f"  Type: {type(e).__name__}")
    print(f"  Message: {str(e)}")
    traceback.print_exc()

print("\n[TEST] Done.")
