import React from 'react';
import { render, screen } from '@testing-library/react';
import DashboardPage from './DashboardPage';

test('renders dashboard heading', () => {
  render(<DashboardPage />);
  const headingElement = screen.getByText(/Dashboard - Global Overview/i);
  expect(headingElement).toBeInTheDocument();
});
