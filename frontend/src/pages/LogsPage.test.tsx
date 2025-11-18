import { render, screen } from '@testing-library/react';
import LogsPage from './LogsPage';

describe('LogsPage', () => {
  test('renders the logs page heading and filter controls', () => {
    render(<LogsPage />);
    expect(screen.getByRole('heading', { name: /system logs/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/filter by level/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/search logs/i)).toBeInTheDocument();
  });
});
