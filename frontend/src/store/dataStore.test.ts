import { useDataStore } from './dataStore';
import { act } from 'react-dom/test-utils';

describe('dataStore', () => {
  beforeEach(() => {
    useDataStore.setState({
      positionGroups: [],
      queuedSignals: [],
      poolUsage: { active: 0, max: 0 },
      pnlMetrics: { unrealized_pnl: 0, realized_pnl: 0, total_pnl: 0 },
    });
  });

  test('updates position groups', () => {
    const groups = [{ id: '1' }];
    act(() => {
      useDataStore.getState().updatePositionGroups(groups);
    });
    expect(useDataStore.getState().positionGroups).toEqual(groups);
  });

  test('updates queued signals', () => {
    const signals = [{ id: 's1' }];
    act(() => {
      useDataStore.getState().updateQueuedSignals(signals);
    });
    expect(useDataStore.getState().queuedSignals).toEqual(signals);
  });

  test('sets initial data', () => {
    const data = {
      positionGroups: [{ id: '1' }],
      queuedSignals: [{ id: 's1' }],
      poolUsage: { active: 1, max: 10 },
      pnlMetrics: { unrealized_pnl: 100, realized_pnl: 50, total_pnl: 150 },
    };
    act(() => {
      useDataStore.getState().setInitialData(data);
    });
    expect(useDataStore.getState()).toMatchObject(data);
  });
});
