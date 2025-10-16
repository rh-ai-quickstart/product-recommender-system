import { useQuery } from '@tanstack/react-query';
import {
  fetchExistingUserRecommendations,
  getTopProductsInCategory,
} from '../services/recommendations';
import { useAuth } from '../contexts/AuthProvider';
import type { ProductData } from '../types';
import { DEFAULT_RECOMMENDATIONS_COUNT } from '../constants';

/**
 * Smart recommendations hook that automatically chooses the right recommendation type
 * - Existing users: Those with available ML recommendations (uses personalized recommendations)
 * - New users: Those without ML recommendations (uses category-based recommendations)
 * - Requires authentication (redirects to login if not authenticated)
 */
export const usePersonalizedRecommendations = () => {
  const { user, isAuthenticated } = useAuth();

  // For users without ML recommendations, use category-based recommendations
  const newUserRecommendations = useNewUserRecommendations(
    user?.user_id || '',
    10
  );

  // Try to fetch ML-based recommendations for users with interactions
  const existingUserRecommendations = useQuery({
    queryKey: ['recommendations', 'existing-user', user?.user_id],
    queryFn: () => {
      if (!user?.user_id) {
        throw new Error(
          'User authentication required for personalized recommendations'
        );
      }
      return fetchExistingUserRecommendations(user.user_id);
    },
    enabled: isAuthenticated && !!user?.user_id,
    retry: 1, // Only retry once to avoid long loading times
  });

  // Define "existing user" as someone with successful ML recommendations
  const hasMLRecommendations =
    existingUserRecommendations.isSuccess &&
    existingUserRecommendations.data &&
    existingUserRecommendations.data.length > 0;

  // Return appropriate recommendation set based on ML recommendation availability
  if (!isAuthenticated || !user?.user_id) {
    return {
      data: undefined,
      isLoading: false,
      error: new Error('User authentication required'),
      isError: true,
    };
  }

  // Simple binary choice based on ML recommendation availability:
  // - If ML recommendations exist and have data → Existing user (use ML)
  // - Otherwise → New user (use category-based)
  if (hasMLRecommendations) {
    return existingUserRecommendations;
  } else {
    return newUserRecommendations;
  }
};

// Recommendations for users with existing interaction history
export const useExistingUserRecommendations = (userId: string) => {
  return useQuery({
    queryKey: ['recommendations', 'existing-user', userId],
    queryFn: () => fetchExistingUserRecommendations(userId),
    enabled: !!userId,
  });
};

// Recommendations for users without interaction history (cold start)
// Uses top products from user's preferred categories
export const useNewUserRecommendations = (
  userId: string,
  numRecommendations: number = DEFAULT_RECOMMENDATIONS_COUNT
) => {
  const { user } = useAuth();

  return useQuery({
    queryKey: [
      'recommendations',
      'new-user',
      userId,
      numRecommendations,
      user?.user_preferences
        ?.map(p => p.category_id)
        .sort()
        .join(','), // Convert to string
    ],
    queryFn: async () => {
      if (!user?.user_preferences || user.user_preferences.length === 0) {
        console.warn('No user preferences found for recommendations');
        return [];
      }

      try {
        // Get ALL products from each preferred category in parallel (no limit)
        const categoryPromises = user.user_preferences.map(async category => {
          try {
            return await getTopProductsInCategory(category.category_id, {
              limit: 100, // Backend maximum limit (ge=1, le=100)
              include_subcategories: true,
            });
          } catch (error) {
            console.warn(
              `Failed to load products for category ${category.name}:`,
              error
            );
            return []; // Return empty array for failed categories
          }
        });

        const categoryResults = await Promise.all(categoryPromises);

        // Flatten results from all categories while preserving interaction order
        const allProducts = categoryResults.flat();

        // Skip if no products found across all categories
        if (allProducts.length === 0) {
          console.warn('No products found in any preferred categories');
          return [];
        }

        // Create a weighted list that preserves backend interaction ordering
        // Backend returns products ordered by: interaction_count DESC, avg_rating DESC
        const weightedProducts: Array<{
          product: ProductData;
          weight: number;
        }> = [];

        categoryResults.forEach((products, categoryIndex) => {
          products.forEach((product, productIndex) => {
            // Calculate weight: higher for earlier positions (better interaction count)
            // Category weight ensures products from first category get slight priority
            const positionWeight = products.length - productIndex;
            const categoryWeight =
              (categoryResults.length - categoryIndex) * 0.1;
            const weight = positionWeight + categoryWeight;

            weightedProducts.push({ product, weight });
          });
        });

        // Remove duplicates while preserving the highest weighted occurrence
        const seenProducts = new Map<
          string,
          { product: ProductData; weight: number }
        >();
        weightedProducts.forEach(({ product, weight }) => {
          const existing = seenProducts.get(product.item_id);
          if (!existing || weight > existing.weight) {
            seenProducts.set(product.item_id, { product, weight });
          }
        });

        // Sort by weight (highest interaction priority first) and return products
        const sortedProducts = Array.from(seenProducts.values())
          .sort((a, b) => b.weight - a.weight)
          .map(({ product }) => product);

        return sortedProducts;
      } catch (error) {
        console.error('Error loading category-based recommendations:', error);
        return [];
      }
    },
    enabled: !!userId && !!user?.user_preferences,
  });
};
