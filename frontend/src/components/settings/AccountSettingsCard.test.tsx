import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { useForm, FormProvider } from 'react-hook-form';
import AccountSettingsCard from './AccountSettingsCard';
import { darkTheme } from '../../theme/theme';

// Mock notification store
const mockShowNotification = jest.fn();
jest.mock('../../store/notificationStore', () => {
  const storeMock = jest.fn();
  (storeMock as any).getState = () => ({
    showNotification: mockShowNotification
  });
  return {
    __esModule: true,
    default: storeMock
  };
});

// Mock clipboard API
const mockWriteText = jest.fn();
Object.assign(navigator, {
  clipboard: {
    writeText: mockWriteText,
  },
});

// Wrapper component to provide form context
const FormWrapper: React.FC<{
  children: (control: any) => React.ReactNode;
  defaultValues?: Record<string, any>;
}> = ({ children, defaultValues = {} }) => {
  const methods = useForm({
    defaultValues: {
      appSettings: {
        username: 'testuser',
        email: 'test@example.com',
        webhook_secret: 'secret123',
        secure_signals: true,
        ...defaultValues,
      },
    },
  });

  return (
    <FormProvider {...methods}>
      <form>{children(methods.control)}</form>
    </FormProvider>
  );
};

const renderWithProviders = (
  webhookUrl = 'https://api.example.com/webhooks/user123/tradingview',
  defaultValues?: Record<string, any>,
  errors?: Record<string, any>
) => {
  return render(
    <ThemeProvider theme={darkTheme}>
      <FormWrapper defaultValues={defaultValues}>
        {(control) => (
          <AccountSettingsCard
            control={control}
            errors={errors}
            webhookUrl={webhookUrl}
          />
        )}
      </FormWrapper>
    </ThemeProvider>
  );
};

describe('AccountSettingsCard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    test('renders section title', () => {
      renderWithProviders();

      expect(screen.getByText('Account Settings')).toBeInTheDocument();
    });

    test('renders section description', () => {
      renderWithProviders();

      expect(screen.getByText('Your profile and webhook configuration')).toBeInTheDocument();
    });
  });

  describe('Form Fields', () => {
    test('renders username field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    });

    test('renders email field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    test('renders webhook URL field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/webhook url/i)).toBeInTheDocument();
    });

    test('renders webhook secret field', () => {
      renderWithProviders();

      expect(screen.getByLabelText(/webhook secret/i)).toBeInTheDocument();
    });

    test('displays default values', () => {
      renderWithProviders();

      expect(screen.getByDisplayValue('testuser')).toBeInTheDocument();
      expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('secret123')).toBeInTheDocument();
    });

    test('displays webhook URL', () => {
      renderWithProviders('https://api.example.com/webhooks/user123/tradingview');

      expect(screen.getByDisplayValue('https://api.example.com/webhooks/user123/tradingview')).toBeInTheDocument();
    });
  });

  describe('Webhook URL Field', () => {
    test('webhook URL field is readonly', () => {
      renderWithProviders();

      const webhookInput = screen.getByLabelText(/webhook url/i);
      expect(webhookInput).toHaveAttribute('readonly');
    });

    test('displays helper text for webhook URL', () => {
      renderWithProviders();

      expect(screen.getByText('Copy for TradingView alerts')).toBeInTheDocument();
    });

    test('copies webhook URL to clipboard when copy button clicked', () => {
      renderWithProviders('https://api.example.com/webhooks/user123/tradingview');

      const copyButton = screen.getByRole('button', { name: /copy to clipboard/i });
      fireEvent.click(copyButton);

      expect(mockWriteText).toHaveBeenCalledWith('https://api.example.com/webhooks/user123/tradingview');
      expect(mockShowNotification).toHaveBeenCalledWith(
        'Webhook URL copied to clipboard',
        'success'
      );
    });
  });

  describe('Webhook Secret Field', () => {
    test('webhook secret field is disabled', () => {
      renderWithProviders();

      const secretInput = screen.getByLabelText(/webhook secret/i);
      expect(secretInput).toBeDisabled();
    });

    test('displays helper text for webhook secret', () => {
      renderWithProviders();

      expect(screen.getByText('Auto-generated secret')).toBeInTheDocument();
    });
  });

  describe('Error States', () => {
    test('displays error for username', () => {
      const errors = {
        appSettings: {
          username: {
            message: 'Username is required',
          },
        },
      };

      renderWithProviders(undefined, undefined, errors);

      expect(screen.getByText('Username is required')).toBeInTheDocument();
    });

    test('displays error for email', () => {
      const errors = {
        appSettings: {
          email: {
            message: 'Invalid email address',
          },
        },
      };

      renderWithProviders(undefined, undefined, errors);

      expect(screen.getByText('Invalid email address')).toBeInTheDocument();
    });
  });

  describe('Input Interaction', () => {
    test('allows changing username', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/username/i);
      fireEvent.change(input, { target: { value: 'newuser' } });

      expect(input).toHaveValue('newuser');
    });

    test('allows changing email', () => {
      renderWithProviders();

      const input = screen.getByLabelText(/email/i);
      fireEvent.change(input, { target: { value: 'new@example.com' } });

      expect(input).toHaveValue('new@example.com');
    });
  });

  describe('Custom Default Values', () => {
    test('renders with custom default values', () => {
      renderWithProviders('https://api.test.com/webhook', {
        username: 'customuser',
        email: 'custom@test.com',
        webhook_secret: 'customsecret',
      });

      expect(screen.getByDisplayValue('customuser')).toBeInTheDocument();
      expect(screen.getByDisplayValue('custom@test.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('customsecret')).toBeInTheDocument();
    });
  });

  describe('Different Webhook URLs', () => {
    test('displays loading webhook URL', () => {
      renderWithProviders('Loading...');

      expect(screen.getByDisplayValue('Loading...')).toBeInTheDocument();
    });

    test('displays long webhook URL', () => {
      const longUrl = 'https://very-long-domain-name.example.com/api/v1/webhooks/user-with-long-id-123456789/tradingview';
      renderWithProviders(longUrl);

      expect(screen.getByDisplayValue(longUrl)).toBeInTheDocument();
    });
  });
});
