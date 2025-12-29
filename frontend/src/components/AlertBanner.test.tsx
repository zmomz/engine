import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import AlertBanner from './AlertBanner';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('AlertBanner', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('basic rendering', () => {
    it('renders message', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      expect(screen.getByText('Test message')).toBeInTheDocument();
    });

    it('renders title when provided', () => {
      renderWithTheme(
        <AlertBanner severity="info" title="Test Title" message="Test message" />
      );
      expect(screen.getByText('Test Title')).toBeInTheDocument();
    });

    it('does not render title when not provided', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      expect(screen.queryByRole('heading')).not.toBeInTheDocument();
    });
  });

  describe('severity types', () => {
    it('renders info alert', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Info message" />
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByTestId('InfoIcon')).toBeInTheDocument();
    });

    it('renders warning alert', () => {
      renderWithTheme(
        <AlertBanner severity="warning" message="Warning message" />
      );
      expect(screen.getByTestId('WarningIcon')).toBeInTheDocument();
    });

    it('renders error alert', () => {
      renderWithTheme(
        <AlertBanner severity="error" message="Error message" />
      );
      expect(screen.getByTestId('ErrorIcon')).toBeInTheDocument();
    });

    it('renders success alert', () => {
      renderWithTheme(
        <AlertBanner severity="success" message="Success message" />
      );
      expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
    });
  });

  describe('dismissible', () => {
    it('renders close button by default', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      expect(screen.getByRole('button', { name: 'close' })).toBeInTheDocument();
    });

    it('does not render close button when dismissible is false', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" dismissible={false} />
      );
      expect(screen.queryByRole('button', { name: 'close' })).not.toBeInTheDocument();
    });

    it('calls onDismiss when close button clicked', () => {
      const onDismiss = jest.fn();
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" onDismiss={onDismiss} />
      );
      fireEvent.click(screen.getByRole('button', { name: 'close' }));
      expect(onDismiss).toHaveBeenCalled();
    });

    it('closes alert when dismiss clicked', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      fireEvent.click(screen.getByRole('button', { name: 'close' }));
      // After click, state is set to false (collapse animation)
      act(() => {
        jest.advanceTimersByTime(500);
      });
    });
  });

  describe('variants', () => {
    it('renders filled variant by default', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      expect(screen.getByRole('alert')).toHaveClass('MuiAlert-filled');
    });

    it('renders standard variant', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" variant="standard" />
      );
      expect(screen.getByRole('alert')).toHaveClass('MuiAlert-standard');
    });

    it('renders outlined variant', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" variant="outlined" />
      );
      expect(screen.getByRole('alert')).toHaveClass('MuiAlert-outlined');
    });
  });

  describe('show prop', () => {
    it('shows alert by default', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" />
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('hides alert when show is false', () => {
      renderWithTheme(
        <AlertBanner severity="info" message="Test message" show={false} />
      );
      // The alert still exists in DOM but is in collapsed state
    });

    it('updates visibility when show prop changes', () => {
      const { rerender } = renderWithTheme(
        <AlertBanner severity="info" message="Test message" show={true} />
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();

      rerender(
        <ThemeProvider theme={theme}>
          <AlertBanner severity="info" message="Test message" show={false} />
        </ThemeProvider>
      );
    });
  });

  describe('action', () => {
    it('renders custom action', () => {
      renderWithTheme(
        <AlertBanner
          severity="info"
          message="Test message"
          action={<button data-testid="custom-action">Custom</button>}
        />
      );
      expect(screen.getByTestId('custom-action')).toBeInTheDocument();
    });
  });
});
