"""
PubChem PUG REST API client for fetching compound data.

Retrieves identity, physicochemical properties, and hazard information.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.parse import quote
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests

from packages.doss_core.logging_support import cas_context, get_logger

logger = get_logger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_VIEW_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
PUBCHEM_COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/compound"

REQUEST_TIMEOUT = (5.0, 30.0)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MIN_INTERVAL = 0.35
_MAX_RETRY_WAIT = 20
_CACHE_TTL = 3600
_CACHE_MAX_ENTRIES = 128
_request_lock = Lock()
_cache_lock = Lock()
_next_request_at = 0.0
_cooldown_until = 0.0
_cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()


class PubChemError(Exception):
    """Raised when PubChem cannot supply the requested data."""


class PubChemThrottledError(PubChemError):
    """PubChem is throttling requests or asks the client to pause."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class _PubChemNotFoundError(PubChemError):
    """PubChem returned HTTP 404."""


def _throttle() -> None:
    global _next_request_at
    with _request_lock:
        now = time.monotonic()
        if now < _cooldown_until:
            raise PubChemThrottledError("PubChem requested a cooldown.", _cooldown_until - now)
        wait = _next_request_at - now
        if wait > 0:
            time.sleep(wait)
        _next_request_at = time.monotonic() + _MIN_INTERVAL


def _retry_after(response: requests.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    if value.isascii() and value.isdigit() and len(value) < 20:
        return float(value)
    try:
        when = parsedate_to_datetime(value)
        if not when or when.tzinfo is None:
            return None
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def _cached_response(url: str) -> requests.Response | None:
    with _cache_lock:
        item = _cache.get(url)
        if item is None:
            return None
        expires_at, content = item
        if time.monotonic() >= expires_at:
            del _cache[url]
            return None
        _cache.move_to_end(url)
    response = requests.Response()
    response.status_code = 200
    response.url = url
    response.encoding = "utf-8"
    response._content = content
    response.headers["X-Cache"] = "HIT"
    return response


def _cache_success(url: str, response: requests.Response) -> None:
    try:
        if not isinstance(response.json(), dict):
            return
    except ValueError as exc:
        logger.debug("pubchem_cache_skip_non_json error_type=%s", type(exc).__name__)
        return
    with _cache_lock:
        _cache[url] = (time.monotonic() + _CACHE_TTL, response.content)
        _cache.move_to_end(url)
        if len(_cache) > _CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)


def _get_with_retries(url: str, *, label: str, attempts: int = 4) -> requests.Response:
    """Fetch with a process-wide request pace, success cache, and bounded retry."""
    global _cooldown_until
    cached = _cached_response(url)
    if cached is not None:
        return cached

    for attempt in range(attempts):
        _throttle()
        retry_after = None
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
        except (requests.ConnectionError, requests.Timeout) as exc:
            if attempt + 1 == attempts:
                logger.warning("pubchem_transport_failed context=%r error_type=%s", label, type(exc).__name__)
                raise PubChemError(f"{label}: PubChem network request failed.") from exc
        except requests.RequestException as exc:
            raise PubChemError(f"{label}: PubChem request failed.") from exc
        else:
            status = response.status_code
            if status == 404:
                raise _PubChemNotFoundError(f"{label}: PubChem record not found.")
            if status == 200:
                _cache_success(url, response)
                return response
            if status not in RETRYABLE_STATUS:
                raise PubChemError(f"{label}: PubChem returned HTTP {status}.")
            retry_after = _retry_after(response)
            throttled = status in {429, 503}
            logger.debug("pubchem_retryable_response context=%r status=%d attempt=%d", label, status, attempt + 1)
            if throttled and (attempt + 1 == attempts or (retry_after or 0) > _MAX_RETRY_WAIT):
                if retry_after:
                    with _request_lock:
                        _cooldown_until = max(_cooldown_until, time.monotonic() + retry_after)
                logger.warning("pubchem_throttled context=%r status=%d attempts=%d", label, status, attempt + 1)
                raise PubChemThrottledError(f"{label}: PubChem is temporarily throttled.", retry_after)
            if attempt + 1 == attempts or (retry_after or 0) > _MAX_RETRY_WAIT:
                raise PubChemError(f"{label}: PubChem returned HTTP {status}.")
        delay = min(_MAX_RETRY_WAIT, 1.0 * (2 ** attempt) + random.uniform(0, 0.5))
        wait = max(delay, retry_after or 0)
        time.sleep(wait)

    raise PubChemError(f"{label}: PubChem request did not complete.")


def get_cid_by_cas(cas: str) -> Optional[int]:
    """Look up PubChem CID by CAS registry number."""
    url = f"{PUBCHEM_BASE}/compound/name/{quote(cas, safe='')}/cids/JSON"
    try:
        response = _get_with_retries(url, label=f"CID lookup for CAS {cas_context(cas)}")
    except _PubChemNotFoundError:
        return None
    cids = response.json().get("IdentifierList", {}).get("CID", [])
    return cids[0] if cids else None


def get_compound_properties(cid: int) -> Dict[str, Any]:
    """Fetch basic compound properties from PubChem."""
    properties = [
        "MolecularFormula",
        "MolecularWeight",
        "IUPACName",
        "Title",
        "CanonicalSMILES",
        "ConnectivitySMILES",
        "IsomericSMILES",
    ]
    url = f"{PUBCHEM_BASE}/compound/cid/{cid}/property/{','.join(properties)}/JSON"
    try:
        resp = _get_with_retries(url, label=f"Failed to fetch properties for CID {cid}")
        data = resp.json()
        props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
        return props
    except PubChemError:
        raise
    except requests.RequestException as e:
        raise PubChemError(f"Failed to fetch properties for CID {cid}: {e}") from e




def get_smiles_for_cas(cas: str) -> Optional[str]:
    """PubChem Canonical/Isomeric SMILES for a CAS. None if unknown. Never invents."""
    cid = get_cid_by_cas(cas)
    if cid is None:
        return None
    props = get_compound_properties(cid)
    smiles = (
        props.get("CanonicalSMILES")
        or props.get("IsomericSMILES")
        or props.get("ConnectivitySMILES")
        or ""
    )
    smiles = str(smiles).strip()
    return smiles or None


def get_compound_view_data(cid: int) -> Dict[str, Any]:
    """Fetch extended compound data from PUG View API (retries on ServerBusy)."""
    url = f"{PUBCHEM_VIEW_BASE}/data/compound/{cid}/JSON"
    resp = _get_with_retries(
        url,
        label=f"Failed to fetch view data for CID {cid}",
        attempts=5,
    )
    return resp.json()


def extract_experimental_properties(view_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract experimental properties and hazards from PUG View response."""
    result: Dict[str, Any] = {}

    try:
        record = view_data.get("Record", {})
        sections = record.get("Section", [])

        for section in sections:
            heading = section.get("TOCHeading", "")

            if heading == "Chemical and Physical Properties":
                for subsec in section.get("Section", []):
                    sub_heading = subsec.get("TOCHeading", "")

                    if sub_heading == "Experimental Properties":
                        for prop_sec in subsec.get("Section", []):
                            prop_name = prop_sec.get("TOCHeading", "")
                            info_list = prop_sec.get("Information", [])

                            if info_list:
                                value = _extract_first_value(info_list)
                                if value is not None:
                                    result[prop_name] = value

                    elif sub_heading == "Computed Properties":
                        for prop_sec in subsec.get("Section", []):
                            prop_name = prop_sec.get("TOCHeading", "")
                            info_list = prop_sec.get("Information", [])

                            if prop_name == "Molecular Weight" and info_list:
                                value = _extract_first_value(info_list)
                                if value is not None:
                                    result["Molecular Weight"] = value

            elif heading == "Safety and Hazards":
                for subsec in section.get("Section", []):
                    sub_heading = subsec.get("TOCHeading", "")

                    if sub_heading == "Hazards Identification":
                        for hazard_sec in subsec.get("Section", []):
                            hazard_name = hazard_sec.get("TOCHeading", "")

                            if hazard_name == "GHS Classification":
                                result["GHS"] = _extract_ghs_hazards(hazard_sec)

                            elif hazard_name == "NFPA Hazard Classification":
                                nfpa = _extract_nfpa(hazard_sec)
                                result.update(nfpa)

    except (KeyError, IndexError, TypeError) as exc:
        logger.debug("pubchem_view_parse_failed error_type=%s", type(exc).__name__)
        pass

    return result


def _extract_first_value(info_list: List[Dict]) -> Optional[str]:
    """Extract the first string or numeric value from an Information list."""
    for info in info_list:
        value = info.get("Value", {})

        if "StringWithMarkup" in value:
            strings = value["StringWithMarkup"]
            if strings and "String" in strings[0]:
                return strings[0]["String"]

        if "Number" in value:
            nums = value["Number"]
            if nums:
                unit = value.get("Unit", "")
                return f"{nums[0]} {unit}".strip() if unit else str(nums[0])

    return None


def _extract_ghs_hazards(ghs_section: Dict) -> List[str]:
    """Extract GHS hazard codes from GHS Classification section."""
    hazards: List[str] = []

    for info in ghs_section.get("Information", []):
        value = info.get("Value", {})
        if "StringWithMarkup" in value:
            for item in value["StringWithMarkup"]:
                text = item.get("String", "")
                for part in re.findall(r"\bH\d{3}[A-Z]?\b", text):
                    if part not in hazards:
                        hazards.append(part)
                if text.startswith("H") and len(text) > 3 and text[1:4].isdigit():
                    code = text.split()[0].rstrip(":")
                    if code not in hazards:
                        hazards.append(code)

    return hazards


def _extract_nfpa(nfpa_section: Dict) -> Dict[str, str]:
    """Extract NFPA health and flammability ratings from PUG View.

    PubChem usually stores ratings as:
    - ``NFPA Health Rating`` / ``NFPA Fire Rating`` strings like ``1 - Materials...``
    - Diamond icon Markup ``Extra`` codes like ``1-3-0`` (H-F-R)
    - Occasionally numeric ``Value.Number`` fields
    """
    result: Dict[str, str] = {}

    def _first_digit(s: str) -> str | None:
        s = (s or "").strip()
        m = re.match(r"([0-4])\b", s)
        return m.group(1) if m else None

    for info in nfpa_section.get("Information", []):
        name = info.get("Name", "") or ""
        value = info.get("Value", {}) or {}

        if "Number" in value:
            num = value["Number"][0] if value["Number"] else None
            if num is not None:
                if "Health" in name:
                    result["NFPA Health"] = str(int(num))
                elif "Fire" in name or "Flammability" in name:
                    result["NFPA Flame"] = str(int(num))

        swm = value.get("StringWithMarkup") or []
        if swm:
            text = swm[0].get("String", "") if isinstance(swm[0], dict) else ""
            digit = _first_digit(text)
            # Diamond Extra: "1-3-0"
            for mk in swm[0].get("Markup", []) or []:
                extra = (mk.get("Extra") or "").strip()
                m = re.match(r"([0-4])-([0-4])-([0-4])", extra)
                if m:
                    result.setdefault("NFPA Health", m.group(1))
                    result.setdefault("NFPA Flame", m.group(2))
            if digit:
                if "Health" in name:
                    result["NFPA Health"] = digit
                elif "Fire" in name or "Flammability" in name:
                    result["NFPA Flame"] = digit

    return result


def parse_numeric_with_unit(
    value_str: str, _target_unit: Optional[str] = None
) -> Optional[float]:
    """
    Parse a numeric value from a string that may contain units.

    If the numeric token is immediately followed by °F / F (temperature unit),
    convert to Celsius. A °F appearing later in the string (e.g. density
    measured "at 68 °F") does NOT trigger conversion of the leading number.
    """
    if not value_str:
        return None

    s = str(value_str)
    match = re.search(r"[-+]?\d*\.?\d+", s)
    if not match:
        return None
    try:
        num = float(match.group())
    except ValueError:
        return None

    after = s[match.end() : match.end() + 16]
    if re.match(r"\s*°?\s*F\b", after, re.I) or re.match(
        r"\s*(?:deg(?:ree)?s?\s*)?F(?:ahrenheit)?\b", after, re.I
    ):
        return (num - 32.0) * 5.0 / 9.0

    return num


def fetch_compound_data(cas: str, name_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch compound data for a CAS number.

    Basic identity always comes from PUG REST. PUG View (physchem / GHS / NFPA)
    is retried on ServerBusy; if it still fails, the row is built from identity
    alone and ``view_warning`` explains the partial result.
    """
    cid = get_cid_by_cas(cas)
    if cid is None:
        raise PubChemError(f"Compound not found for CAS {cas}")

    basic_props = get_compound_properties(cid)

    exp_props: Dict[str, Any] = {}
    view_warning: Optional[str] = None
    try:
        view_data = get_compound_view_data(cid)
        exp_props = extract_experimental_properties(view_data)
    except PubChemThrottledError:
        view_warning = (
            "PubChem is rate-limiting extended data. Identity is available, but experimental and "
            "hazard fields from PubChem may be missing. Retry later."
        )
    except PubChemError as exc:
        logger.warning("pubchem_view_unavailable cas=%s error_type=%s", cas_context(cas), type(exc).__name__)
        view_warning = "PubChem extended data unavailable. The result uses the available identity data."

    name = name_hint or basic_props.get("Title") or basic_props.get("IUPACName", "")

    return {
        "cid": cid,
        "name": name,
        "cas": cas,
        "formula": basic_props.get("MolecularFormula", ""),
        "molecular_weight": basic_props.get("MolecularWeight"),
        "properties": exp_props,
        "ghs_hazards": exp_props.get("GHS", []),
        "nfpa_health": exp_props.get("NFPA Health"),
        "nfpa_flame": exp_props.get("NFPA Flame"),
        "pubchem_url": f"{PUBCHEM_COMPOUND_URL}/{cid}",
        "view_warning": view_warning,
        "smiles": (
            basic_props.get("CanonicalSMILES")
            or basic_props.get("IsomericSMILES")
            or basic_props.get("ConnectivitySMILES")
            or ""
        ),
    }
