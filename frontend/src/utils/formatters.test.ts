import {
  safeToFixed,
  safeNumber,
  formatCompactCurrency,
  formatCompactPercent,
} from './formatters';

describe('safeToFixed', () => {
  test('formats number with default decimals', () => {
    expect(safeToFixed(123.456)).toBe('123.46');
  });

  test('formats number with custom decimals', () => {
    expect(safeToFixed(123.456, 3)).toBe('123.456');
    expect(safeToFixed(123.456, 0)).toBe('123');
  });

  test('handles string values', () => {
    expect(safeToFixed('123.456')).toBe('123.46');
  });

  test('handles null value', () => {
    expect(safeToFixed(null)).toBe('0.00');
  });

  test('handles undefined value', () => {
    expect(safeToFixed(undefined)).toBe('0.00');
  });

  test('handles NaN value', () => {
    expect(safeToFixed(NaN)).toBe('0.00');
  });

  test('handles non-numeric string', () => {
    expect(safeToFixed('abc')).toBe('0.00');
  });

  test('handles zero', () => {
    expect(safeToFixed(0)).toBe('0.00');
  });

  test('handles negative numbers', () => {
    expect(safeToFixed(-123.456)).toBe('-123.46');
  });
});

describe('safeNumber', () => {
  test('converts number to number', () => {
    expect(safeNumber(123.456)).toBe(123.456);
  });

  test('converts string to number', () => {
    expect(safeNumber('123.456')).toBe(123.456);
  });

  test('returns default for null', () => {
    expect(safeNumber(null)).toBe(0);
    expect(safeNumber(null, 10)).toBe(10);
  });

  test('returns default for undefined', () => {
    expect(safeNumber(undefined)).toBe(0);
    expect(safeNumber(undefined, 5)).toBe(5);
  });

  test('returns default for NaN', () => {
    expect(safeNumber(NaN)).toBe(0);
    expect(safeNumber(NaN, -1)).toBe(-1);
  });

  test('returns default for non-numeric string', () => {
    expect(safeNumber('abc')).toBe(0);
  });

  test('handles zero', () => {
    expect(safeNumber(0)).toBe(0);
  });

  test('handles negative numbers', () => {
    expect(safeNumber(-123.456)).toBe(-123.456);
  });
});

describe('formatCompactCurrency', () => {
  test('returns dash for null', () => {
    expect(formatCompactCurrency(null)).toBe('-');
  });

  test('returns dash for undefined', () => {
    expect(formatCompactCurrency(undefined)).toBe('-');
  });

  test('returns dash for NaN', () => {
    expect(formatCompactCurrency(NaN)).toBe('-');
  });

  test('formats zero', () => {
    expect(formatCompactCurrency(0)).toBe('$0.00');
  });

  test('formats numbers >= 1 with 2 decimals', () => {
    expect(formatCompactCurrency(100)).toBe('$100.00');
    expect(formatCompactCurrency(1234.56)).toBe('$1,234.56');
    expect(formatCompactCurrency(1)).toBe('$1.00');
  });

  test('formats negative numbers', () => {
    expect(formatCompactCurrency(-100)).toBe('-$100.00');
    expect(formatCompactCurrency(-0.5)).toBe('-$0.5000');
  });

  test('formats small numbers < 1 with few zeros', () => {
    expect(formatCompactCurrency(0.5)).toBe('$0.5000');
    expect(formatCompactCurrency(0.12)).toBe('$0.1200');
    // 0.001 has 2 leading zeros, so it uses decimals = min(2+4, 8) = 6 decimals
    expect(formatCompactCurrency(0.001)).toBe('$0.001000');
  });

  test('formats very small numbers with subscript notation', () => {
    // For 4+ leading zeros, use subscript
    const result = formatCompactCurrency(0.00001234);
    expect(result).toMatch(/\$0\.0.*1234/);
  });

  test('handles string input', () => {
    expect(formatCompactCurrency('100.50')).toBe('$100.50');
  });

  test('handles non-numeric string', () => {
    expect(formatCompactCurrency('abc')).toBe('-');
  });

  test('formats large numbers with locale separators', () => {
    const result = formatCompactCurrency(100002.45);
    expect(result).toContain('$');
    expect(result).toContain('100');
  });
});

describe('formatCompactPercent', () => {
  test('returns dash for null', () => {
    expect(formatCompactPercent(null)).toBe('-');
  });

  test('returns dash for undefined', () => {
    expect(formatCompactPercent(undefined)).toBe('-');
  });

  test('formats positive percentage with plus sign', () => {
    expect(formatCompactPercent(5.5)).toBe('+5.5%');
    expect(formatCompactPercent(0)).toBe('+0.0%');
    expect(formatCompactPercent(100)).toBe('+100.0%');
  });

  test('formats negative percentage', () => {
    expect(formatCompactPercent(-5.5)).toBe('-5.5%');
    expect(formatCompactPercent(-100)).toBe('-100.0%');
  });

  test('handles string input', () => {
    expect(formatCompactPercent('5.5')).toBe('+5.5%');
  });

  test('handles decimal places', () => {
    // Note: JavaScript's toFixed uses banker's rounding
    expect(formatCompactPercent(5.56)).toBe('+5.6%');
    expect(formatCompactPercent(5.54)).toBe('+5.5%');
  });
});
