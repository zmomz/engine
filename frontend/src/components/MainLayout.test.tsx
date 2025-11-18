import React from 'react';
import { render, screen } from '@testing-library/react';
import MainLayout from './MainLayout';

test('renders main layout', () => {
  render(<MainLayout><div>Test Content</div></MainLayout>);
  const linkElement = screen.getByText(/Test Content/i);
  expect(linkElement).toBeInTheDocument();
});
