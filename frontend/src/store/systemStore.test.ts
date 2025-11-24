import { useSystemStore } from './systemStore';
import { act } from 'react-dom/test-utils';

describe('systemStore', () => {
  beforeEach(() => {
    useSystemStore.setState({
      engineStatus: 'Stopped',
      riskEngineStatus: 'Idle',
      alerts: [],
      theme: 'light',
    });
  });

  test('sets engine status', () => {
    act(() => {
      useSystemStore.getState().setEngineStatus('Running');
    });
    expect(useSystemStore.getState().engineStatus).toBe('Running');
  });

  test('adds alert', () => {
    const alert = { message: 'Error' };
    act(() => {
      useSystemStore.getState().addAlert(alert);
    });
    expect(useSystemStore.getState().alerts).toContain(alert);
  });

  test('clears alerts', () => {
    useSystemStore.setState({ alerts: [{ message: 'Error' }] });
    act(() => {
      useSystemStore.getState().clearAlerts();
    });
    expect(useSystemStore.getState().alerts).toHaveLength(0);
  });

  test('toggles theme', () => {
    expect(useSystemStore.getState().theme).toBe('light');
    act(() => {
      useSystemStore.getState().toggleTheme();
    });
    expect(useSystemStore.getState().theme).toBe('dark');
    act(() => {
      useSystemStore.getState().toggleTheme();
    });
    expect(useSystemStore.getState().theme).toBe('light');
  });
});
