import type {
  OnboardingProductsResponse,
  OnboardingSelectionRequest,
  OnboardingSelectionResponse,
} from '../types';
import { apiRequest, ServiceLogger } from './api';

/**
 * Fetches products for a specific onboarding round from the backend.
 * Returns 10-12 curated products: 10 from user's selected categories + 2 random products.
 *
 * @param {number} roundNumber - The round number (1-3, defaults to 1)
 * @param {string[]} excludedProductIds - Array of product IDs to exclude from results (optional)
 * @returns {Promise<OnboardingProductsResponse>} Promise resolving to products and metadata
 */
export const getOnboardingProducts = async (
  roundNumber: number = 1,
  excludedProductIds: string[] = []
): Promise<OnboardingProductsResponse> => {
  ServiceLogger.logServiceCall('getOnboardingProducts', {
    roundNumber,
    excludedProductIds,
  });

  const excludedParam =
    excludedProductIds.length > 0
      ? `&excluded_product_ids=${excludedProductIds.join(',')}`
      : '';

  return apiRequest<OnboardingProductsResponse>(
    `/users/onboarding/products?round_number=${roundNumber}${excludedParam}`,
    'getOnboardingProducts'
  );
};

/**
 * Submits user's product selections to the backend as positive interactions.
 * In our frontend-only approach, this is typically called once at the end
 * with all selections from all rounds combined.
 *
 * @param {OnboardingSelectionRequest} selections - Object containing selected product IDs and round number
 * @returns {Promise<OnboardingSelectionResponse>} Promise resolving to submission result
 */
export const submitOnboardingSelections = async (
  selections: OnboardingSelectionRequest
): Promise<OnboardingSelectionResponse> => {
  ServiceLogger.logServiceCall('submitOnboardingSelections', { selections });
  return apiRequest<OnboardingSelectionResponse>(
    '/users/onboarding/selections',
    'submitOnboardingSelections',
    {
      method: 'POST',
      body: selections,
    }
  );
};
