"""
Formatting utilities for demo output.

Provides consistent formatting for prices, PnL, tables, and other data.
"""

from typing import Any, List, Optional, Union


def format_price(price: float, decimals: int = 2) -> str:
    """
    Format price with proper decimal places and currency symbol.

    Args:
        price: Price value (accepts string/Decimal, converts to float)
        decimals: Number of decimal places

    Returns:
        Formatted price string (e.g., "$95,000.00")
    """
    price = float(price or 0)
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    elif price >= 1:
        return f"${price:.{decimals}f}"
    else:
        return f"${price:.6f}"


def format_pnl(pnl: float, include_sign: bool = True) -> str:
    """
    Format PnL value with color-appropriate sign.

    Args:
        pnl: PnL value (positive or negative, accepts string/Decimal)
        include_sign: Whether to include + for positive

    Returns:
        Formatted PnL string (e.g., "+$25.50" or "-$10.00")
    """
    pnl = float(pnl or 0)
    if pnl >= 0:
        sign = "+" if include_sign else ""
        return f"{sign}${pnl:.2f}"
    else:
        return f"-${abs(pnl):.2f}"


def format_pnl_percent(pnl_percent: float, include_sign: bool = True) -> str:
    """
    Format PnL percentage.

    Args:
        pnl_percent: PnL percentage value (accepts string/Decimal)
        include_sign: Whether to include + for positive

    Returns:
        Formatted percentage string (e.g., "+5.25%" or "-2.10%")
    """
    pnl_percent = float(pnl_percent or 0)
    if pnl_percent >= 0:
        sign = "+" if include_sign else ""
        return f"{sign}{pnl_percent:.2f}%"
    else:
        return f"{pnl_percent:.2f}%"


def format_quantity(qty: float, precision: int = 6) -> str:
    """
    Format quantity with appropriate precision.

    Args:
        qty: Quantity value (accepts string/Decimal)
        precision: Number of decimal places

    Returns:
        Formatted quantity string
    """
    qty = float(qty or 0)
    if qty >= 1:
        return f"{qty:.4f}"
    else:
        return f"{qty:.{precision}f}"


def format_duration(ms: float) -> str:
    """
    Format duration in milliseconds to human readable.

    Args:
        ms: Duration in milliseconds (accepts string/Decimal)

    Returns:
        Formatted duration (e.g., "2.5s", "150ms", "1m 30s")
    """
    ms = float(ms or 0)
    if ms < 1000:
        return f"{ms:.0f}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        minutes = int(ms // 60000)
        seconds = (ms % 60000) / 1000
        return f"{minutes}m {seconds:.0f}s"


def format_status(status: str) -> str:
    """
    Format status with emoji indicator.

    Args:
        status: Status string

    Returns:
        Formatted status with emoji
    """
    status_map = {
        "waiting": " waiting",
        "live": " live",
        "partially_filled": " partially_filled",
        "active": " active",
        "closing": " closing",
        "closed": " closed",
        "failed": " failed",
        "queued": " queued",
        "promoted": " promoted",
        "cancelled": " cancelled",
    }
    return status_map.get(status.lower(), status)


def truncate(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to max length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_table_row(values: List[Any], widths: List[int]) -> str:
    """
    Format a table row with aligned columns.

    Args:
        values: List of values
        widths: List of column widths

    Returns:
        Formatted row string
    """
    cells = []
    for i, (value, width) in enumerate(zip(values, widths)):
        str_value = str(value)
        if len(str_value) > width:
            str_value = str_value[:width-3] + "..."
        cells.append(str_value.ljust(width))
    return " | ".join(cells)


def calculate_column_widths(
    headers: List[str],
    rows: List[List[Any]],
    min_width: int = 5,
    max_width: int = 30,
) -> List[int]:
    """
    Calculate optimal column widths for a table.

    Args:
        headers: Column headers
        rows: Table data rows
        min_width: Minimum column width
        max_width: Maximum column width

    Returns:
        List of column widths
    """
    widths = [len(h) for h in headers]

    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    # Apply min/max constraints
    widths = [max(min_width, min(w, max_width)) for w in widths]

    return widths


def format_simple_table(
    headers: List[str],
    rows: List[List[Any]],
    title: Optional[str] = None,
) -> str:
    """
    Format a simple ASCII table.

    Args:
        headers: Column headers
        rows: Table data rows
        title: Optional table title

    Returns:
        Formatted table string
    """
    widths = calculate_column_widths(headers, rows)

    lines = []

    if title:
        lines.append(f"\n{title}")
        lines.append("-" * (sum(widths) + 3 * (len(headers) - 1)))

    # Header
    lines.append(format_table_row(headers, widths))
    lines.append("-" * (sum(widths) + 3 * (len(headers) - 1)))

    # Rows
    for row in rows:
        lines.append(format_table_row(row, widths))

    lines.append("")

    return "\n".join(lines)
