
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

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

// Helper to get token (assuming stored in localStorage or handled by interceptor)
// Since we don't have the auth store context here easily, we rely on the global axios instance if configured, 
// or simple header injection. For now, assuming standard axios usage with interceptors in App.tsx or similar.
// If not, we might need to import the store.

const getAuthHeader = () => {
    const token = localStorage.getItem('token');
    return token ? { Authorization: `Bearer ${token}` } : {};
};

export const dcaConfigApi = {
    getAll: async (): Promise<DCAConfiguration[]> => {
        const response = await axios.get<DCAConfiguration[]>(`${API_URL}/dca-configs/`, {
            headers: getAuthHeader()
        });
        return response.data;
    },

    create: async (data: DCAConfigurationCreate): Promise<DCAConfiguration> => {
        const response = await axios.post<DCAConfiguration>(`${API_URL}/dca-configs/`, data, {
            headers: getAuthHeader()
        });
        return response.data;
    },

    update: async (id: string, data: DCAConfigurationUpdate): Promise<DCAConfiguration> => {
        const response = await axios.put<DCAConfiguration>(`${API_URL}/dca-configs/${id}`, data, {
            headers: getAuthHeader()
        });
        return response.data;
    },

    delete: async (id: string): Promise<void> => {
        await axios.delete(`${API_URL}/dca-configs/${id}`, {
            headers: getAuthHeader()
        });
    }
};
