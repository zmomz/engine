import { render, screen } from '@testing-library/react';
import ExecutionPoolSettings from './ExecutionPoolSettings';

describe('ExecutionPoolSettings', () => {
  test('renders the form fields', () => {
    render(<ExecutionPoolSettings />);
    expect(screen.getByLabelText(/max open groups/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save pool settings/i })).toBeInTheDocument();
  });
});
