import { render, screen } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

// Mock console.error to prevent logging during tests
const mockConsoleError = jest.spyOn(console, 'error').mockImplementation(() => {});

const ProblemChild = () => {
  throw new Error('Test error');
};

describe('ErrorBoundary', () => {
  afterAll(() => {
    mockConsoleError.mockRestore();
  });

  test('displays an error message when a child component throws an error', () => {
    render(
      <ErrorBoundary>
        <ProblemChild />
      </ErrorBoundary>
    );

    expect(screen.getByRole('heading', { name: /oops! something went wrong/i })).toBeInTheDocument();
    expect(screen.getByText(/an unexpected error has occurred/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument();
  });

  test('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Child Component</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Child Component')).toBeInTheDocument();
  });
});
