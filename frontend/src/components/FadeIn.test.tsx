import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider, createTheme } from '@mui/material';
import FadeIn from './FadeIn';

const theme = createTheme({
  palette: {
    mode: 'dark',
  },
});

const renderWithTheme = (component: React.ReactElement) => {
  return render(
    <ThemeProvider theme={theme}>
      {component}
    </ThemeProvider>
  );
};

describe('FadeIn', () => {
  describe('basic rendering', () => {
    it('renders children', () => {
      renderWithTheme(
        <FadeIn>
          <div data-testid="test-content">Test Content</div>
        </FadeIn>
      );
      expect(screen.getByTestId('test-content')).toBeInTheDocument();
    });

    it('renders text children', () => {
      renderWithTheme(
        <FadeIn>Hello World</FadeIn>
      );
      expect(screen.getByText('Hello World')).toBeInTheDocument();
    });
  });

  describe('animation props', () => {
    it('uses default duration of 0.5s', () => {
      const { container } = renderWithTheme(
        <FadeIn>
          <div>Content</div>
        </FadeIn>
      );
      const box = container.firstChild as HTMLElement;
      const style = window.getComputedStyle(box);
      expect(style.animation).toContain('0.5s');
    });

    it('uses custom duration', () => {
      const { container } = renderWithTheme(
        <FadeIn duration={1}>
          <div>Content</div>
        </FadeIn>
      );
      const box = container.firstChild as HTMLElement;
      const style = window.getComputedStyle(box);
      expect(style.animation).toContain('1s');
    });

    it('uses default delay of 0', () => {
      const { container } = renderWithTheme(
        <FadeIn>
          <div>Content</div>
        </FadeIn>
      );
      const box = container.firstChild as HTMLElement;
      const style = window.getComputedStyle(box);
      expect(style.animation).toContain('0s both');
    });

    it('uses custom delay', () => {
      const { container } = renderWithTheme(
        <FadeIn delay={0.5}>
          <div>Content</div>
        </FadeIn>
      );
      const box = container.firstChild as HTMLElement;
      const style = window.getComputedStyle(box);
      expect(style.animation).toContain('0.5s');
    });
  });

  describe('sx prop', () => {
    it('applies custom sx prop', () => {
      const { container } = renderWithTheme(
        <FadeIn sx={{ padding: 2 }}>
          <div>Content</div>
        </FadeIn>
      );
      const box = container.firstChild as HTMLElement;
      expect(box).toBeInTheDocument();
    });

    it('uses empty sx by default', () => {
      const { container } = renderWithTheme(
        <FadeIn>
          <div>Content</div>
        </FadeIn>
      );
      expect(container.firstChild).toBeInTheDocument();
    });
  });
});
