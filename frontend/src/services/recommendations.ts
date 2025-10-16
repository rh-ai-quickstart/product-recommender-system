import type { ProductData, TopProductsParams } from '../types';
import { apiRequest, ServiceLogger } from './api';

/**
 * Fetch personalized recommendations for users with existing interaction history
 * These recommendations use the user's past behavior to suggest relevant products
 */
export const fetchExistingUserRecommendations = async (
  userId: string
): Promise<ProductData[]> => {
  ServiceLogger.logServiceCall('fetchExistingUserRecommendations', { userId });
  return apiRequest<ProductData[]>(
    `/recommendations/${userId}`,
    'fetchExistingUserRecommendations'
  );
};

// Get top products in a category
export const getTopProductsInCategory = async (
  categoryId: string,
  params?: TopProductsParams
): Promise<ProductData[]> => {
  ServiceLogger.logServiceCall('getTopProductsInCategory', {
    categoryId,
    params,
  });
  const queryParams = new URLSearchParams();
  if (params?.limit) queryParams.append('limit', params.limit.toString());
  if (params?.include_subcategories !== undefined) {
    queryParams.append(
      'include_subcategories',
      params.include_subcategories.toString()
    );
  }

  const url = `/users/categories/${categoryId}/top-products${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;
  return apiRequest<ProductData[]>(url, 'getTopProductsInCategory');
};
