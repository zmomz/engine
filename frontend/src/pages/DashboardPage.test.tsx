import React from 'react';
import { render, screen } from '@testing-library/react';
import DashboardPage from './DashboardPage';

test('renders dashboard heading', () => {
  render(<DashboardPage />);
  const headingElement = screen.getByText(/Dashboard/i);
  expect(headingElement).toBeInTheDocument();
});
