"""
Date Validator Module - Post-LLM date validation and correction.

This module detects and corrects DD↔MM swaps in LLM-generated response text
by comparing against canonical dates from tool outputs.
"""

import re
import logging
from datetime import date
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class CanonicalDate:
    """Represents a date extracted from a tool output."""

    date_obj: date
    display: str  # Original display string from tool, e.g., "12/05" or "Lunes 12/05"
    source_tool: str  # Tool name that produced this date


def extract_canonical_dates(intermediate_steps: List[Any]) -> List[CanonicalDate]:
    """
    Extract canonical dates from tool outputs in intermediate_steps.

    Looks for date fields in tool observations: 'date_display', 'fecha',
    'appointment_date', 'date'.

    Args:
        intermediate_steps: List of (action, observation) tuples from LangChain

    Returns:
        List of CanonicalDate objects (possibly empty)
    """
    canonical_dates: List[CanonicalDate] = []

    # Keys to look for in tool outputs
    date_keys = ["date_display", "fecha", "appointment_date", "date", "formatted_date"]

    for step in intermediate_steps:
        if not isinstance(step, tuple) or len(step) != 2:
            continue

        action, observation = step

        # Get tool name
        tool_name = ""
        if hasattr(action, "tool"):
            tool_name = action.tool
        elif hasattr(action, "name"):
            tool_name = action.name
        elif isinstance(action, str):
            tool_name = action

        if not isinstance(observation, dict):
            continue

        # Look for date fields
        for key in date_keys:
            if key in observation:
                value = observation[key]
                if not value:
                    continue

                # Try to parse the date
                date_obj = _parse_date_from_string(str(value))
                if date_obj:
                    canonical_dates.append(
                        CanonicalDate(
                            date_obj=date_obj, display=str(value), source_tool=tool_name
                        )
                    )

    return canonical_dates


def _parse_date_from_string(date_str: str) -> Optional[date]:
    """Try to parse a date from various formats."""
    from dateutil.parser import parse as dateutil_parse

    # Try common formats
    formats = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%m-%y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    # Try dateutil parser
    try:
        parsed = dateutil_parse(date_str, dayfirst=True)
        if parsed:
            return parsed.date()
    except (ValueError, TypeError):
        pass

    return None


from datetime import datetime


def validate_and_correct(
    text: str, canonical_dates: List[CanonicalDate]
) -> Tuple[str, List[Dict]]:
    """
    Detect and correct DD↔MM swaps in LLM response text.

    Compares dates found in text against canonical dates from tools.
    If a date in text is a swap of a canonical date, replaces it.

    Args:
        text: LLM-generated response text
        canonical_dates: List of canonical dates from tool outputs

    Returns:
        Tuple of (corrected_text, list_of_corrections)
    """
    corrections = []

    if not canonical_dates:
        return text, corrections

    # Build a lookup for canonical dates
    # Key: (day, month), Value: display string
    # Also add swapped version to detect swaps
    canonical_lookup: Dict[Tuple[int, int], str] = {}
    for cd in canonical_dates:
        key = (cd.date_obj.day, cd.date_obj.month)
        canonical_lookup[key] = cd.display
        # Also add swapped key for detection
        swapped_key = (cd.date_obj.month, cd.date_obj.day)
        if swapped_key not in canonical_lookup:
            canonical_lookup[swapped_key] = cd.display

    # Regex to find dates in text: DD/MM, DD/MM/YYYY, etc.
    date_pattern = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

    def replace_match(match):
        part_a = match.group(1)  # First part (could be day or month)
        part_b = match.group(2)  # Second part
        year = match.group(3)  # Optional year

        try:
            a = int(part_a)
            b = int(part_b)

            # Skip if day == month (can't be a swap - 05/05 is valid)
            if a == b:
                return match.group(0)

            # Check if this is a swap: text has (a,b) but canonical has (b,a)
            # That means the LLM wrote a/b but should have written b/a
            if (a, b) in canonical_lookup:
                swapped_key = (b, a)
                if swapped_key in canonical_lookup:
                    original = match.group(0)
                    replacement = canonical_lookup[swapped_key]

                    # Only add year if present in original but NOT in replacement
                    if year and year not in replacement:
                        replacement = f"{replacement}/{year}"

                    # Only record and apply if actually different
                    if replacement != original:
                        corrections.append(
                            {
                                "original": original,
                                "replaced_with": replacement,
                                "reason": "DD↔MM swap detected",
                            }
                        )
                        logger.warning(
                            f"[DateValidator] Corrección: '{original}' → '{replacement}'"
                        )
                        return replacement

        except (ValueError, TypeError):
            pass

        return match.group(0)  # No change

    corrected_text = date_pattern.sub(replace_match, text)

    # Also handle weekday + date patterns
    corrected_text = _fix_weekday_date_mismatch(
        corrected_text, canonical_dates, corrections
    )

    return corrected_text, corrections


def _fix_weekday_date_mismatch(
    text: str, canonical_dates: List[CanonicalDate], corrections: List[Dict]
) -> str:
    """Fix dates that appear with weekday names (e.g., "Lunes 05/12")."""
    weekdays = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    # Build lookup for canonical (day, month) -> display
    canonical_lookup: Dict[Tuple[int, int], str] = {}
    for cd in canonical_dates:
        key = (cd.date_obj.day, cd.date_obj.month)
        canonical_lookup[key] = cd.display

    for weekday in weekdays:
        # Pattern: "Lunes 05/12" or "Lunes 05/12/2025"
        pattern = re.compile(
            rf"\b{weekday}\s+(\d{{1,2}})/(\d{{1,2}})(?:/(\d{{2,4}}))?\b", re.IGNORECASE
        )

        def replace_weekday_match(match):
            day = int(match.group(1))
            month = int(match.group(2))
            year = match.group(3)

            # Check if swapped version exists in canonical
            if (day, month) in canonical_lookup:
                if (month, day) in canonical_lookup:
                    original = match.group(0)
                    replacement = canonical_lookup[(month, day)]
                    if year:
                        replacement = f"{weekday} {replacement}/{year}"
                    else:
                        replacement = f"{weekday} {replacement}"
                    corrections.append(
                        {
                            "original": original,
                            "replaced_with": replacement,
                            "reason": "DD↔MM swap in weekday context",
                        }
                    )
                    logger.warning(
                        f"[DateValidator] Corrección: '{original}' → '{replacement}'"
                    )
                    return replacement
            return match.group(0)

        text = pattern.sub(replace_weekday_match, text)

    return text


def validate_dates_in_response(llm_text: str, intermediate_steps: List[Any]) -> str:
    """
    Main entry point: validate and correct dates in LLM response.

    Args:
        llm_text: The LLM-generated response text
        intermediate_steps: The intermediate steps from LangChain execution

    Returns:
        Corrected text (or original if no corrections needed)
    """
    try:
        canonical = extract_canonical_dates(intermediate_steps)
        if not canonical:
            return llm_text

        text, corrections = validate_and_correct(llm_text, canonical)

        if corrections:
            logger.info(f"[DateValidator] Applied {len(corrections)} correction(s)")

        return text
    except Exception as e:
        logger.warning(f"[DateValidator] Error during validation: {e}")
        return llm_text  # Fail safe - return original
