import api from '../services/api';
import { dcaConfigApi, DCAConfiguration, DCAConfigurationCreate, DCAConfigurationUpdate } from './dcaConfig';

jest.mock('../services/api');

const mockApi = api as jest.Mocked<typeof api>;

describe('dcaConfigApi', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockConfig: DCAConfiguration = {
    id: 'config-123',
    user_id: 'user-456',
    pair: 'BTC/USDT',
    timeframe: 60,
    exchange: 'binance',
    entry_order_type: 'limit',
    dca_levels: [
      { gap_percent: 0, weight_percent: 50, tp_percent: 1.0 },
      { gap_percent: -1, weight_percent: 50, tp_percent: 0.5 },
    ],
    tp_mode: 'per_leg',
    tp_settings: { tp_aggregate_percent: 0 },
    max_pyramids: 5,
    use_custom_capital: false,
    custom_capital_usd: 200,
  };

  describe('getAll', () => {
    it('should fetch all DCA configurations', async () => {
      const mockConfigs = [mockConfig];
      mockApi.get.mockResolvedValueOnce({ data: mockConfigs });

      const result = await dcaConfigApi.getAll();

      expect(mockApi.get).toHaveBeenCalledWith('/dca-configs/');
      expect(result).toEqual(mockConfigs);
    });

    it('should handle empty response', async () => {
      mockApi.get.mockResolvedValueOnce({ data: [] });

      const result = await dcaConfigApi.getAll();

      expect(result).toEqual([]);
    });

    it('should propagate API errors', async () => {
      const error = new Error('Network error');
      mockApi.get.mockRejectedValueOnce(error);

      await expect(dcaConfigApi.getAll()).rejects.toThrow('Network error');
    });
  });

  describe('create', () => {
    const createData: DCAConfigurationCreate = {
      pair: 'ETH/USDT',
      timeframe: 15,
      exchange: 'binance',
      entry_order_type: 'market',
      dca_levels: [
        { gap_percent: 0, weight_percent: 100, tp_percent: 1.0 },
      ],
      tp_mode: 'aggregate',
      tp_settings: { tp_aggregate_percent: 2.0 },
      max_pyramids: 3,
    };

    it('should create a new DCA configuration', async () => {
      const createdConfig = { ...mockConfig, ...createData, id: 'new-config-id' };
      mockApi.post.mockResolvedValueOnce({ data: createdConfig });

      const result = await dcaConfigApi.create(createData);

      expect(mockApi.post).toHaveBeenCalledWith('/dca-configs/', createData);
      expect(result).toEqual(createdConfig);
    });

    it('should handle API errors on create', async () => {
      const error = new Error('Validation failed');
      mockApi.post.mockRejectedValueOnce(error);

      await expect(dcaConfigApi.create(createData)).rejects.toThrow('Validation failed');
    });

    it('should create config with pyramid_specific_levels', async () => {
      const dataWithPyramids: DCAConfigurationCreate = {
        ...createData,
        pyramid_specific_levels: {
          '1': [{ gap_percent: 0, weight_percent: 100, tp_percent: 0.8 }],
        },
      };
      mockApi.post.mockResolvedValueOnce({ data: { ...mockConfig, ...dataWithPyramids } });

      await dcaConfigApi.create(dataWithPyramids);

      expect(mockApi.post).toHaveBeenCalledWith('/dca-configs/', dataWithPyramids);
    });

    it('should create config with custom capital settings', async () => {
      const dataWithCapital: DCAConfigurationCreate = {
        ...createData,
        use_custom_capital: true,
        custom_capital_usd: 500,
        pyramid_custom_capitals: { '0': 300, '1': 400 },
      };
      mockApi.post.mockResolvedValueOnce({ data: { ...mockConfig, ...dataWithCapital } });

      await dcaConfigApi.create(dataWithCapital);

      expect(mockApi.post).toHaveBeenCalledWith('/dca-configs/', dataWithCapital);
    });
  });

  describe('update', () => {
    const updateData: DCAConfigurationUpdate = {
      entry_order_type: 'market',
      max_pyramids: 7,
      tp_mode: 'hybrid',
    };

    it('should update an existing DCA configuration', async () => {
      const updatedConfig = { ...mockConfig, ...updateData };
      mockApi.put.mockResolvedValueOnce({ data: updatedConfig });

      const result = await dcaConfigApi.update('config-123', updateData);

      expect(mockApi.put).toHaveBeenCalledWith('/dca-configs/config-123', updateData);
      expect(result).toEqual(updatedConfig);
    });

    it('should handle API errors on update', async () => {
      const error = new Error('Config not found');
      mockApi.put.mockRejectedValueOnce(error);

      await expect(dcaConfigApi.update('invalid-id', updateData)).rejects.toThrow('Config not found');
    });

    it('should update DCA levels', async () => {
      const updateWithLevels: DCAConfigurationUpdate = {
        dca_levels: [
          { gap_percent: 0, weight_percent: 40, tp_percent: 1.5 },
          { gap_percent: -2, weight_percent: 60, tp_percent: 1.0 },
        ],
      };
      mockApi.put.mockResolvedValueOnce({ data: { ...mockConfig, ...updateWithLevels } });

      await dcaConfigApi.update('config-123', updateWithLevels);

      expect(mockApi.put).toHaveBeenCalledWith('/dca-configs/config-123', updateWithLevels);
    });

    it('should update TP settings', async () => {
      const updateWithTp: DCAConfigurationUpdate = {
        tp_mode: 'pyramid_aggregate',
        tp_settings: {
          tp_aggregate_percent: 3.0,
          pyramid_tp_percents: { '0': 2.0, '1': 2.5 },
        },
      };
      mockApi.put.mockResolvedValueOnce({ data: { ...mockConfig, ...updateWithTp } });

      await dcaConfigApi.update('config-123', updateWithTp);

      expect(mockApi.put).toHaveBeenCalledWith('/dca-configs/config-123', updateWithTp);
    });

    it('should update capital override settings', async () => {
      const updateWithCapital: DCAConfigurationUpdate = {
        use_custom_capital: true,
        custom_capital_usd: 1000,
        pyramid_custom_capitals: { '0': 500, '1': 750 },
      };
      mockApi.put.mockResolvedValueOnce({ data: { ...mockConfig, ...updateWithCapital } });

      await dcaConfigApi.update('config-123', updateWithCapital);

      expect(mockApi.put).toHaveBeenCalledWith('/dca-configs/config-123', updateWithCapital);
    });
  });

  describe('delete', () => {
    it('should delete a DCA configuration', async () => {
      mockApi.delete.mockResolvedValueOnce({ data: undefined });

      await dcaConfigApi.delete('config-123');

      expect(mockApi.delete).toHaveBeenCalledWith('/dca-configs/config-123');
    });

    it('should handle API errors on delete', async () => {
      const error = new Error('Deletion failed');
      mockApi.delete.mockRejectedValueOnce(error);

      await expect(dcaConfigApi.delete('config-123')).rejects.toThrow('Deletion failed');
    });

    it('should handle delete of non-existent config', async () => {
      const error = new Error('Config not found');
      mockApi.delete.mockRejectedValueOnce(error);

      await expect(dcaConfigApi.delete('non-existent')).rejects.toThrow('Config not found');
    });
  });
});
