import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import SettingsSectionCard from './SettingsSectionCard';
import { darkTheme } from '../../theme/theme';
import SettingsIcon from '@mui/icons-material/Settings';

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={darkTheme}>{component}</ThemeProvider>
  );
};

describe('SettingsSectionCard', () => {
  describe('Basic Rendering', () => {
    test('renders title', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test Title" icon={<SettingsIcon />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByText('Test Title')).toBeInTheDocument();
    });

    test('renders icon', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon data-testid="settings-icon" />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByTestId('settings-icon')).toBeInTheDocument();
    });

    test('renders children content', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>Child Content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByText('Child Content')).toBeInTheDocument();
    });

    test('renders inside a card', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      const card = document.querySelector('.MuiCard-root');
      expect(card).toBeInTheDocument();
    });
  });

  describe('Optional Description', () => {
    test('renders description when provided', () => {
      renderWithTheme(
        <SettingsSectionCard
          title="Test"
          icon={<SettingsIcon />}
          description="This is a description"
        >
          <div>Content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByText('This is a description')).toBeInTheDocument();
    });

    test('does not render description when not provided', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      // Should only have the title text, no description
      const caption = document.querySelector('.MuiTypography-caption');
      expect(caption).not.toBeInTheDocument();
    });
  });

  describe('Optional Action', () => {
    test('renders action when provided', () => {
      renderWithTheme(
        <SettingsSectionCard
          title="Test"
          icon={<SettingsIcon />}
          action={<button>Action Button</button>}
        >
          <div>Content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByRole('button', { name: /action button/i })).toBeInTheDocument();
    });

    test('does not render action container when not provided', () => {
      const { container } = renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      // Should not have an action button
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });
  });

  describe('Divider', () => {
    test('renders divider by default', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>Content</div>
        </SettingsSectionCard>
      );

      const divider = document.querySelector('.MuiDivider-root');
      expect(divider).toBeInTheDocument();
    });

    test('does not render divider when noDivider is true', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />} noDivider>
          <div>Content</div>
        </SettingsSectionCard>
      );

      const divider = document.querySelector('.MuiDivider-root');
      expect(divider).not.toBeInTheDocument();
    });
  });

  describe('Complex Children', () => {
    test('renders multiple children elements', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <div>First child</div>
          <div>Second child</div>
          <div>Third child</div>
        </SettingsSectionCard>
      );

      expect(screen.getByText('First child')).toBeInTheDocument();
      expect(screen.getByText('Second child')).toBeInTheDocument();
      expect(screen.getByText('Third child')).toBeInTheDocument();
    });

    test('renders nested components', () => {
      renderWithTheme(
        <SettingsSectionCard title="Test" icon={<SettingsIcon />}>
          <form>
            <input type="text" placeholder="Test input" />
            <button type="submit">Submit</button>
          </form>
        </SettingsSectionCard>
      );

      expect(screen.getByPlaceholderText('Test input')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument();
    });
  });

  describe('Full Configuration', () => {
    test('renders with all props', () => {
      renderWithTheme(
        <SettingsSectionCard
          title="Full Config Title"
          icon={<SettingsIcon data-testid="icon" />}
          description="Full description text"
          action={<button>Custom Action</button>}
          noDivider={false}
        >
          <div>Full config content</div>
        </SettingsSectionCard>
      );

      expect(screen.getByText('Full Config Title')).toBeInTheDocument();
      expect(screen.getByTestId('icon')).toBeInTheDocument();
      expect(screen.getByText('Full description text')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /custom action/i })).toBeInTheDocument();
      expect(screen.getByText('Full config content')).toBeInTheDocument();
      expect(document.querySelector('.MuiDivider-root')).toBeInTheDocument();
    });
  });
});
