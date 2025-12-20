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
