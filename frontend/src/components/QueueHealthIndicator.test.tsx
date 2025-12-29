import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import { QueueHealthIndicator } from './QueueHealthIndicator';

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

describe('QueueHealthIndicator', () => {
  describe('basic rendering', () => {
    it('renders Queue Health title', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={0} />);
      expect(screen.getByText('Queue Health')).toBeInTheDocument();
    });

    it('renders Queue Size label', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByText('Queue Size')).toBeInTheDocument();
    });

    it('renders Avg Wait label', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByText('Avg Wait')).toBeInTheDocument();
    });

    it('renders High Priority label', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByText('High Priority')).toBeInTheDocument();
    });
  });

  describe('health status - empty queue', () => {
    it('shows Empty status when queue size is 0', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={0} />);
      expect(screen.getByText('Empty')).toBeInTheDocument();
      expect(screen.getByText('No signals in queue')).toBeInTheDocument();
    });
  });

  describe('health status - healthy queue', () => {
    it('shows Healthy status when queue is within good threshold', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={2} />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('Queue is processing smoothly')).toBeInTheDocument();
    });

    it('shows Healthy at exactly good threshold', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={3} />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });
  });

  describe('health status - busy queue', () => {
    it('shows Busy status when queue exceeds good threshold', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={4} />);
      expect(screen.getByText('Busy')).toBeInTheDocument();
      expect(screen.getByText('Queue is getting busy')).toBeInTheDocument();
    });

    it('shows Busy at exactly warning threshold', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByText('Busy')).toBeInTheDocument();
    });
  });

  describe('health status - critical queue', () => {
    it('shows Critical status when queue exceeds warning threshold', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={6} />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('Queue backlog detected')).toBeInTheDocument();
    });

    it('shows Critical for large queue sizes', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={100} />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('custom thresholds', () => {
    it('respects custom thresholds', () => {
      renderWithTheme(
        <QueueHealthIndicator
          queueSize={8}
          thresholds={{ good: 10, warning: 20, critical: 30 }}
        />
      );
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('shows Busy with custom thresholds', () => {
      renderWithTheme(
        <QueueHealthIndicator
          queueSize={15}
          thresholds={{ good: 10, warning: 20, critical: 30 }}
        />
      );
      expect(screen.getByText('Busy')).toBeInTheDocument();
    });

    it('shows Critical with custom thresholds', () => {
      renderWithTheme(
        <QueueHealthIndicator
          queueSize={25}
          thresholds={{ good: 10, warning: 20, critical: 30 }}
        />
      );
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  describe('queue size display', () => {
    it('displays queue size correctly', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={7} />);
      expect(screen.getByText('7 / 10')).toBeInTheDocument();
    });

    it('displays custom critical threshold in size', () => {
      renderWithTheme(
        <QueueHealthIndicator
          queueSize={5}
          thresholds={{ good: 3, warning: 5, critical: 20 }}
        />
      );
      expect(screen.getByText('5 / 20')).toBeInTheDocument();
    });
  });

  describe('average wait time', () => {
    it('displays N/A when averageWaitTime is 0', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} averageWaitTime={0} />);
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });

    it('displays minutes for wait time less than 60', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} averageWaitTime={45} />);
      expect(screen.getByText('45m')).toBeInTheDocument();
    });

    it('displays hours and minutes for wait time >= 60', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} averageWaitTime={90} />);
      expect(screen.getByText('1h 30m')).toBeInTheDocument();
    });

    it('displays multiple hours correctly', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} averageWaitTime={150} />);
      expect(screen.getByText('2h 30m')).toBeInTheDocument();
    });

    it('rounds minutes correctly', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} averageWaitTime={45.7} />);
      expect(screen.getByText('46m')).toBeInTheDocument();
    });
  });

  describe('high priority count', () => {
    it('displays 0 when not provided', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByText('0')).toBeInTheDocument();
    });

    it('displays high priority count when provided', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} highPriorityCount={3} />);
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  describe('progress bar', () => {
    it('renders progress bar', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={5} />);
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('caps utilization at 100%', () => {
      renderWithTheme(<QueueHealthIndicator queueSize={20} />);
      // Should still render, just capped at 100%
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });
});
