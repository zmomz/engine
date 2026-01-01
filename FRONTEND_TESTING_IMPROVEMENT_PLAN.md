# Frontend Testing Improvement Plan

## Executive Summary

**Previous State:** 90.19% statement coverage, 83.53% branch coverage, **1206 tests** in 70 test suites
**Current State:** 90.68% statement coverage, 84.25% branch coverage, **1232 tests** in 71 test suites
**Target State:** 93%+ statement coverage, 88%+ branch coverage

### Completed Improvements

| Phase | Status | Tests Added | Description |
|-------|--------|-------------|-------------|
| 1.1 | DONE | 15 tests | dcaConfig API CRUD operations |
| 1.2 | DONE | 11 tests | DCAConfigForm pyramid handlers & validation |

### Coverage Overview

| Category | Statement | Branch | Function | Lines |
|----------|-----------|--------|----------|-------|
| Overall | 90.68% | 84.25% | 89.66% | 91.23% |
| Target | 93%+ | 88%+ | 92%+ | 93%+ |

### Identified Gaps by Priority

| Priority | Area | Current Coverage | Target | Est. Tests | Status |
|----------|------|-----------------|--------|------------|--------|
| HIGH | API modules (dcaConfig) | 100% | 90%+ | - | ✅ DONE |
| HIGH | DCAConfigForm.tsx | 77.02% | 90%+ | 10 tests | Improved |
| HIGH | SettingsPage.tsx | 75.89% | 90%+ | 12 tests | Pending |
| MEDIUM | RiskPage.tsx | 77.77% | 90%+ | 10 tests | Pending |
| MEDIUM | BackupRestoreCard.tsx | 80.76% | 95%+ | 6 tests | Pending |
| MEDIUM | PositionsPage.tsx | 85.22% | 92%+ | 8 tests | Pending |
| LOW | Skeleton components | 77-81% | 90%+ | 6 tests | Pending |
| LOW | DataFreshnessIndicator | 76.66% | 90%+ | 4 tests | Pending |

**Estimated Remaining Tests:** ~56 tests

---

## Phase 1: Critical Coverage Gaps

### 1.1 DCA Config API Module Tests ✅ COMPLETED

**File:** `src/api/dcaConfig.ts` (Current: 100%)
**Status:** All CRUD operations now fully tested

**New Test File:** `src/api/dcaConfig.test.ts`

```typescript
// Tests to add:
describe('dcaConfigApi', () => {
  describe('create', () => {
    it('should create a new DCA configuration');
    it('should handle API errors on create');
  });

  describe('update', () => {
    it('should update an existing DCA configuration');
    it('should handle API errors on update');
  });

  describe('delete', () => {
    it('should delete a DCA configuration');
    it('should handle API errors on delete');
  });

  describe('getAll', () => {
    it('should fetch all DCA configurations');
    it('should handle empty response');
  });
});
```

**Coverage Impact:** 37.5% → 100% ✅

### 1.2 DCAConfigForm Component Tests (Partially Improved)

**File:** `src/components/dca_config/DCAConfigForm.tsx` (Current: 77.02%)
**Gaps:**
- Lines 48, 120: Form validation error paths
- Lines 212-218: `handlePyramidTpChange` function
- Lines 223-229: `handlePyramidCapitalChange` function
- Lines 243-250: `handleTogglePyramidOverride` function
- Lines 366: Form submission
- Lines 458-551: Pyramid tab UI rendering (conditional branches)

**Tests to Add:**

```typescript
describe('DCAConfigForm', () => {
  describe('Pyramid-specific handlers', () => {
    it('should handle pyramid TP percentage change');
    it('should clear pyramid TP when set to null');
    it('should handle pyramid capital change');
    it('should clear pyramid capital when set to null');
    it('should toggle pyramid override on');
    it('should toggle pyramid override off and remove levels');
  });

  describe('Tab rendering', () => {
    it('should render pyramid tabs for each max_pyramids value');
    it('should show pyramid-specific TP field in pyramid_aggregate mode');
    it('should show pyramid-specific capital when custom capital enabled');
    it('should show override checkbox for pyramid tabs');
    it('should render DCALevelsEditor when pyramid override enabled');
  });

  describe('Form validation', () => {
    it('should validate total weight equals 100%');
    it('should show validation error for invalid weight sum');
    it('should require pair field');
    it('should validate positive TP percent');
  });

  describe('Form submission', () => {
    it('should call onSubmit with form data');
    it('should close dialog after successful submit');
  });
});
```

**Coverage Impact:** 68.91% → 77.02% (improved), target 92%+

### 1.3 SettingsPage Tests

**File:** `src/pages/SettingsPage.tsx` (Current: 75.89%)
**Gaps:**
- Lines 378-386: API key payload with testnet/account_type
- Lines 396-400: onError form validation tab switching
- Lines 431-446: handleSaveApiKeys with all conditions
- Lines 489-497: handleRestore DCA configuration conversion

**Tests to Add:**

```typescript
describe('SettingsPage', () => {
  describe('API Key handling', () => {
    it('should save API keys with testnet flag');
    it('should save API keys with account_type');
    it('should show warning when API key or secret missing');
    it('should clear form after successful save');
    it('should handle edit key by pre-filling form');
    it('should handle delete key with confirmation');
  });

  describe('Form error handling', () => {
    it('should switch to exchange tab on exchangeSettings error');
    it('should switch to risk tab on riskEngineConfig error');
    it('should switch to telegram tab on telegramSettings error');
    it('should switch to app tab on appSettings error');
  });

  describe('Backup restore', () => {
    it('should restore risk config');
    it('should restore and create new DCA configs');
    it('should restore and update existing DCA configs');
    it('should convert backup DCA level format correctly');
    it('should convert pyramid-specific levels correctly');
  });
});
```

**Coverage Impact:** 75.89% → 92%+

---

## Phase 2: Medium Priority Gaps

### 2.1 RiskPage Tests

**File:** `src/pages/RiskPage.tsx` (Current: 78.78%)
**Gaps:**
- Lines 54-59: Keyboard shortcuts callback
- Lines 64-65: Visibility refresh callback
- Lines 125: handleExecuteOffsetClick guard
- Lines 140-150: handleExecuteOffset full flow
- Lines 676, 761-762: UI conditional rendering

**Tests to Add:**

```typescript
describe('RiskPage', () => {
  describe('Keyboard shortcuts', () => {
    it('should refresh on keyboard shortcut');
    it('should trigger force start on shortcut');
    it('should trigger force stop on shortcut');
    it('should trigger run evaluation on shortcut');
  });

  describe('Offset execution', () => {
    it('should open offset preview dialog');
    it('should not open preview when no loser identified');
    it('should execute offset and close dialog');
    it('should handle offset execution error');
    it('should set executing state during offset');
  });

  describe('Position actions', () => {
    it('should block position with confirmation');
    it('should unblock position with confirmation');
    it('should skip next evaluation with confirmation');
  });
});
```

**Coverage Impact:** 78.78% → 92%+

### 2.2 BackupRestoreCard Tests

**File:** `src/components/settings/BackupRestoreCard.tsx` (Current: 80.76%)
**Gaps:** Lines 76-99 - handleBackup function

**Tests to Add:**

```typescript
describe('BackupRestoreCard', () => {
  describe('Backup', () => {
    it('should create backup with risk config and DCA configs');
    it('should download backup file with correct filename');
    it('should show success notification on backup');
    it('should handle backup error');
  });

  describe('Restore', () => {
    it('should read and parse uploaded file');
    it('should validate backup schema');
    it('should call onRestore with parsed data');
    it('should show error for invalid file format');
  });
});
```

**Coverage Impact:** 80.76% → 95%+

### 2.3 PositionsPage Tests

**File:** `src/pages/PositionsPage.tsx` (Current: 85.22%)
**Gaps:**
- Lines 91-92, 98-99: Keyboard shortcut handlers
- Lines 135, 168-170, 189: Various callbacks
- Lines 259, 602, 621: Conditional UI rendering
- Lines 840, 886-974: History and detail views

**Tests to Add:**

```typescript
describe('PositionsPage', () => {
  describe('Keyboard shortcuts', () => {
    it('should refresh positions on shortcut');
    it('should trigger close all on shortcut');
    it('should trigger cancel pyramids on shortcut');
  });

  describe('Position actions', () => {
    it('should close position with confirmation');
    it('should cancel pyramids with confirmation');
    it('should handle position close error');
  });

  describe('View modes', () => {
    it('should render active positions view');
    it('should render history view');
    it('should render detail view for selected position');
    it('should toggle between active and history');
  });
});
```

**Coverage Impact:** 85.22% → 92%+

---

## Phase 3: Low Priority Gaps

### 3.1 Skeleton Component Tests

**Files:** PositionsSkeleton, QueueSkeleton, RiskSkeleton (77-81%)

**Tests to Add:**

```typescript
describe('PositionsSkeleton', () => {
  it('should render with default count');
  it('should render with custom count');
  it('should match mobile layout on small screens');
});

describe('QueueSkeleton', () => {
  it('should render with default count');
  it('should render with custom count');
});

describe('RiskSkeleton', () => {
  it('should render all skeleton sections');
});
```

### 3.2 DataFreshnessIndicator Tests

**File:** `src/components/DataFreshnessIndicator.tsx` (Current: 76.66%)
**Gaps:** Lines 44-51 - stale data UI rendering

**Tests to Add:**

```typescript
describe('DataFreshnessIndicator', () => {
  it('should show fresh indicator for recent data');
  it('should show stale warning for old data');
  it('should format timestamp correctly');
  it('should handle null timestamp');
});
```

### 3.3 Other Component Gaps

**Components with 80-85% coverage:**

| Component | Gap Lines | Test Focus |
|-----------|-----------|------------|
| QueuePrioritySettings | 180-187 | Save priority settings flow |
| NotificationManager | 28, 34-36 | Auto-dismiss timing, error notifications |
| Header | 20-21 | Mobile menu toggle |
| AnimatedStatusChip | 39 | Animation completion callback |
| ErrorBoundary | 47 | componentDidCatch logging |

---

## Phase 4: Branch Coverage Improvements

### Current Branch Coverage Issues

Many components have lower branch coverage due to:

1. **Conditional rendering** - ternary operators not fully tested
2. **Optional chaining** - `?.` operators in JSX
3. **Default values** - `|| defaultValue` patterns
4. **Error paths** - try/catch blocks

### Strategy

For each component with <90% branch coverage:

1. Identify conditional branches using coverage report
2. Add test cases for both true/false paths
3. Test edge cases (null, undefined, empty arrays)

**Priority Components for Branch Coverage:**

| Component | Branch % | Focus |
|-----------|----------|-------|
| DCAConfigForm | 55.1% | Conditional fields based on tp_mode |
| QueuePrioritySettings | 62.5% | Priority rules toggles |
| ResponsiveTableWrapper | 66.66% | Mobile vs desktop rendering |
| DataFreshnessIndicator | 73.68% | Stale state conditions |
| Header | 75% | Mobile menu state |
| TelegramSettings | 76.74% | Configuration toggles |

---

## Exclusions (Intentionally Not Covered)

These files can be excluded from coverage requirements:

| File | Reason |
|------|--------|
| `src/index.tsx` | CRA bootstrap code, no testable logic |
| `src/reportWebVitals.ts` | CRA boilerplate for metrics |
| `src/components/settings/index.ts` | Barrel export file |

**Jest Configuration Update:**

```javascript
// jest.config.js or package.json
collectCoverageFrom: [
  "src/**/*.{ts,tsx}",
  "!src/index.tsx",
  "!src/reportWebVitals.ts",
  "!src/**/index.ts"
]
```

---

## Implementation Order

### Week 1: Phase 1 (Critical)
- [ ] 1.1 DCA Config API tests (8 tests)
- [ ] 1.2 DCAConfigForm tests (15 tests)
- [ ] 1.3 SettingsPage tests (12 tests)

### Week 2: Phase 2 (Medium)
- [ ] 2.1 RiskPage tests (10 tests)
- [ ] 2.2 BackupRestoreCard tests (6 tests)
- [ ] 2.3 PositionsPage tests (8 tests)

### Week 3: Phase 3 & 4 (Low + Branch)
- [ ] 3.1 Skeleton component tests (6 tests)
- [ ] 3.2 DataFreshnessIndicator tests (4 tests)
- [ ] 3.3 Remaining component gaps
- [ ] 4.0 Branch coverage improvements

---

## Success Metrics

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Total Tests | 1232 | 1275+ | In Progress |
| Statement Coverage | 90.68% | 93%+ | In Progress |
| Branch Coverage | 84.25% | 88%+ | In Progress |
| Function Coverage | 89.66% | 92%+ | In Progress |
| Lines Coverage | 91.23% | 93%+ | In Progress |

---

## Test Infrastructure Notes

### Existing Patterns

The codebase follows good testing patterns:

1. **Component mocking** - Child components are mocked in page tests
2. **Store mocking** - Zustand stores are mocked with jest.mock()
3. **Theme provider** - Tests wrap components in ThemeProvider
4. **Router context** - MemoryRouter used for routing tests
5. **User events** - @testing-library/user-event for interactions

### Recommended Test Utilities

```typescript
// test-utils.tsx
import { render } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { MemoryRouter } from 'react-router-dom';
import { darkTheme } from '../theme/theme';

export const renderWithProviders = (ui: React.ReactElement, options = {}) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </ThemeProvider>,
    options
  );
};
```

---

## Quick Reference: New Test Commands

```bash
# Run all frontend tests
cd frontend && npm test

# Run tests with coverage
npm test -- --coverage

# Run specific test file
npm test -- DCAConfigForm.test.tsx

# Run tests matching pattern
npm test -- --testPathPattern="settings"

# Update snapshots if needed
npm test -- --updateSnapshot
```

---

## Phase 5: Test Quality Improvements

### Quality Assessment (Current: 7.5/10)

Beyond coverage metrics, test quality matters. Based on analysis:

| Quality Aspect | Score | Notes |
|----------------|-------|-------|
| Assertion Quality | 7.5/10 | Many tests check existence, not values |
| Mock Usage | 7/10 | Some over-mocking hiding integration bugs |
| Edge Cases | 8/10 | Good boundary testing in most areas |
| Error Paths | 7.5/10 | Some error scenarios untested |
| Test Isolation | 8.5/10 | Good use of beforeEach/afterEach |

### Quality Patterns to Enforce

**1. Strong Assertions (not weak)**
```typescript
// BAD - Weak assertion
expect(result).toBeDefined();
expect(config.id).not.toBeNull();

// GOOD - Strong assertion
expect(result).toEqual({ id: 'expected-id', status: 'active' });
expect(config.id).toBe('f937c6cb-f9f9-4d25-be19-db9bf596d7e1');
```

**2. Verify Mock Arguments (not just calls)**
```typescript
// BAD - Just checking if called
expect(mockApi.create).toHaveBeenCalled();

// GOOD - Verify exact arguments
expect(mockApi.create).toHaveBeenCalledWith({
  pair: 'BTC/USDT',
  tp_mode: 'per_leg',
  levels: expect.arrayContaining([
    expect.objectContaining({ gap_percent: 0 })
  ])
});
```

**3. Test Error States Explicitly**
```typescript
// GOOD - Test specific error handling
it('should show error message for network failure', async () => {
  mockApi.fetch.mockRejectedValue(new Error('Network Error'));
  render(<Component />);
  await waitFor(() => {
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });
});
```

**4. Test State Transitions**
```typescript
// GOOD - Verify state changes through workflow
it('should update status through save workflow', async () => {
  render(<Form />);
  expect(screen.getByRole('button', { name: /save/i })).toBeEnabled();

  fireEvent.click(screen.getByRole('button', { name: /save/i }));
  expect(screen.getByRole('button', { name: /saving/i })).toBeDisabled();

  await waitFor(() => {
    expect(screen.getByText(/saved successfully/i)).toBeInTheDocument();
  });
});
```

### Reference: Backend Quality Tests

See `tests/test_quality_assertions.py` for backend examples demonstrating:
- Strong assertion patterns for database models
- Partial failure scenarios (exchange succeeds, DB fails)
- Network timeout handling
- Decimal precision boundary testing
- Mock argument validation patterns

---

## Conclusion

The frontend test suite is in good shape with 90%+ coverage overall. The main improvement areas are:

1. **API module tests** - Low coverage on CRUD operations
2. **Complex form components** - DCAConfigForm has many untested branches
3. **Page-level interactions** - Settings, Risk, and Positions pages need more action testing
4. **Branch coverage** - Many conditional UI paths need explicit tests
5. **Test quality** - Move from "does it run?" to "is it correct?" assertions

Implementing these improvements will bring the test suite to production-quality coverage levels.
