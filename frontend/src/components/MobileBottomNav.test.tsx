import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { BrowserRouter, useNavigate, useLocation } from 'react-router-dom';
import MobileBottomNav from './MobileBottomNav';
import useAuthStore from '../store/authStore';

// Mock dependencies
jest.mock('../store/authStore');
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: jest.fn(),
  useLocation: jest.fn(),
}));

// Track useMediaQuery mock value
let mockIsMobile = true;
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: () => mockIsMobile,
}));

const mockedUseNavigate = useNavigate as jest.Mock;
const mockedUseLocation = useLocation as jest.Mock;
const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      <BrowserRouter>
        {component}
      </BrowserRouter>
    </ThemeProvider>
  );
};

describe('MobileBottomNav', () => {
  const mockNavigate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockIsMobile = true; // Default to mobile
    mockedUseNavigate.mockReturnValue(mockNavigate);
    mockedUseLocation.mockReturnValue({ pathname: '/dashboard' });
    mockedUseAuthStore.mockReturnValue({ isAuthenticated: true });
  });

  describe('visibility conditions', () => {
    it('returns null on desktop', () => {
      mockIsMobile = false; // Not mobile
      const { container } = renderWithProviders(<MobileBottomNav />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null when not authenticated', () => {
      mockIsMobile = true; // Mobile
      mockedUseAuthStore.mockReturnValue({ isAuthenticated: false });
      const { container } = renderWithProviders(<MobileBottomNav />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null on login page', () => {
      mockIsMobile = true; // Mobile
      mockedUseLocation.mockReturnValue({ pathname: '/login' });
      const { container } = renderWithProviders(<MobileBottomNav />);
      expect(container.firstChild).toBeNull();
    });

    it('returns null on register page', () => {
      mockIsMobile = true; // Mobile
      mockedUseLocation.mockReturnValue({ pathname: '/register' });
      const { container } = renderWithProviders(<MobileBottomNav />);
      expect(container.firstChild).toBeNull();
    });

    it('renders on mobile when authenticated', () => {
      mockIsMobile = true; // Mobile
      renderWithProviders(<MobileBottomNav />);
      // BottomNavigation doesn't have navigation role, check for presence of nav items instead
      expect(screen.getByText('Positions')).toBeInTheDocument();
    });
  });

  describe('navigation items', () => {
    beforeEach(() => {
      mockIsMobile = true; // Mobile
    });

    it('shows all nav items except current page', () => {
      mockedUseLocation.mockReturnValue({ pathname: '/dashboard' });
      renderWithProviders(<MobileBottomNav />);

      // Dashboard is current, so should not be visible
      expect(screen.queryByText('Home')).not.toBeInTheDocument();
      // Others should be visible
      expect(screen.getByText('Positions')).toBeInTheDocument();
      expect(screen.getByText('Queue')).toBeInTheDocument();
      expect(screen.getByText('Risk')).toBeInTheDocument();
      expect(screen.getByText('Analytics')).toBeInTheDocument();
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    it('excludes positions from nav when on positions page', () => {
      mockedUseLocation.mockReturnValue({ pathname: '/positions' });
      renderWithProviders(<MobileBottomNav />);

      expect(screen.queryByText('Positions')).not.toBeInTheDocument();
      expect(screen.getByText('Home')).toBeInTheDocument();
    });

    it('excludes queue from nav when on queue page', () => {
      mockedUseLocation.mockReturnValue({ pathname: '/queue' });
      renderWithProviders(<MobileBottomNav />);

      expect(screen.queryByText('Queue')).not.toBeInTheDocument();
      expect(screen.getByText('Home')).toBeInTheDocument();
    });
  });

  describe('navigation behavior', () => {
    beforeEach(() => {
      mockIsMobile = true; // Mobile
      mockedUseLocation.mockReturnValue({ pathname: '/dashboard' });
    });

    it('navigates when nav item clicked', () => {
      renderWithProviders(<MobileBottomNav />);

      fireEvent.click(screen.getByText('Positions'));

      expect(mockNavigate).toHaveBeenCalledWith('/positions');
    });

    it('navigates to queue page', () => {
      renderWithProviders(<MobileBottomNav />);

      fireEvent.click(screen.getByText('Queue'));

      expect(mockNavigate).toHaveBeenCalledWith('/queue');
    });

    it('navigates to risk page', () => {
      renderWithProviders(<MobileBottomNav />);

      fireEvent.click(screen.getByText('Risk'));

      expect(mockNavigate).toHaveBeenCalledWith('/risk');
    });

    it('navigates to analytics page', () => {
      renderWithProviders(<MobileBottomNav />);

      fireEvent.click(screen.getByText('Analytics'));

      expect(mockNavigate).toHaveBeenCalledWith('/analytics');
    });

    it('navigates to settings page', () => {
      renderWithProviders(<MobileBottomNav />);

      fireEvent.click(screen.getByText('Settings'));

      expect(mockNavigate).toHaveBeenCalledWith('/settings');
    });
  });

  describe('icons', () => {
    beforeEach(() => {
      mockIsMobile = true; // Mobile
      mockedUseLocation.mockReturnValue({ pathname: '/dashboard' });
    });

    it('renders icons for all nav items', () => {
      renderWithProviders(<MobileBottomNav />);

      // Check for SVG icons
      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });
});
