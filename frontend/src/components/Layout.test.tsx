import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Layout from './Layout';

// Mock the auth store
const mockLogout = jest.fn();
jest.mock('../store/authStore', () => ({
  __esModule: true,
  default: (selector: (state: { logout: () => void }) => unknown) =>
    selector({ logout: mockLogout }),
}));

const renderLayout = () => {
  return render(
    <MemoryRouter>
      <Layout />
    </MemoryRouter>
  );
};

describe('Layout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('navigation links', () => {
    it('renders Dashboard link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard');
    });

    it('renders Positions link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Positions' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Positions' })).toHaveAttribute('href', '/positions');
    });

    it('renders Queue link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Queue' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Queue' })).toHaveAttribute('href', '/queue');
    });

    it('renders Risk Engine link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Risk Engine' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Risk Engine' })).toHaveAttribute('href', '/risk-engine');
    });

    it('renders Logs link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Logs' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Logs' })).toHaveAttribute('href', '/logs');
    });

    it('renders Settings link', () => {
      renderLayout();
      expect(screen.getByRole('link', { name: 'Settings' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Settings' })).toHaveAttribute('href', '/settings');
    });
  });

  describe('logout functionality', () => {
    it('renders logout button', () => {
      renderLayout();
      expect(screen.getByRole('button', { name: 'Logout' })).toBeInTheDocument();
    });

    it('calls logout when button is clicked', () => {
      renderLayout();
      fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
  });

  describe('structure', () => {
    it('renders navigation element', () => {
      renderLayout();
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    it('renders list items for each nav item', () => {
      renderLayout();
      const listItems = screen.getAllByRole('listitem');
      expect(listItems).toHaveLength(7); // 6 links + 1 logout button
    });
  });
});
