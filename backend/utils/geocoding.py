"""
Reverse Geocoding Module — OpenStreetMap Nominatim
===================================================
Uses urllib.request with retry logic, extended field fallbacks,
and deep diagnostic logging at every step.
"""
import urllib.request
import json
import logging
import ssl
import traceback
import time
import sys

logger = logging.getLogger("SEAS_Geocoding")

# Default fallback result when geocoding fails
_FALLBACK = {
    "full_address": "Address unavailable",
    "landmark": None,
    "city": None,
    "state": None,
    "country": None,
    "postal_code": None,
}

# Nominatim endpoint
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"

from config import settings

# Required User-Agent per Nominatim usage policy
_HEADERS = {
    "User-Agent": f"SmartEmergencyAlertSystem/1.0 ({settings.ADMIN_EMAIL})",
    "Accept-Language": "en",
    "Accept": "application/json",
    "Referer": "https://seas-app.local",
}

_TIMEOUT = 8  # seconds


def _parse_address(data: dict) -> dict:
    """
    Parse Nominatim response JSON into structured address fields.
    Uses intelligent fallback mapping for Indian and international addresses.
    """
    address = data.get("address", {})
    display_name = data.get("display_name", "Address unavailable")

    # Deep debug: print all available keys
    print(f"[GEOCODING] Available address keys: {list(address.keys())}")
    print(f"[GEOCODING] Full address object: {address}")

    # ── Landmark: road → suburb → neighbourhood → quarter → hamlet ──
    landmark = (
        address.get("road")
        or address.get("suburb")
        or address.get("neighbourhood")
        or address.get("quarter")
        or address.get("hamlet")
    )

    # ── City: city → town → village → municipality → county ──
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
    )

    # ── State, Country, Postal Code ──
    state = address.get("state")
    country = address.get("country")
    postal_code = address.get("postcode")

    result = {
        "full_address": display_name,
        "landmark": landmark,
        "city": city,
        "state": state,
        "country": country,
        "postal_code": postal_code,
    }

    print(f"[GEOCODING] Parsed: landmark={landmark}, city={city}, "
          f"state={state}, postal_code={postal_code}")
    print(f"[GEOCODING] Full address: {display_name}")

    return result


def _do_reverse_geocode(lat: float, lon: float) -> dict:
    """
    Single attempt at reverse geocoding via Nominatim.
    Returns parsed dict on success. Raises Exception on any failure.
    """
    url = (
        f"{_NOMINATIM_URL}"
        f"?format=jsonv2"
        f"&lat={lat}"
        f"&lon={lon}"
        f"&zoom=18"
        f"&addressdetails=1"
    )

    print(f"[GEOCODING] Requesting: lat={lat}, lng={lon}")
    print(f"[GEOCODING] URL: {url}")

    # ── Step 1: Build request ──
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
    except Exception as e:
        print(f"[GEOCODING] FAILED at Request construction: {e}")
        raise

    # ── Step 2: Create SSL context ──
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    except Exception as e:
        print(f"[GEOCODING] FAILED at SSL context creation: {e}")
        raise

    # ── Step 3: Execute HTTP request ──
    try:
        response = urllib.request.urlopen(req, timeout=_TIMEOUT, context=context)
    except urllib.error.HTTPError as e:
        print(f"[GEOCODING] HTTP ERROR: {e.code} {e.reason}")
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        print(f"[GEOCODING] Error response body: {error_body}")
        raise
    except urllib.error.URLError as e:
        print(f"[GEOCODING] URL ERROR (network/DNS/proxy): {e.reason}")
        raise
    except TimeoutError:
        print(f"[GEOCODING] TIMEOUT after {_TIMEOUT}s")
        raise
    except Exception as e:
        print(f"[GEOCODING] UNEXPECTED HTTP ERROR: {type(e).__name__}: {e}")
        raise

    # ── Step 4: Read response body ──
    try:
        status_code = response.status
        print(f"[GEOCODING] HTTP Status: {status_code}")

        raw_data = response.read().decode("utf-8")
        print(f"[GEOCODING] RAW RESPONSE (first 500 chars): {raw_data[:500]}")
        response.close()

        if status_code != 200:
            raise RuntimeError(f"Nominatim returned HTTP {status_code}")
    except RuntimeError:
        raise
    except Exception as e:
        print(f"[GEOCODING] FAILED reading response: {type(e).__name__}: {e}")
        raise

    # ── Step 5: Parse JSON ──
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"[GEOCODING] JSON PARSE ERROR: {e}")
        print(f"[GEOCODING] Raw text was: {raw_data[:300]}")
        raise

    # ── Step 6: Check for Nominatim error ──
    if "error" in data:
        error_msg = data["error"]
        print(f"[GEOCODING] Nominatim API error: {error_msg}")
        raise RuntimeError(f"Nominatim error: {error_msg}")

    # ── Step 7: Parse address fields ──
    return _parse_address(data)


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Perform reverse geocoding with automatic retry on failure.

    - Attempt 1: immediately
    - If fails → retry once after 2 seconds
    - If retry fails → return graceful fallback (never crash)

    Returns parsed dictionary of address components.
    """
    if lat is None or lon is None:
        print("[GEOCODING] ERROR: lat or lon is None")
        return dict(_FALLBACK)

    if lat == 0.0 or lon == 0.0:
        print("[GEOCODING] ERROR: lat or lon is zero (invalid)")
        return dict(_FALLBACK)

    # ── Attempt 1 ──
    print(f"[GEOCODING] ═══ Attempt 1 for ({lat}, {lon}) ═══")
    try:
        result = _do_reverse_geocode(lat, lon)
        print(f"[GEOCODING] ✓ SUCCESS on first attempt")
        return result
    except Exception as e:
        print(f"[GEOCODING] ✗ First attempt FAILED: {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)

    # ── Retry after 2 seconds ──
    print("[GEOCODING] ═══ Retrying in 2 seconds... ═══")
    time.sleep(2)

    try:
        result = _do_reverse_geocode(lat, lon)
        print(f"[GEOCODING] ✓ SUCCESS on retry")
        return result
    except Exception as e:
        print(f"[GEOCODING] ✗ Retry also FAILED: {type(e).__name__}: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        logger.error(f"Reverse geocoding failed after retry: {str(e)}")

    print("[GEOCODING] ✗✗ Returning fallback (Address unavailable)")
    return dict(_FALLBACK)
