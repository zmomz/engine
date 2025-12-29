import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { ThemeProvider, createTheme } from '@mui/material';
import RiskEngineSettings from './RiskEngineSettings';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const MockFormProvider = ({ children, defaultValues }: { children: React.ReactNode; defaultValues?: any }) => {
  const methods = useForm({
    defaultValues: defaultValues || {
      lossThresholdPercent: -2,
      requiredPyramidsForTimer: 2,
      postPyramidsWaitMinutes: 5,
      maxWinnersToCombine: 3,
      maxRealizedLossUsd: 100,
      partialCloseEnabled: true,
    },
  });
  return (
    <ThemeProvider theme={theme}>
      <FormProvider {...methods}>{children}</FormProvider>
    </ThemeProvider>
  );
};

describe('RiskEngineSettings', () => {
  describe('rendering', () => {
    test('renders title', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText('Risk Engine Configuration')).toBeInTheDocument();
    });

    test('renders description', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/Timer starts when BOTH conditions are met/)).toBeInTheDocument();
    });

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

  describe('helper texts', () => {
    test('displays loss threshold helper text', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/e\.g\., -1\.5 means timer starts when loss exceeds -1\.5%/)).toBeInTheDocument();
    });

    test('displays required pyramids helper text', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/Number of pyramids \(with all DCAs filled\) required before timer can start/)).toBeInTheDocument();
    });

    test('displays wait time helper text', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/Timer countdown duration before offset execution/)).toBeInTheDocument();
    });

    test('displays max winners helper text', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/Maximum winning positions to partially close for offset/)).toBeInTheDocument();
    });

    test('displays max realized loss helper text', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByText(/Queue stops releasing trades when this limit is reached/)).toBeInTheDocument();
    });
  });

  describe('field interactions', () => {
    test('updates loss threshold on change', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const input = screen.getByLabelText(/loss threshold/i);
      fireEvent.change(input, { target: { value: '-3' } });
      expect(input).toHaveValue(-3);
    });

    test('updates required pyramids on change', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const input = screen.getByLabelText(/required pyramids for timer/i);
      fireEvent.change(input, { target: { value: '5' } });
      expect(input).toHaveValue(5);
    });

    test('updates wait time on change', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const input = screen.getByLabelText(/wait time after conditions met/i);
      fireEvent.change(input, { target: { value: '10' } });
      expect(input).toHaveValue(10);
    });

    test('updates max winners on change', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const input = screen.getByLabelText(/max winners to combine/i);
      fireEvent.change(input, { target: { value: '5' } });
      expect(input).toHaveValue(5);
    });

    test('updates max realized loss on change', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const input = screen.getByLabelText(/max realized loss/i);
      fireEvent.change(input, { target: { value: '200' } });
      expect(input).toHaveValue(200);
    });

    test('toggles partial close checkbox', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      const checkbox = screen.getByLabelText(/enable partial close of winners/i);
      expect(checkbox).toBeChecked();
      fireEvent.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  describe('default values', () => {
    test('shows default values from form', () => {
      render(
        <MockFormProvider>
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByLabelText(/loss threshold/i)).toHaveValue(-2);
      expect(screen.getByLabelText(/required pyramids for timer/i)).toHaveValue(2);
      expect(screen.getByLabelText(/wait time after conditions met/i)).toHaveValue(5);
      expect(screen.getByLabelText(/max winners to combine/i)).toHaveValue(3);
      expect(screen.getByLabelText(/max realized loss/i)).toHaveValue(100);
    });

    test('shows different default values', () => {
      render(
        <MockFormProvider
          defaultValues={{
            lossThresholdPercent: -5,
            requiredPyramidsForTimer: 3,
            postPyramidsWaitMinutes: 10,
            maxWinnersToCombine: 5,
            maxRealizedLossUsd: 500,
            partialCloseEnabled: false,
          }}
        >
          <RiskEngineSettings />
        </MockFormProvider>
      );
      expect(screen.getByLabelText(/loss threshold/i)).toHaveValue(-5);
      expect(screen.getByLabelText(/required pyramids for timer/i)).toHaveValue(3);
      expect(screen.getByLabelText(/wait time after conditions met/i)).toHaveValue(10);
      expect(screen.getByLabelText(/max winners to combine/i)).toHaveValue(5);
      expect(screen.getByLabelText(/max realized loss/i)).toHaveValue(500);
      expect(screen.getByLabelText(/enable partial close of winners/i)).not.toBeChecked();
    });
  });
});