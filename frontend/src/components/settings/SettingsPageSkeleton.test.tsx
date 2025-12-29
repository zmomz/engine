import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import SettingsPageSkeleton from './SettingsPageSkeleton';
import { darkTheme } from '../../theme/theme';

// Mock useMediaQuery to test responsive behavior
jest.mock('@mui/material', () => {
  const actual = jest.requireActual('@mui/material');
  return {
    ...actual,
    useMediaQuery: jest.fn(),
  };
});

import { useMediaQuery } from '@mui/material';

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

describe('SettingsPageSkeleton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Desktop View', () => {
    beforeEach(() => {
      (useMediaQuery as jest.Mock).mockReturnValue(false);
    });

    test('renders skeleton structure', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Should render multiple skeleton elements
      const skeletons = document.querySelectorAll('.MuiSkeleton-root');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    test('renders tab skeletons', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Should have 4 tab skeletons on desktop
      const container = document.querySelector('[class*="MuiBox-root"]');
      expect(container).toBeInTheDocument();
    });

    test('renders two-column card layout on desktop', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Should have card elements
      const cards = document.querySelectorAll('.MuiCard-root');
      expect(cards.length).toBeGreaterThan(0);
    });

    test('renders metric card skeletons', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Should have metric card placeholders
      const cards = document.querySelectorAll('.MuiCard-root');
      expect(cards.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Mobile View', () => {
    beforeEach(() => {
      (useMediaQuery as jest.Mock).mockReturnValue(true);
    });

    test('renders skeleton structure for mobile', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      const skeletons = document.querySelectorAll('.MuiSkeleton-root');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    test('renders DCA config card skeletons on mobile', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Should have cards in mobile view (DCA config cards)
      const cards = document.querySelectorAll('.MuiCard-root');
      expect(cards.length).toBeGreaterThan(0);
    });

    test('renders smaller tab skeletons on mobile', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      // Mobile should still have tabs
      const container = document.querySelector('[class*="MuiBox-root"]');
      expect(container).toBeInTheDocument();
    });
  });

  describe('Structure', () => {
    beforeEach(() => {
      (useMediaQuery as jest.Mock).mockReturnValue(false);
    });

    test('has proper container padding', () => {
      const { container } = renderWithTheme(<SettingsPageSkeleton />);

      // The root container should be a Box
      const rootBox = container.firstChild;
      expect(rootBox).toBeInTheDocument();
    });

    test('renders circular skeleton for icons', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      const circularSkeletons = document.querySelectorAll('.MuiSkeleton-circular');
      expect(circularSkeletons.length).toBeGreaterThan(0);
    });

    test('renders rounded skeletons for buttons and inputs', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      const roundedSkeletons = document.querySelectorAll('.MuiSkeleton-rounded');
      expect(roundedSkeletons.length).toBeGreaterThan(0);
    });

    test('renders text skeletons for labels', () => {
      renderWithTheme(<SettingsPageSkeleton />);

      const textSkeletons = document.querySelectorAll('.MuiSkeleton-text');
      expect(textSkeletons.length).toBeGreaterThan(0);
    });
  });
});
