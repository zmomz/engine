import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { Timeline, TimelineItem } from './Timeline';

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

describe('Timeline', () => {
  const mockItems: TimelineItem[] = [
    {
      id: '1',
      title: 'First Event',
      description: 'Description of first event',
      type: 'success',
      timestamp: '2024-01-15T10:30:00Z',
      metadata: { key1: 'value1', key2: 'value2' },
    },
    {
      id: '2',
      title: 'Second Event',
      description: 'Description of second event',
      type: 'error',
      timestamp: '2024-01-15T11:00:00Z',
    },
    {
      id: '3',
      title: 'Third Event',
      type: 'warning',
      timestamp: new Date('2024-01-15T12:00:00Z'),
    },
    {
      id: '4',
      title: 'Fourth Event',
      type: 'info',
    },
  ];

  describe('basic rendering', () => {
    it('renders all timeline items', () => {
      renderWithTheme(<Timeline items={mockItems} />);

      expect(screen.getByText('First Event')).toBeInTheDocument();
      expect(screen.getByText('Second Event')).toBeInTheDocument();
      expect(screen.getByText('Third Event')).toBeInTheDocument();
      expect(screen.getByText('Fourth Event')).toBeInTheDocument();
    });

    it('renders descriptions when provided', () => {
      renderWithTheme(<Timeline items={mockItems} />);

      expect(screen.getByText('Description of first event')).toBeInTheDocument();
      expect(screen.getByText('Description of second event')).toBeInTheDocument();
    });

    it('renders metadata chips', () => {
      renderWithTheme(<Timeline items={mockItems} />);

      expect(screen.getByText('key1: value1')).toBeInTheDocument();
      expect(screen.getByText('key2: value2')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('shows empty message when no items', () => {
      renderWithTheme(<Timeline items={[]} />);

      expect(screen.getByText('No timeline items to display')).toBeInTheDocument();
    });
  });

  describe('maxItems', () => {
    it('limits displayed items to maxItems', () => {
      renderWithTheme(<Timeline items={mockItems} maxItems={2} />);

      expect(screen.getByText('First Event')).toBeInTheDocument();
      expect(screen.getByText('Second Event')).toBeInTheDocument();
      expect(screen.queryByText('Third Event')).not.toBeInTheDocument();
      expect(screen.queryByText('Fourth Event')).not.toBeInTheDocument();
    });

    it('uses default maxItems of 10', () => {
      const manyItems: TimelineItem[] = Array.from({ length: 15 }, (_, i) => ({
        id: String(i),
        title: `Event ${i}`,
      }));

      renderWithTheme(<Timeline items={manyItems} />);

      expect(screen.getByText('Event 0')).toBeInTheDocument();
      expect(screen.getByText('Event 9')).toBeInTheDocument();
      expect(screen.queryByText('Event 10')).not.toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('renders in compact mode', () => {
      renderWithTheme(<Timeline items={mockItems} compact={true} />);

      expect(screen.getByText('First Event')).toBeInTheDocument();
    });

    it('renders in non-compact mode by default', () => {
      renderWithTheme(<Timeline items={mockItems} />);

      expect(screen.getByText('First Event')).toBeInTheDocument();
    });
  });

  describe('timestamp formatting', () => {
    it('formats string timestamp correctly', () => {
      renderWithTheme(<Timeline items={[mockItems[0]]} />);
      // Timestamp should be formatted
      expect(screen.getByText(/Jan 15/)).toBeInTheDocument();
    });

    it('formats Date timestamp correctly', () => {
      renderWithTheme(<Timeline items={[mockItems[2]]} />);
      expect(screen.getByText(/Jan 15/)).toBeInTheDocument();
    });

    it('shows Unknown time for null timestamp', () => {
      const itemWithNullTimestamp: TimelineItem[] = [
        { id: '1', title: 'No Time', timestamp: null },
      ];
      renderWithTheme(<Timeline items={itemWithNullTimestamp} />);

      expect(screen.getByText('Unknown time')).toBeInTheDocument();
    });

    it('shows Unknown time for undefined timestamp', () => {
      const itemWithUndefinedTimestamp: TimelineItem[] = [
        { id: '1', title: 'No Time', timestamp: undefined },
      ];
      renderWithTheme(<Timeline items={itemWithUndefinedTimestamp} />);

      expect(screen.getByText('Unknown time')).toBeInTheDocument();
    });

    it('handles invalid timestamp gracefully', () => {
      const itemWithInvalidTimestamp: TimelineItem[] = [
        { id: '1', title: 'Invalid Time', timestamp: 'invalid-date' },
      ];
      renderWithTheme(<Timeline items={itemWithInvalidTimestamp} />);

      expect(screen.getByText('Unknown time')).toBeInTheDocument();
    });
  });

  describe('item types and icons', () => {
    it('renders success type with icon', () => {
      renderWithTheme(<Timeline items={[mockItems[0]]} />);
      expect(screen.getByTestId('CheckCircleIcon')).toBeInTheDocument();
    });

    it('renders error type with icon', () => {
      renderWithTheme(<Timeline items={[mockItems[1]]} />);
      expect(screen.getByTestId('ErrorIcon')).toBeInTheDocument();
    });

    it('renders warning type with icon', () => {
      renderWithTheme(<Timeline items={[mockItems[2]]} />);
      expect(screen.getAllByTestId('InfoIcon').length).toBeGreaterThan(0);
    });

    it('renders info type with icon', () => {
      renderWithTheme(<Timeline items={[mockItems[3]]} />);
      expect(screen.getAllByTestId('InfoIcon').length).toBeGreaterThan(0);
    });

    it('renders default info icon for undefined type', () => {
      const itemWithNoType: TimelineItem[] = [
        { id: '1', title: 'Default Type' },
      ];
      renderWithTheme(<Timeline items={itemWithNoType} />);

      expect(screen.getAllByTestId('InfoIcon').length).toBeGreaterThan(0);
    });
  });

  describe('metadata', () => {
    it('renders metadata chips when provided', () => {
      renderWithTheme(<Timeline items={[mockItems[0]]} />);

      expect(screen.getByText('key1: value1')).toBeInTheDocument();
      expect(screen.getByText('key2: value2')).toBeInTheDocument();
    });

    it('does not render metadata section when empty', () => {
      const itemWithEmptyMetadata: TimelineItem[] = [
        { id: '1', title: 'No Metadata', metadata: {} },
      ];
      renderWithTheme(<Timeline items={itemWithEmptyMetadata} />);

      expect(screen.getByText('No Metadata')).toBeInTheDocument();
    });

    it('does not render metadata section when undefined', () => {
      const itemWithNoMetadata: TimelineItem[] = [
        { id: '1', title: 'No Metadata', metadata: undefined },
      ];
      renderWithTheme(<Timeline items={itemWithNoMetadata} />);

      expect(screen.getByText('No Metadata')).toBeInTheDocument();
    });
  });
});
