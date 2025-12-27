import api from '../services/api';

export type EntryOrderType = 'limit' | 'market';
export type TPMode = 'per_leg' | 'aggregate' | 'hybrid' | 'pyramid_aggregate';

export interface TPSettings {
    tp_aggregate_percent?: number;
    pyramid_tp_percents?: Record<string, number>;  // "0": 2.0, "1": 3.0, etc.
}

// Capital override settings for per-pyramid capital allocation
export interface CapitalSettings {
    use_custom_capital: boolean;  // Toggle: true = use custom capital, false = use webhook signal
    custom_capital_usd: number;   // Default capital in USD (default: 200)
    pyramid_custom_capitals?: Record<string, number>;  // Per-pyramid capital: "0": 200, "1": 300, etc.
}

export interface DCALevelConfig {
    gap_percent: number;
    weight_percent: number;
    tp_percent: number;
}

export interface DCAConfiguration {
    id: string;
    user_id: string;
    pair: string;
    timeframe: number;
    exchange: string;
    entry_order_type: EntryOrderType;
    dca_levels: DCALevelConfig[];
    pyramid_specific_levels?: Record<string, DCALevelConfig[]>;
    tp_mode: TPMode;
    tp_settings: TPSettings;
    max_pyramids: number;
    // Capital Override Settings
    use_custom_capital: boolean;
    custom_capital_usd: number;
    pyramid_custom_capitals?: Record<string, number>;
    created_at?: string;
    updated_at?: string;
}

export interface DCAConfigurationCreate {
    pair: string;
    timeframe: number;
    exchange: string;
    entry_order_type: EntryOrderType;
    dca_levels: DCALevelConfig[];
    pyramid_specific_levels?: Record<string, DCALevelConfig[]>;
    tp_mode: TPMode;
    tp_settings: TPSettings;
    max_pyramids?: number;
    // Capital Override Settings
    use_custom_capital?: boolean;
    custom_capital_usd?: number;
    pyramid_custom_capitals?: Record<string, number>;
}

export interface DCAConfigurationUpdate {
    entry_order_type?: EntryOrderType;
    dca_levels?: DCALevelConfig[];
    pyramid_specific_levels?: Record<string, DCALevelConfig[]>;
    tp_mode?: TPMode;
    tp_settings?: TPSettings;
    max_pyramids?: number;
    // Capital Override Settings
    use_custom_capital?: boolean;
    custom_capital_usd?: number;
    pyramid_custom_capitals?: Record<string, number>;
}

export const dcaConfigApi = {
    getAll: async (): Promise<DCAConfiguration[]> => {
        const response = await api.get<DCAConfiguration[]>('/dca-configs/');
        return response.data;
    },

    create: async (data: DCAConfigurationCreate): Promise<DCAConfiguration> => {
        const response = await api.post<DCAConfiguration>('/dca-configs/', data);
        return response.data;
    },

    update: async (id: string, data: DCAConfigurationUpdate): Promise<DCAConfiguration> => {
        const response = await api.put<DCAConfiguration>(`/dca-configs/${id}`, data);
        return response.data;
    },

    delete: async (id: string): Promise<void> => {
        await api.delete(`/dca-configs/${id}`);
    }
};
