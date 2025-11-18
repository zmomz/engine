import { render, screen } from '@testing-library/react';
import SettingsPage from './SettingsPage';
import { MemoryRouter } from 'react-router-dom';

describe('SettingsPage', () => {
  test('renders settings heading and tabs', () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: /settings/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /exchange api/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /risk engine/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /execution pool/i })).toBeInTheDocument();
  });
});
