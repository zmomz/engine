import { render, screen } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import ExecutionPoolSettings from './ExecutionPoolSettings';

const MockFormProvider = ({ children }: { children: React.ReactNode }) => {
  const methods = useForm();
  return <FormProvider {...methods}>{children}</FormProvider>;
};

describe('ExecutionPoolSettings', () => {
  test('renders the form fields', () => {
    render(
      <MockFormProvider>
        <ExecutionPoolSettings />
      </MockFormProvider>
    );
    expect(screen.getByLabelText(/max open groups/i)).toBeInTheDocument();

  });
});