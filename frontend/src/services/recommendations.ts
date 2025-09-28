import type { ProductData } from '../types';
import { apiRequest, ServiceLogger } from './api';
import { DEFAULT_RECOMMENDATIONS_COUNT } from '../constants';

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

/**
 * Create new user recommendations via ML model (POST endpoint)
 * This triggers the backend to generate initial recommendations for new users
 */
export const createNewUserRecommendations = async (
  numRecommendations: number = 10
): Promise<ProductData[]> => {
  ServiceLogger.logServiceCall('createNewUserRecommendations', {
    numRecommendations,
  });

  return apiRequest<ProductData[]>(
    '/recommendations',
    'createNewUserRecommendations',
    {
      method: 'POST',
      body: { num_recommendations: numRecommendations },
    }
  );
};

/**
 * Fetch recommendations for new users without interaction history (cold start problem)
 * Uses the POST endpoint which generates ML-powered recommendations based on user preferences
 */
export const fetchNewUserRecommendations = async (
  userId: string,
  numRecommendations: number = DEFAULT_RECOMMENDATIONS_COUNT
): Promise<ProductData[]> => {
  ServiceLogger.logServiceCall('fetchNewUserRecommendations', {
    userId,
    numRecommendations,
  });

  try {
    // Use the POST endpoint which generates new user recommendations via ML model
    return await apiRequest<ProductData[]>(
      '/recommendations',
      'fetchNewUserRecommendations',
      {
        method: 'POST',
        body: { num_recommendations: numRecommendations },
      }
    );
  } catch (error) {
    // If backend fails, return mock data as fallback
    console.warn('Recommendations failed, using fallback data:', error);
    return [
      {
        item_id: '1',
        product_name: 'Sample Product 1',
        actual_price: 29.99,
        rating: 4.5,
        category: 'Sample Category',
        about_product:
          'This is a sample product while we set up your personalized recommendations.',
        img_link: 'https://via.placeholder.com/300x300?text=Product+1',
      },
      {
        item_id: '2',
        product_name: 'Sample Product 2',
        actual_price: 49.99,
        rating: 4.0,
        category: 'Sample Category',
        about_product: 'Another sample product for testing purposes.',
        img_link:
          'https://repo-avatars.githubusercontent.com/300x300?text=Product+2',
      },
    ];
  }
};
