import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import WinLossWidget from './WinLossWidget';

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

describe('WinLossWidget', () => {
  it('renders title', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={7} losses={3} winRate={70} />);
    expect(screen.getByText('Trade Statistics')).toBeInTheDocument();
  });

  it('renders all stat labels', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={7} losses={3} winRate={70} />);

    expect(screen.getByText('Total Trades')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('Wins')).toBeInTheDocument();
    expect(screen.getByText('Losses')).toBeInTheDocument();
  });

  it('displays values correctly', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={7} losses={3} winRate={70} />);

    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByText('70.0%')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('displays dash for null totalTrades', () => {
    renderWithTheme(<WinLossWidget totalTrades={null} wins={7} losses={3} winRate={70} />);

    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(1);
  });

  it('displays dash for null wins', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={null} losses={3} winRate={70} />);

    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(1);
  });

  it('displays dash for null losses', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={7} losses={null} winRate={70} />);

    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(1);
  });

  it('displays dash for null winRate', () => {
    renderWithTheme(<WinLossWidget totalTrades={10} wins={7} losses={3} winRate={null} />);

    expect(screen.getAllByText('-').length).toBeGreaterThanOrEqual(1);
  });

  it('displays all dashes when all values are null', () => {
    renderWithTheme(<WinLossWidget totalTrades={null} wins={null} losses={null} winRate={null} />);

    const dashes = screen.getAllByText('-');
    expect(dashes.length).toBe(4);
  });

  it('displays zero values correctly', () => {
    renderWithTheme(<WinLossWidget totalTrades={0} wins={0} losses={0} winRate={0} />);

    expect(screen.getAllByText('0').length).toBe(3);
    expect(screen.getByText('0.0%')).toBeInTheDocument();
  });

  it('handles decimal win rate', () => {
    renderWithTheme(<WinLossWidget totalTrades={100} wins={66} losses={34} winRate={66.666} />);

    expect(screen.getByText('66.7%')).toBeInTheDocument();
  });
});
