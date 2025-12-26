/**
 * Safely converts a value to a number and applies toFixed.
 * Handles strings (from Decimal backend values), null, undefined, and NaN.
 */
export const safeToFixed = (value: any, decimals: number = 2): string => {
  if (value === null || value === undefined) return (0).toFixed(decimals);
  const num = typeof value === 'string' ? parseFloat(value) : Number(value);
  return isNaN(num) ? (0).toFixed(decimals) : num.toFixed(decimals);
};

/**
 * Safely converts a value to a number.
 * Handles strings (from Decimal backend values), null, undefined, and NaN.
 */
export const safeNumber = (value: any, defaultValue: number = 0): number => {
  if (value === null || value === undefined) return defaultValue;
  const num = typeof value === 'string' ? parseFloat(value) : Number(value);
  return isNaN(num) ? defaultValue : num;
};

/**
 * Formats a currency value for trading tables.
 * Shows FULL precision for prices >= $1 (every digit matters in trading!)
 * Only uses compact notation for very small numbers < $1 with many zeros.
 *
 * Examples:
 * - $100,002.45 → "$100,002.45" (full number shown)
 * - $0.1234 → "$0.1234"
 * - $0.00001234 → "$0.0₄1234" (subscript = 4 zeros after decimal)
 */
export const formatCompactCurrency = (value: any): string => {
  if (value === null || value === undefined) return '-';
  const num = typeof value === 'string' ? parseFloat(value) : Number(value);
  if (isNaN(num)) return '-';

  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';

  // Zero
  if (absNum === 0) return '$0.00';

  // Numbers >= 1: show full number with 2 decimals
  if (absNum >= 1) {
    return `${sign}$${absNum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  // Small numbers < 1: count leading zeros after decimal
  const str = absNum.toFixed(12);
  const match = str.match(/^0\.(0*)([1-9]\d*)/);

  if (match) {
    const zeroCount = match[1].length;
    const significantDigits = match[2];

    // If 3 or fewer zeros, show normally with enough decimals
    if (zeroCount <= 3) {
      const decimals = Math.min(zeroCount + 4, 8);
      return `${sign}$${absNum.toFixed(decimals)}`;
    }

    // For many zeros (4+), use subscript notation: 0.0₄1234 means 0.00001234
    const subscriptDigits = '₀₁₂₃₄₅₆₇₈₉';
    const subscript = zeroCount.toString().split('').map(d => subscriptDigits[parseInt(d)]).join('');
    const sigFigs = significantDigits.slice(0, 4);
    return `${sign}$0.0${subscript}${sigFigs}`;
  }

  return `${sign}$${absNum.toFixed(4)}`;
};

/**
 * Formats a percentage value compactly.
 */
export const formatCompactPercent = (value: any): string => {
  if (value === null || value === undefined) return '-';
  const num = safeNumber(value);
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(1)}%`;
};
