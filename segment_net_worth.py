"""Known PRIZM average household net worth values by segment.

These values were extracted from the legacy PRIZM cache/CSV exports before the
API moved from browser scraping to the Environics geocoder + Supabase reference
data. The current Supabase `prizm_quick_reference` table does not include a net
worth column, so this map preserves the real values we already collected.
"""

from typing import Any, Optional


AVERAGE_HOUSEHOLD_NET_WORTH_BY_SEGMENT = {
    1: 5831842,
    2: 3581482,
    3: 2337233,
    4: 2145466,
    5: 1738429,
    6: 1559462,
    7: 2154011,
    8: 1318325,
    9: 1513488,
    10: 1734343,
    12: 926329,
    14: 1423912,
    16: 1231141,
    17: 1537284,
    18: 1079579,
    19: 1032934,
    21: 1255437,
    22: 988892,
    23: 973823,
    25: 916822,
    28: 640083,
    30: 780256,
    31: 822468,
    32: 568201,
    33: 989487,
    36: 581073,
    37: 544102,
    38: 638139,
    41: 735547,
    43: 733193,
    45: 603044,
    47: 367331,
    48: 773753,
    49: 627646,
    51: 583438,
    52: 340098,
    53: 508868,
    57: 415686,
    58: 486393,
    60: 401548,
    61: 225766,
    62: 461727,
    67: 238646,
}


def average_household_net_worth_amount(segment_number: Any) -> Optional[int]:
    try:
        numeric_segment = int(segment_number)
    except (TypeError, ValueError):
        return None

    return AVERAGE_HOUSEHOLD_NET_WORTH_BY_SEGMENT.get(numeric_segment)


def average_household_net_worth(segment_number: Any) -> str:
    value = average_household_net_worth_amount(segment_number)
    if value is None:
        return ""
    if value <= 600000:
        return "$0 to $600K"
    if value <= 1000000:
        return "$600K to $1M"
    if value <= 2150000:
        return "$1M to $2.15M"
    return "$2.15M+"
