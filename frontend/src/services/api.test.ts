// We must define the mock factory inline to avoid hoisting issues with variables
jest.mock('axios', () => {
  const mockRequestUse = jest.fn();
  const mockResponseUse = jest.fn();
  const mockEject = jest.fn();
  
  const mockInstance = {
    interceptors: {
      request: { use: mockRequestUse, eject: mockEject },
      response: { use: mockResponseUse, eject: mockEject },
    },
    defaults: { baseURL: 'http://localhost:8000/api/v1' },
    get: jest.fn(),
    post: jest.fn(),
  };
  
  return {
    create: jest.fn(() => mockInstance),
  };
});

jest.mock('../store/authStore', () => ({
  getState: jest.fn(),
}));

import axios from 'axios';

describe('API Service', () => {
  let api: any;
  let mockRequestUse: jest.Mock;
  let mockResponseUse: jest.Mock;
  let mockEject: jest.Mock;
  let mockCreate: jest.Mock;
  let isolatedAuthStore: any;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();

    // Re-setup axios mock spies since resetModules might clear them or we need fresh ones
    // Actually, jest.mock factory runs again if resetModules is called? 
    // Yes, but we need to capture the NEW spies.
    // But since the factory is defined at top level, how do we access the new spies?
    // We can't easily access the closure variables of the factory from here.
    
    // Alternative: Don't use factory closure variables. Use the imported axios module to find spies?
    // But axios.create returns a NEW mock instance every time?
    // In our factory: `create: jest.fn(() => mockInstance)` -> returns SAME instance.
    
    // Let's assume the factory is constant.
    // We need to get the spies from the *imported* axios in the isolated context.
    
    jest.isolateModules(() => {
      api = require('./api').default;
      const axiosModule = require('axios');
      // We need to dig into the mock to find the spies
      // Since our factory returns { create: ... }, and create returns mockInstance...
      // We can call create to get the instance and inspect it?
      // But api.ts already called it.
      
      // Since our factory returns the SAME mockInstance object every time (it's defined in closure scope of the module factory),
      // we might be sharing state if we are not careful.
      
      // Wait, if jest.resetModules() is called, the factory runs again?
      // Yes. So a NEW mockInstance is created.
      
      // We need to capture THAT instance's spies.
      // How?
      // We can spy on the result of require('axios').create() ?
      // But we don't call it, api.ts calls it.
      
      // We can inspect `api` itself! `api` IS the mockInstance (because axios.create returns it).
      
      isolatedAuthStore = require('../store/authStore');
    });
    
    // Now api is the axios instance used in api.ts
    mockRequestUse = api.interceptors.request.use;
    mockResponseUse = api.interceptors.response.use;
  });

  it('should have base URL configured', () => {
    expect(api.defaults.baseURL).toBe('http://localhost:8000/api/v1');
  });

  it('should register interceptors', () => {
    expect(mockRequestUse).toHaveBeenCalled();
    expect(mockResponseUse).toHaveBeenCalled();
  });

  describe('Interceptors Logic', () => {
    let requestOnFulfilled: any;
    let responseOnRejected: any;

    beforeEach(() => {
      if (mockRequestUse.mock.calls.length > 0) {
        requestOnFulfilled = mockRequestUse.mock.calls[0][0];
      }
      if (mockResponseUse.mock.calls.length > 0) {
        responseOnRejected = mockResponseUse.mock.calls[0][1];
      }
    });

    it('request interceptor should add Authorization header if token exists', () => {
      expect(requestOnFulfilled).toBeDefined();
      
      // Configure the ISOLATED auth store mock
      isolatedAuthStore.getState.mockReturnValue({ token: 'test-token' });
      
      const config = { headers: {} };
      const result = requestOnFulfilled(config);
      
      expect(result.headers.Authorization).toBe('Bearer test-token');
    });

    it('request interceptor should NOT add Authorization header if token is missing', () => {
      expect(requestOnFulfilled).toBeDefined();
      isolatedAuthStore.getState.mockReturnValue({ token: null });
      
      const config = { headers: {} };
      const result = requestOnFulfilled(config);
      
      expect(result.headers.Authorization).toBeUndefined();
    });

    it('response interceptor should handle 401 errors', async () => {
      expect(responseOnRejected).toBeDefined();
      const mockLogout = jest.fn();
      isolatedAuthStore.getState.mockReturnValue({ logout: mockLogout });

      Object.defineProperty(window, 'location', {
        value: { href: '' },
        writable: true
      });

      const error = { response: { status: 401 } };

      await expect(responseOnRejected(error)).rejects.toEqual(error);

      expect(mockLogout).toHaveBeenCalled();
      expect(window.location.href).toBe('/login');
    });

    it('response interceptor should pass through non-401 errors', async () => {
      expect(responseOnRejected).toBeDefined();
      const mockLogout = jest.fn();
      isolatedAuthStore.getState.mockReturnValue({ logout: mockLogout });

      const error = { response: { status: 500 } };

      await expect(responseOnRejected(error)).rejects.toEqual(error);

      expect(mockLogout).not.toHaveBeenCalled();
    });

    it('response interceptor should handle errors without response object', async () => {
      expect(responseOnRejected).toBeDefined();
      const mockLogout = jest.fn();
      isolatedAuthStore.getState.mockReturnValue({ logout: mockLogout });

      const error = { message: 'Network Error' };

      await expect(responseOnRejected(error)).rejects.toEqual(error);

      expect(mockLogout).not.toHaveBeenCalled();
    });

    it('request interceptor should reject on error', async () => {
      // Get the error handler (second argument to use)
      const requestOnError = mockRequestUse.mock.calls[0]?.[1];
      expect(requestOnError).toBeDefined();

      const error = new Error('Request setup failed');

      await expect(requestOnError(error)).rejects.toEqual(error);
    });

    it('response interceptor should pass through successful responses', () => {
      // Get the success handler (first argument to use)
      const responseOnFulfilled = mockResponseUse.mock.calls[0]?.[0];
      expect(responseOnFulfilled).toBeDefined();

      const response = { data: { message: 'success' }, status: 200 };
      const result = responseOnFulfilled(response);

      expect(result).toEqual(response);
    });
  });
});