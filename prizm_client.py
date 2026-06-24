import logging
import os
import re
from typing import Any, Dict, Optional

import requests

from segment_net_worth import average_household_net_worth, average_household_net_worth_amount

logger = logging.getLogger(__name__)

DEFAULT_GEOCODER_API_URL = "https://api.environicsanalytics.com/geocoder-openauth"
DEFAULT_SUPABASE_URL = "https://rkfddhcgcubrelqdzajw.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_C5R7JrownCY44ufZmGj5oQ_d4wQAd7M"


class PrizmLookupError(Exception):
    """Raised when the upstream PRIZM data services cannot satisfy a lookup."""


def normalize_postal_code(postal_code: str) -> Optional[str]:
    """Return a Canadian postal code as A1A 1A1, or None if invalid."""
    if not postal_code:
        return None

    compact = postal_code.strip().upper().replace(" ", "")
    if not re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", compact):
        return None

    return f"{compact[:3]} {compact[3:]}"


def compact_postal_code(postal_code: str) -> str:
    return postal_code.replace(" ", "").upper()


def format_number(value: Any) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    try:
        number = int(float(text.replace(",", "")))
        return f"{number:,}"
    except ValueError:
        return text


def format_currency(value: Any) -> str:
    number = format_number(value)
    return f"${number}" if number else ""


class PrizmClient:
    def __init__(
        self,
        geocoder_api_url: Optional[str] = None,
        geocoder_country: Optional[str] = None,
        geocoder_vintage: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        self.geocoder_api_url = (geocoder_api_url or os.environ.get("PRIZM_GEOCODER_API_URL") or DEFAULT_GEOCODER_API_URL).rstrip("/")
        self.geocoder_country = geocoder_country or os.environ.get("PRIZM_GEOCODER_COUNTRY", "ca")
        self.geocoder_vintage = geocoder_vintage or os.environ.get("PRIZM_GEOCODER_VINTAGE", "2026")
        self.supabase_url = (supabase_url or os.environ.get("PRIZM_SUPABASE_URL") or DEFAULT_SUPABASE_URL).rstrip("/")
        self.supabase_key = supabase_key or os.environ.get("PRIZM_SUPABASE_KEY") or DEFAULT_SUPABASE_KEY
        self.timeout_seconds = timeout_seconds or float(os.environ.get("PRIZM_UPSTREAM_TIMEOUT", "12"))
        self.session = requests.Session()

    def lookup(self, postal_code: str) -> Dict[str, Any]:
        formatted = normalize_postal_code(postal_code)
        if not formatted:
            return self._invalid_response(postal_code, "Invalid Canadian postal code format")

        rural_result = self._lookup_rural_postal_code(formatted)
        if rural_result:
            segment_number = int(rural_result["PRIZM"])
            geocoder_result = {
                "found": True,
                "postal": compact_postal_code(formatted),
                "geography": {"names": {"FSALDU": compact_postal_code(formatted)}},
                "attributes": {},
            }
        else:
            geocoder_result = self._lookup_geocoder(formatted)
            if not geocoder_result.get("found"):
                return self._not_found_response(formatted, geocoder_result)

            segment_code = geocoder_result.get("segmentation", {}).get("codes", {}).get("PZMLLIC")
            segment_number = int(segment_code) if segment_code and str(segment_code).isdigit() else None
            if segment_number is None or segment_number == 68:
                return self._not_found_response(formatted, geocoder_result)

        segment = self.get_segment(segment_number)
        if not segment:
            raise PrizmLookupError(f"No PRIZM segment details found for segment {segment_number}")

        return self._build_response(formatted, segment_number, segment, geocoder_result)

    def get_segment(self, segment_number: int) -> Optional[Dict[str, Any]]:
        rows = self._supabase_get(
            "prizm_quick_reference",
            {
                "select": "*",
                '"Segment Number"': f"eq.{segment_number}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def _lookup_rural_postal_code(self, postal_code: str) -> Optional[Dict[str, Any]]:
        compact = compact_postal_code(postal_code)
        # The PRIZM frontend ships a Supabase table for rural postal codes. Urban
        # postal codes still require the geocoder service.
        if len(compact) < 2 or compact[1] != "0":
            return None

        rows = self._supabase_get(
            "rural_postal_codes",
            {
                "select": "*",
                "FSALDU": f"eq.{compact}",
                "limit": "1",
            },
        )
        return rows[0] if rows else None

    def get_all_segments(self) -> list[Dict[str, Any]]:
        rows = self._supabase_get(
            "prizm_quick_reference",
            {
                "select": "*",
                "order": '"Segment Number".asc',
            },
        )
        return [self._segment_summary(row) for row in rows]

    def _lookup_geocoder(self, postal_code: str) -> Dict[str, Any]:
        url = (
            f"{self.geocoder_api_url}/{self.geocoder_country}/"
            f"{self.geocoder_vintage}/PostalCode/RuralEnhanced"
        )
        payload = {
            "includeGeography": "All",
            "includeSegmentation": "All",
            "includeAttributes": True,
            "postalCodes": [
                {
                    "id": "1",
                    "postalCode": compact_postal_code(postal_code),
                    "communityName": "null",
                }
            ],
        }

        response = self.session.post(
            url,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=self.timeout_seconds,
        )
        if response.status_code == 403:
            raise PrizmLookupError("PRIZM geocoder quota is unavailable; try again later")
        response.raise_for_status()

        data = response.json()
        return data.get("1", {})

    def _supabase_get(self, table: str, params: Dict[str, str]) -> list[Dict[str, Any]]:
        response = self.session.get(
            f"{self.supabase_url}/rest/v1/{table}",
            params=params,
            headers={
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Accept": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def _build_response(
        self,
        postal_code: str,
        segment_number: int,
        segment: Dict[str, Any],
        geocoder_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        geography = geocoder_result.get("geography", {})
        attributes = geocoder_result.get("attributes", {})

        return {
            "postal_code": postal_code,
            "prizm_code": str(segment_number),
            "segment_number": str(segment_number),
            "segment_name": segment.get("PRIZM Name") or "",
            "segment_description": segment.get("PRIZM Descriptor") or "",
            "who_they_are": segment.get("PRIZM Descriptor") or "",
            "average_household_income": format_currency(segment.get("Average Income")),
            "education": segment.get("Education") or "",
            "urbanity": segment.get("Urbanity") or "",
            "average_household_net_worth": average_household_net_worth(segment_number),
            "average_household_net_worth_amount": average_household_net_worth_amount(segment_number),
            "occupation": segment.get("Job Type") or "",
            "diversity": segment.get("Cultural Diversity Index") or "",
            "family_life": segment.get("Family Status") or "",
            "tenure": segment.get("Tenure") or segment.get("Residency") or "",
            "home_type": segment.get("Dwelling Type") or "",
            "income_level": segment.get("Income Level") or "",
            "lifestage": segment.get("Lifestage") or "",
            "social_group": segment.get("Social Group") or "",
            "official_language": segment.get("Official Language") or "",
            "population": format_number(segment.get("Population")),
            "households": format_number(segment.get("Households")),
            "percent_total_households": segment.get("% of Total Households"),
            "latitude": geocoder_result.get("lat"),
            "longitude": geocoder_result.get("lon"),
            "geography": {
                "fsa": geography.get("names", {}).get("FSA"),
                "city": geography.get("names", {}).get("CMACA"),
                "province": geography.get("names", {}).get("PR"),
                "federal_riding": geography.get("names", {}).get("PRFED"),
            },
            "attributes": {
                "is_business": attributes.get("isBusiness"),
                "is_apartment": attributes.get("isApartment"),
                "is_licensed": attributes.get("isLicensed"),
            },
            "status": "success",
        }

    def _segment_summary(self, row: Dict[str, Any]) -> Dict[str, Any]:
        segment_number = row.get("Segment Number")
        return {
            "prizm_code": str(segment_number) if segment_number is not None else "",
            "segment_number": str(segment_number) if segment_number is not None else "",
            "segment_name": row.get("PRIZM Name") or "",
            "segment_description": row.get("PRIZM Descriptor") or "",
            "average_household_income": format_currency(row.get("Average Income")),
            "average_household_net_worth": average_household_net_worth(segment_number),
            "average_household_net_worth_amount": average_household_net_worth_amount(segment_number),
            "education": row.get("Education") or "",
            "urbanity": row.get("Urbanity") or "",
            "occupation": row.get("Job Type") or "",
            "diversity": row.get("Cultural Diversity Index") or "",
            "family_life": row.get("Family Status") or "",
            "tenure": row.get("Tenure") or row.get("Residency") or "",
            "home_type": row.get("Dwelling Type") or "",
            "income_level": row.get("Income Level") or "",
            "lifestage": row.get("Lifestage") or "",
            "social_group": row.get("Social Group") or "",
            "official_language": row.get("Official Language") or "",
            "population": format_number(row.get("Population")),
            "households": format_number(row.get("Households")),
            "percent_total_households": row.get("% of Total Households"),
        }

    def _invalid_response(self, postal_code: str, message: str) -> Dict[str, Any]:
        return {
            "postal_code": postal_code,
            "prizm_code": "Unknown",
            "segment_number": None,
            "segment_name": "",
            "segment_description": "",
            "average_household_income": "",
            "education": "",
            "urbanity": "",
            "average_household_net_worth": "",
            "occupation": "",
            "diversity": "",
            "family_life": "",
            "tenure": "",
            "home_type": "",
            "status": "invalid",
            "message": message,
        }

    def _not_found_response(self, postal_code: str, geocoder_result: Dict[str, Any]) -> Dict[str, Any]:
        response = self._invalid_response(postal_code, "Postal code was not assigned to a PRIZM segment")
        response["status"] = "error"
        response["geocoder_found"] = bool(geocoder_result.get("found"))
        return response
