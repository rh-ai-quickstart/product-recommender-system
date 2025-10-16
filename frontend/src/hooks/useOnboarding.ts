import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getOnboardingProducts,
  submitOnboardingSelections,
} from '../services/onboarding';
import type {
  OnboardingProductsResponse,
  OnboardingSelectionRequest,
  OnboardingSelectionResponse,
} from '../types';

/**
 * Hook to fetch products for a specific onboarding round.
 * Returns 10-12 products: 10 from user's selected categories + 2 random products.
 *
 * @param {number} roundNumber - The round number (1-3) to fetch products for
 * @param {boolean} enabled - Whether the query should be enabled (default: true)
 * @returns {UseQueryResult<OnboardingProductsResponse>} Query result with products data
 */
export const useOnboardingProducts = (
  roundNumber: number,
  enabled: boolean = true
) => {
  return useQuery<OnboardingProductsResponse>({
    queryKey: ['onboardingProducts', roundNumber],
    queryFn: () => getOnboardingProducts(roundNumber),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: enabled && roundNumber > 0 && roundNumber <= 3, // Only fetch for valid rounds when enabled
  });
};

/**
 * Hook to submit product selections to the backend.
 * In our frontend-only approach, this is typically only called once at the end
 * to submit all selections from all rounds as a batch.
 *
 * @returns {UseMutationResult} Mutation for submitting onboarding selections
 */
export const useSubmitOnboardingSelections = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (selections: OnboardingSelectionRequest) =>
      submitOnboardingSelections(selections),
    onSuccess: (response: OnboardingSelectionResponse) => {
      // If onboarding is complete, invalidate recommendations to refresh with new preferences
      if (response.is_complete) {
        queryClient.invalidateQueries({
          queryKey: ['recommendations'],
        });
      }
    },
  });
};
