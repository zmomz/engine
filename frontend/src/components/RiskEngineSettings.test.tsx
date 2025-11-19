import { render, screen } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import RiskEngineSettings from './RiskEngineSettings';

const MockFormProvider = ({ children }: { children: React.ReactNode }) => {
  const methods = useForm();
  return <FormProvider {...methods}>{children}</FormProvider>;
};

describe('RiskEngineSettings', () => {
  test('renders all form fields', () => {
    render(
      <MockFormProvider>
        <RiskEngineSettings />
      </MockFormProvider>
    );
    expect(screen.getByLabelText(/loss threshold/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/use trade age filter/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/age threshold/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/require full pyramids/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/post-full wait/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/timer start condition/i)).toBeInTheDocument();

  });
});