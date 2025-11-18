import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter as Router } from 'react-router-dom';
import MainLayout from './MainLayout';

describe('MainLayout', () => {
  const renderComponent = () =>
    render(
      <Router>
        <MainLayout>
          <div>Child Content</div>
        </MainLayout>
      </Router>
    );

  it('renders the header with the application title', () => {
    renderComponent();
    expect(screen.getByRole('heading', { name: /execution engine/i })).toBeInTheDocument();
  });

  it('renders the sidebar with navigation links', () => {
    renderComponent();
    expect(screen.getByRole('link', { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /positions/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /queue/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /risk engine/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /logs/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /settings/i })).toBeInTheDocument();
  });

  it('renders the child content', () => {
    renderComponent();
    expect(screen.getByText(/child content/i)).toBeInTheDocument();
  });

  it('renders the theme toggle button', () => {
    renderComponent();
    expect(screen.getByRole('button', { name: /toggle theme/i })).toBeInTheDocument();
  });

  it('renders the user menu with a logout option', () => {
    renderComponent();
    expect(screen.getByRole('button', { name: /user menu/i })).toBeInTheDocument();
    // Note: The logout option might only be visible after clicking the user menu.
    // This can be tested in a more interactive test.
  });
});