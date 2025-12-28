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
    expect(screen.getByLabelText(/required pyramids for timer/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/wait time after conditions met/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max winners to combine/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/max realized loss/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/enable partial close of winners/i)).toBeInTheDocument();
  });
});