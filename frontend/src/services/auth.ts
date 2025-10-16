import type {
  User,
  LoginRequest,
  SignUpRequest,
  AuthResponse,
  AuthError,
} from '../types';

const TOKEN_KEY = 'auth_token';

// Token management
export const getToken = (): string | null => {
  return localStorage.getItem(TOKEN_KEY);
};

export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token);
};

export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY);
};

// API call helper with auth header
const apiCall = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> => {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
    ...options.headers,
  };

  return fetch(`${endpoint}`, {
    ...options,
    headers,
  });
};

// Auth service functions
export const authService = {
  // Login user
  login: async (credentials: LoginRequest): Promise<AuthResponse> => {
    const response = await apiCall('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });

    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const authResponse: AuthResponse = await response.json();
    setToken(authResponse.token);
    return authResponse;
  },

  // Sign up user
  signup: async (userData: SignUpRequest): Promise<AuthResponse> => {
    const response = await apiCall('/auth/signup', {
      method: 'POST',
      body: JSON.stringify(userData),
    });

    if (!response.ok) {
      const error: AuthError = await response.json();
      throw new Error(error.detail || 'Signup failed');
    }

    const authResponse: AuthResponse = await response.json();
    setToken(authResponse.token);
    return authResponse;
  },

  // Get current user from backend
  getCurrentUser: async (): Promise<User> => {
    const response = await apiCall('/auth/me');

    if (!response.ok) {
      if (response.status === 401) {
        removeToken();
        localStorage.removeItem('user_data');
        throw new Error('Authentication expired');
      }
      throw new Error('Failed to get user information');
    }

    const user: User = await response.json();
    // Update localStorage with fresh user data
    storeUserData(user);
    return user;
  },

  // Logout user
  logout: (): void => {
    removeToken();
    localStorage.removeItem('user_data');
  },

  // Check if user is authenticated
  isAuthenticated: (): boolean => {
    return validateToken().isValid;
  },

  // Check display name availability
  checkDisplayNameAvailability: async (
    displayName: string
  ): Promise<boolean> => {
    const response = await apiCall(
      `/auth/check-display-name/${encodeURIComponent(displayName)}`
    );

    if (!response.ok) {
      throw new Error('Failed to check display name availability');
    }

    const result = await response.json();
    return result.available;
  },
};

// Centralized token validation utility
export const validateToken = (): {
  isValid: boolean;
  shouldRedirect: boolean;
} => {
  const token = getToken();

  if (!token) {
    return { isValid: false, shouldRedirect: true };
  }

  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const isExpired = payload.exp * 1000 < Date.now();

    if (isExpired) {
      removeToken();
      localStorage.removeItem('user_data');
      return { isValid: false, shouldRedirect: true };
    }

    return { isValid: true, shouldRedirect: false };
  } catch {
    removeToken();
    localStorage.removeItem('user_data');
    return { isValid: false, shouldRedirect: true };
  }
};

// Store user data in localStorage
export const storeUserData = (user: User): void => {
  localStorage.setItem('user_data', JSON.stringify(user));
};
