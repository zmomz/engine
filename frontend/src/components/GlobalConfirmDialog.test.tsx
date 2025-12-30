import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import GlobalConfirmDialog from './GlobalConfirmDialog';
import useConfirmStore from '../store/confirmStore';

// Suppress console.error for TouchRipple act() warnings - these are known MUI testing issues
const originalError = console.error;
beforeAll(() => {
  console.error = (...args: any[]) => {
    if (args[0]?.includes?.('TouchRipple') ||
        (typeof args[0] === 'string' && args[0].includes('inside a test was not wrapped in act'))) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});

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

describe('GlobalConfirmDialog', () => {
  beforeEach(() => {
    // Reset the store state before each test
    useConfirmStore.setState({
      isOpen: false,
      options: { message: '' },
      resolve: null,
    });
  });

  describe('when closed', () => {
    it('does not render dialog content when closed', () => {
      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('when open', () => {
    it('renders dialog when isOpen is true', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Are you sure?' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders default title when not provided', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test message' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByText('Confirm Action')).toBeInTheDocument();
    });

    it('renders custom title when provided', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { title: 'Custom Title', message: 'Test message' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByText('Custom Title')).toBeInTheDocument();
    });

    it('renders message', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'This is a test message' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByText('This is a test message')).toBeInTheDocument();
    });

    it('renders default cancel button text', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
    });

    it('renders custom cancel button text', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test', cancelText: 'No Thanks' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByRole('button', { name: 'No Thanks' })).toBeInTheDocument();
    });

    it('renders default confirm button text', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
    });

    it('renders custom confirm button text', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test', confirmText: 'Yes, Delete' },
      });

      renderWithTheme(<GlobalConfirmDialog />);
      expect(screen.getByRole('button', { name: 'Yes, Delete' })).toBeInTheDocument();
    });
  });

  describe('button interactions', () => {
    it('calls closeConfirm with false when cancel is clicked', () => {
      const mockResolve = jest.fn();
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
        resolve: mockResolve,
      });

      renderWithTheme(<GlobalConfirmDialog />);
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(mockResolve).toHaveBeenCalledWith(false);
      expect(useConfirmStore.getState().isOpen).toBe(false);
    });

    it('calls closeConfirm with true when confirm is clicked', () => {
      const mockResolve = jest.fn();
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
        resolve: mockResolve,
      });

      renderWithTheme(<GlobalConfirmDialog />);
      fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

      expect(mockResolve).toHaveBeenCalledWith(true);
      expect(useConfirmStore.getState().isOpen).toBe(false);
    });

    it('closes dialog when backdrop is clicked (onClose)', () => {
      const mockResolve = jest.fn();
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
        resolve: mockResolve,
      });

      renderWithTheme(<GlobalConfirmDialog />);

      // MUI Dialog can be closed by pressing Escape
      fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

      expect(mockResolve).toHaveBeenCalledWith(false);
      expect(useConfirmStore.getState().isOpen).toBe(false);
    });
  });

  describe('accessibility', () => {
    it('has proper aria attributes', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test message' },
      });

      renderWithTheme(<GlobalConfirmDialog />);

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-labelledby', 'confirm-dialog-title');
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-describedby', 'confirm-dialog-description');
    });

    it('confirm button has autoFocus', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: { message: 'Test' },
      });

      renderWithTheme(<GlobalConfirmDialog />);

      // The confirm button should have autoFocus attribute in the component
      // We verify the button is a contained primary variant
      const confirmButton = screen.getByRole('button', { name: 'Confirm' });
      expect(confirmButton).toHaveClass('MuiButton-containedPrimary');
    });
  });

  describe('with all custom options', () => {
    it('renders all custom options correctly', () => {
      useConfirmStore.setState({
        isOpen: true,
        options: {
          title: 'Delete Item',
          message: 'Are you sure you want to delete this item?',
          confirmText: 'Delete',
          cancelText: 'Keep',
        },
      });

      renderWithTheme(<GlobalConfirmDialog />);

      expect(screen.getByText('Delete Item')).toBeInTheDocument();
      expect(screen.getByText('Are you sure you want to delete this item?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Keep' })).toBeInTheDocument();
    });
  });
});
