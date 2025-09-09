import type { AuthResponse, PreferencesRequest, CategoryTree } from '../types';
import { apiRequest, ServiceLogger } from './api';

export const setPreferences = async (
  preferences: PreferencesRequest
): Promise<AuthResponse> => {
  ServiceLogger.logServiceCall('setPreferences', { preferences });
  return apiRequest<AuthResponse>('/users/preferences', 'setPreferences', {
    method: 'POST',
    body: preferences,
  });
};

export const getPreferences = async (): Promise<string> => {
  ServiceLogger.logServiceCall('getPreferences');
  return apiRequest<string>('/users/preferences', 'getPreferences');
};

// Get all parent/rootcategories
export const getParentCategories = async (): Promise<CategoryTree[]> => {
  ServiceLogger.logServiceCall('getParentCategories');
  return apiRequest<CategoryTree[]>(
    '/users/categories/parents-only',
    'getParentCategories'
  );
};

// Get all categories in hierarchical tree structure
export const getCategories = async (): Promise<CategoryTree[]> => {
  ServiceLogger.logServiceCall('getCategories');
  return apiRequest<CategoryTree[]>('/users/categories', 'getCategories');
};

// Get subcategories for a given parent category
export const getSubcategories = async (
  categoryId: string
): Promise<CategoryTree[]> => {
  ServiceLogger.logServiceCall('getSubcategories', { categoryId });
  return apiRequest<CategoryTree[]>(
    `/users/categories/${categoryId}/subcategories`,
    'getSubcategories'
  );
};
