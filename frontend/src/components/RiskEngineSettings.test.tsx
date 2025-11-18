import { render, screen } from '@testing-library/react';
import RiskEngineSettings from './RiskEngineSettings';

describe('RiskEngineSettings', () => {
  test('renders all form fields', () => {
    render(<RiskEngineSettings />);
    expect(screen.getByLabelText(/loss threshold/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/use trade age filter/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/age threshold/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/require full pyramids/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/post-full wait/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/timer start condition/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save risk settings/i })).toBeInTheDocument();
  });
});
