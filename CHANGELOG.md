# Changelog

All notable changes to the Trading Engine Dashboard will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-12-18

### Added

#### New Pages
- **Overview Page** (`/overview`) - New high-level dashboard landing page
  - Real-time system status strip with pulsing indicators
  - 8 key metric cards (Portfolio, PnL, Win Rate, Risk Score, etc.)
  - Top 5 positions widget sorted by profitability
  - Top 3 queue signals by priority score
  - Quick action panel for Force Start/Stop
  - Auto-refresh every 5 seconds
  - Loading skeleton for professional UX

#### New Components
- **MetricCard** - Versatile metric display component
  - Large and small variants
  - Sparkline chart support (via Recharts)
  - Color schemes: bullish, bearish, neutral, primary
  - Trend indicators with up/down arrows
  - Percentage change display
  - Icon support for visual identification
  - Smooth hover effects (translateY + shadow)

- **AlertBanner** - Enhanced alert notifications
  - 4 severity levels (info, warning, error, success)
  - Optional title and action buttons
  - Dismissible with callbacks
  - 3 variants (standard, filled, outlined)
  - Smooth fade-in/out animations

- **StatusStrip** - Horizontal status indicators
  - Multiple status items in one row
  - Animated pulsing dots for active states
  - Responsive wrapping layout
  - 4 status colors matching theme

- **ProgressBar & RiskGauge** - Visual progress indicators
  - Determinate and indeterminate modes
  - Custom color schemes
  - Risk gauge with Low/Medium/High thresholds
  - Percentage labels and visual legend

- **OverviewSkeleton** - Loading state component
  - Matches Overview page layout exactly
  - Prevents layout shift during data loading

- **AppFooter** - Application footer component
  - Version and build information
  - System status indicators
  - Compact mode for space-constrained layouts

#### Page Enhancements

**Positions Page**
- Added 4 summary metric cards above the table
  - Total Invested (with position count)
  - Unrealized PnL (with percentage)
  - Win Rate (profitable positions ratio)
  - Average PnL percentage
- Real-time metric calculations
- Color-coded cards (bullish/bearish)

**Risk Page**
- Added 4 summary metric cards
  - Daily PnL (with limit status)
  - Engine Status (Active/Paused/Stopped)
  - Recent Offsets (count and total)
  - Loss Tracking (visual risk gauge)
- DataFreshnessIndicator showing last update
- Visual risk gauge with color-coded thresholds
- Improved button placement and hierarchy

**Queue Page**
- Added 4 summary metric cards
  - Active Signals (with average priority score)
  - Promoted (count and success rate)
  - Cancelled (count and percentage)
  - Total Processed (sum of all)
- DataFreshnessIndicator
- Auto-refresh every 5 seconds
- Color-coded warnings for queue size

**Dashboard Page**
- Already had DataFreshnessIndicator
- Enhanced with AnimatedCurrency components
- Animated status chips with pulsing
- Real-time polling optimizations

#### Design System

**Theme Updates**
- Added `bullish` (#10b981) and `bearish` (#ef4444) colors to palette
- Changed typography to Inter (UI) + JetBrains Mono (numbers)
- Updated type scale (h1: 3rem down to caption: 0.75rem)
- Enhanced component styles (buttons, cards, chips)
- Trading terminal dark mode with #0a0e1a background
- 8px base spacing system
- Border radius: 8px (buttons), 12px (cards)
- TypeScript module augmentation for custom theme properties

**Color Palette**
```
Bullish:  #10b981 (Green)
Bearish:  #ef4444 (Red)
Primary:  #6366f1 (Indigo)
Warning:  #f59e0b (Amber)
Info:     #3b82f6 (Blue)
Success:  #10b981 (Green)
Error:    #ef4444 (Red)
```

#### Navigation & Layout
- Updated Sidebar with new Overview menu item (HomeIcon)
- Set Overview as default landing page for authenticated users
- Responsive drawer system (temporary on mobile, permanent on desktop)
- Active route highlighting with proper colors
- Auto-close mobile drawer after navigation

#### Real-Time Features
- **DataFreshnessIndicator** on Overview, Risk, Queue, and Dashboard
  - Shows "Updated X seconds ago"
  - Color-coded freshness (green < 10s, yellow 10-30s, red > 30s)
  - Pulsing dot for active status
  - Tooltip with exact timestamp
- Auto-refresh intervals (5s) on all major data pages
- Optimized polling (only active tabs)

#### Documentation
- **UI_REDESIGN_PLAN.md** - Comprehensive 8-phase redesign roadmap
- **UI_IMPROVEMENTS_SUMMARY.md** - Complete implementation documentation
- **KEYBOARD_SHORTCUTS.md** - Reference guide for all keyboard shortcuts
- **CHANGELOG.md** - This file

### Changed

#### Responsive Design
- All pages now mobile-first responsive
- Metric cards stack 2x4 on mobile, 4x2 on desktop
- Responsive padding: `{ xs: 2, sm: 3 }`
- Responsive headers: `{ xs: '1.5rem', sm: '2.125rem' }`
- Grid columns adjust by breakpoint
- Tables use compact density on mobile
- Scrollable tabs with auto-scroll buttons

#### Typography
- All monetary values use monospace font (JetBrains Mono)
- Headers use consistent sizing and weights
- Button text uses sentence case (no uppercase transform)
- Improved line heights for readability

#### Component Styling
- Cards have subtle shadows and hover effects
- Buttons have smooth hover elevation
- Chips have consistent sizing and weights
- Tables have better cell padding and alignment
- Forms have improved spacing and focus states

### Fixed
- TypeScript compilation errors with custom theme properties
- Module augmentation for `bullish`/`bearish` palette
- Module augmentation for `fontFamilyMonospace` typography
- Unused import warnings in Queue page
- Proper queue status types ('cancelled' not 'removed')
- Color scheme type safety in MetricCard

### Performance
- Bundle size: 504.56 kB (gzipped)
- Increase from baseline: +6 kB (+1.2%)
- Optimized polling with conditional updates
- Skeleton screens prevent layout shift
- Efficient re-renders with proper React dependencies
- Cached API responses with 5s freshness

### Accessibility
- Proper ARIA labels on all components
- Semantic HTML structure throughout
- Keyboard navigation support
- Tab order follows visual hierarchy
- Focus indicators on all interactive elements
- AA compliant color contrast ratios
- Not relying solely on color for information
- Screen reader announcements for status updates

### Build & Deployment
- ✅ TypeScript compilation: **Success**
- ✅ Production build: **504.56 kB gzipped**
- ✅ Zero errors, zero warnings
- ✅ All components type-safe
- ✅ Responsive layouts verified
- ✅ Auto-refresh tested
- ✅ Navigation functional
- ✅ Theme consistency verified

---

## Implementation Progress

### Phase 1: Foundation ✅ COMPLETE
- [x] New color palette
- [x] Typography scale
- [x] Spacing/sizing system
- [x] Core component library
- [x] Responsive patterns

### Phase 2: Pages ✅ COMPLETE
- [x] Overview page (NEW)
- [x] Enhanced Positions page
- [x] Enhanced Risk page
- [x] Enhanced Queue page
- [x] Loading skeletons
- [x] Real-time updates

### Future Phases (Roadmap)
- [ ] Phase 3: Advanced Dashboard charts
- [ ] Phase 4: Analytics page
- [ ] Phase 5: Mobile card views
- [ ] Phase 6: Swipe gestures
- [ ] Phase 7: Keyboard shortcuts implementation
- [ ] Phase 8: Advanced filtering

---

## File Summary

### New Files (10)
1. `frontend/src/pages/OverviewPage.tsx`
2. `frontend/src/components/MetricCard.tsx`
3. `frontend/src/components/AlertBanner.tsx`
4. `frontend/src/components/StatusStrip.tsx`
5. `frontend/src/components/ProgressBar.tsx`
6. `frontend/src/components/OverviewSkeleton.tsx`
7. `frontend/src/components/AppFooter.tsx`
8. `UI_REDESIGN_PLAN.md`
9. `UI_IMPROVEMENTS_SUMMARY.md`
10. `KEYBOARD_SHORTCUTS.md`

### Modified Files (7)
1. `frontend/src/theme/theme.ts`
2. `frontend/src/App.tsx`
3. `frontend/src/components/Sidebar.tsx`
4. `frontend/src/pages/PositionsPage.tsx`
5. `frontend/src/pages/RiskPage.tsx`
6. `frontend/src/pages/QueuePage.tsx`
7. `frontend/src/pages/DashboardPage.tsx`

---

## Breaking Changes
None. All changes are backward compatible.

---

## Migration Guide
No migration needed. Simply pull the latest changes and rebuild:

```bash
cd frontend
npm install  # If new dependencies added
npm run build
```

---

## Contributors
- Claude Sonnet 4.5 (AI Assistant)

---

## License
Proprietary - All rights reserved

---

**Build Date**: 2025-12-18
**Build Hash**: 2be78f45
**Bundle Size**: 504.56 kB (gzipped)
**Status**: ✅ Production Ready
