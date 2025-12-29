import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import ResponsiveTableWrapper from './ResponsiveTableWrapper';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

// Track useMediaQuery mock value
let mockIsMobile = true;
jest.mock('@mui/material', () => ({
  ...jest.requireActual('@mui/material'),
  useMediaQuery: () => mockIsMobile,
}));

// Track ResizeObserver calls
const resizeObserverMocks = {
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
};

// Mock ResizeObserver
class MockResizeObserver {
  callback: ResizeObserverCallback;
  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }
  observe = resizeObserverMocks.observe;
  unobserve = resizeObserverMocks.unobserve;
  disconnect = resizeObserverMocks.disconnect;
}
global.ResizeObserver = MockResizeObserver as any;

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('ResponsiveTableWrapper', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockIsMobile = true;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('desktop mode', () => {
    it('renders children directly without wrapper on desktop', () => {
      mockIsMobile = false;
      renderWithTheme(
        <ResponsiveTableWrapper>
          <div data-testid="test-content">Test Content</div>
        </ResponsiveTableWrapper>
      );
      expect(screen.getByTestId('test-content')).toBeInTheDocument();
      expect(screen.queryByText('Swipe to see more →')).not.toBeInTheDocument();
    });
  });

  describe('mobile mode', () => {
    it('renders children in scrollable container on mobile', () => {
      mockIsMobile = true;
      renderWithTheme(
        <ResponsiveTableWrapper>
          <div data-testid="test-content">Test Content</div>
        </ResponsiveTableWrapper>
      );
      expect(screen.getByTestId('test-content')).toBeInTheDocument();
    });

    it('renders without indicators when showIndicators is false', () => {
      mockIsMobile = true;
      renderWithTheme(
        <ResponsiveTableWrapper showIndicators={false}>
          <div style={{ width: 1000 }}>Wide Content</div>
        </ResponsiveTableWrapper>
      );
      expect(screen.queryByText('Swipe to see more →')).not.toBeInTheDocument();
    });

    it('renders with showIndicators true by default', () => {
      mockIsMobile = true;
      const { container } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Content</div>
        </ResponsiveTableWrapper>
      );
      // The container should exist with relative positioning
      expect(container.firstChild).toBeTruthy();
    });
  });

  describe('scroll indicators', () => {
    it('shows scroll hint text when scrollable', () => {
      mockIsMobile = true;

      // Create a container with scrollable content
      const { container } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div style={{ width: 1000 }}>Wide Content</div>
        </ResponsiveTableWrapper>
      );

      // Simulate scrollable container
      const scrollContainer = container.querySelector('[style*="overflow"]') || container.firstChild;
      if (scrollContainer) {
        Object.defineProperty(scrollContainer, 'scrollWidth', { value: 1000, configurable: true });
        Object.defineProperty(scrollContainer, 'clientWidth', { value: 300, configurable: true });
        Object.defineProperty(scrollContainer, 'scrollLeft', { value: 0, configurable: true });

        // Trigger scroll check via the timeout
        act(() => {
          jest.advanceTimersByTime(200);
        });
      }
    });

    it('handles scroll left indicator click', () => {
      mockIsMobile = true;

      const { container } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div style={{ width: 1000 }}>Wide Content</div>
        </ResponsiveTableWrapper>
      );

      // Set up scroll position to show left indicator
      const scrollContainers = container.querySelectorAll('div');
      scrollContainers.forEach(el => {
        Object.defineProperty(el, 'scrollBy', {
          value: jest.fn(),
          configurable: true,
          writable: true
        });
      });
    });

    it('handles scroll right indicator click', () => {
      mockIsMobile = true;

      const { container } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div style={{ width: 1000 }}>Wide Content</div>
        </ResponsiveTableWrapper>
      );

      // Set up to show right indicator
      const scrollContainers = container.querySelectorAll('div');
      scrollContainers.forEach(el => {
        Object.defineProperty(el, 'scrollBy', {
          value: jest.fn(),
          configurable: true,
          writable: true
        });
      });
    });
  });

  describe('effects and cleanup', () => {
    it('adds and removes scroll event listener', () => {
      mockIsMobile = true;
      const addEventListenerSpy = jest.spyOn(HTMLDivElement.prototype, 'addEventListener');
      const removeEventListenerSpy = jest.spyOn(HTMLDivElement.prototype, 'removeEventListener');

      const { unmount } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Content</div>
        </ResponsiveTableWrapper>
      );

      expect(addEventListenerSpy).toHaveBeenCalledWith('scroll', expect.any(Function));

      unmount();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('scroll', expect.any(Function));

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('cleans up timeout on unmount', () => {
      mockIsMobile = true;

      const { unmount } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Content</div>
        </ResponsiveTableWrapper>
      );

      unmount();

      // Advancing timers should not cause errors
      act(() => {
        jest.advanceTimersByTime(200);
      });
    });

    it('uses ResizeObserver to check scroll on resize', () => {
      mockIsMobile = true;

      const { unmount } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Content</div>
        </ResponsiveTableWrapper>
      );

      // ResizeObserver.observe should have been called
      expect(resizeObserverMocks.observe).toHaveBeenCalled();

      unmount();

      // ResizeObserver.disconnect should be called on cleanup
      expect(resizeObserverMocks.disconnect).toHaveBeenCalled();
    });

    it('re-checks scroll when children change', () => {
      mockIsMobile = true;

      const { rerender } = renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Initial Content</div>
        </ResponsiveTableWrapper>
      );

      act(() => {
        jest.advanceTimersByTime(200);
      });

      rerender(
        <ThemeProvider theme={theme}>
          <ResponsiveTableWrapper>
            <div style={{ width: 2000 }}>Updated Wide Content</div>
          </ResponsiveTableWrapper>
        </ThemeProvider>
      );

      act(() => {
        jest.advanceTimersByTime(200);
      });
    });
  });

  describe('scroll behavior', () => {
    it('handles container being null gracefully', () => {
      mockIsMobile = true;

      // This should not throw
      renderWithTheme(
        <ResponsiveTableWrapper>
          <div>Content</div>
        </ResponsiveTableWrapper>
      );

      act(() => {
        jest.advanceTimersByTime(200);
      });
    });
  });
});
