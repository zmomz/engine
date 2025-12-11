import api from '../services/api';

export type EntryOrderType = 'limit' | 'market';
export type TPMode = 'per_leg' | 'aggregate' | 'hybrid';

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
    tp_settings: Record<string, any>;
    max_pyramids: number;
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
    tp_settings: Record<string, any>;
    max_pyramids?: number;
}

export interface DCAConfigurationUpdate {
    entry_order_type?: EntryOrderType;
    dca_levels?: DCALevelConfig[];
    pyramid_specific_levels?: Record<string, DCALevelConfig[]>;
    tp_mode?: TPMode;
    tp_settings?: Record<string, any>;
    max_pyramids?: number;
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
