import { render, screen } from '@testing-library/react';
import ExchangeApiSettings from './ExchangeApiSettings';

describe('ExchangeApiSettings', () => {
  test('renders the form fields', () => {
    render(<ExchangeApiSettings />);
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api secret/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/testnet mode/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save settings/i })).toBeInTheDocument();
  });
});
