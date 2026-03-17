def dms_to_decimal(dms_values: list, ref: str) -> float:
    """
    Convert GPS DMS (degrees, minutes, seconds) to decimal degrees.

    Args:
        dms_values: List of IFD rational values [degrees, minutes, seconds]
        ref: Reference direction ('N', 'S', 'E', 'W')

    Returns:
        Decimal degrees (negative for S and W)
    """
    d = float(dms_values[0].num) / float(dms_values[0].den) if dms_values[0].den else 0
    m = float(dms_values[1].num) / float(dms_values[1].den) if dms_values[1].den else 0
    s = float(dms_values[2].num) / float(dms_values[2].den) if dms_values[2].den else 0

    decimal = d + m / 60 + s / 3600

    if ref in ("S", "W"):
        decimal = -decimal

    return decimal
