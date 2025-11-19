import { render, screen } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import ExchangeApiSettings from './ExchangeApiSettings';

const MockFormProvider = ({ children }: { children: React.ReactNode }) => {
  const methods = useForm();
  return <FormProvider {...methods}>{children}</FormProvider>;
};

describe('ExchangeApiSettings', () => {
  test('renders the form fields', () => {
    render(
      <MockFormProvider>
        <ExchangeApiSettings />
      </MockFormProvider>
    );
    expect(screen.getByLabelText(/api key/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/api secret/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/testnet mode/i)).toBeInTheDocument();

  });
});