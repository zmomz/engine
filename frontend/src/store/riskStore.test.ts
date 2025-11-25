import useRiskStore from './riskStore';
import axios from 'axios';

jest.mock('axios');

describe('riskStore', () => {
  beforeEach(() => {
    useRiskStore.setState({
      status: null,
      loading: false,
      error: null,
    });
    jest.clearAllMocks();
  });

  it('fetchStatus should call API and update state', async () => {
    const mockStatus = {
      identified_loser: null,
      identified_winners: [],
      required_offset_usd: 0,
      risk_engine_running: true,
      config: {},
    };
    (axios.get as jest.Mock).mockResolvedValue({ data: mockStatus });

    await useRiskStore.getState().fetchStatus();

    expect(axios.get).toHaveBeenCalledWith('/risk/status');
    expect(useRiskStore.getState().status).toEqual(mockStatus);
    expect(useRiskStore.getState().loading).toBe(false);
  });

  it('runEvaluation should call API and refresh status', async () => {
    (axios.post as jest.Mock).mockResolvedValue({});
    (axios.get as jest.Mock).mockResolvedValue({ data: {} }); // Mock get for fetchStatus
    const fetchSpy = jest.spyOn(useRiskStore.getState(), 'fetchStatus');

    await useRiskStore.getState().runEvaluation();

    expect(axios.post).toHaveBeenCalledWith('/risk/run-evaluation');
    expect(fetchSpy).toHaveBeenCalled();
  });

  it('blockGroup should call API and refresh status', async () => {
    (axios.post as jest.Mock).mockResolvedValue({});
    (axios.get as jest.Mock).mockResolvedValue({ data: {} }); // Mock get for fetchStatus
    const fetchSpy = jest.spyOn(useRiskStore.getState(), 'fetchStatus');

    await useRiskStore.getState().blockGroup('123');

    expect(axios.post).toHaveBeenCalledWith('/risk/123/block');
    expect(fetchSpy).toHaveBeenCalled();
  });
});