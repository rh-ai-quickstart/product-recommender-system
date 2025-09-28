import { useQuery } from '@tanstack/react-query';
import {
  fetchExistingUserRecommendations,
  fetchNewUserRecommendations,
} from '../services/recommendations';
import { useAuth } from '../contexts/AuthProvider';
import { DEFAULT_RECOMMENDATIONS_COUNT } from '../constants';

/**
 * Smart recommendations hook that automatically chooses the right recommendation type
 * - For users with interaction history: uses personalized recommendations
 * - For new users without history: uses new user recommendations based on preferences
 * - Requires authentication (redirects to login if not authenticated)
 */
export const usePersonalizedRecommendations = () => {
  const { user, isAuthenticated } = useAuth();

  // Check if user has interaction history
  // For now, treat users with views/interactions as "existing", otherwise "new"
  const hasInteractionHistory = user?.views && user.views.length > 0;

  return useQuery({
    queryKey: [
      'recommendations',
      'personalized',
      user?.user_id,
      hasInteractionHistory,
    ],
    queryFn: () => {
      if (!user?.user_id) {
        throw new Error(
          'User authentication required for personalized recommendations'
        );
      }

      if (hasInteractionHistory) {
        return fetchExistingUserRecommendations(user.user_id);
      } else {
        return fetchNewUserRecommendations(user.user_id);
      }
    },
    enabled: isAuthenticated && !!user?.user_id,
  });
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
export const useNewUserRecommendations = (
  userId: string,
  numRecommendations: number = DEFAULT_RECOMMENDATIONS_COUNT
) => {
  return useQuery({
    queryKey: ['recommendations', 'new-user', userId, numRecommendations],
    queryFn: () => fetchNewUserRecommendations(userId, numRecommendations),
    enabled: !!userId,
  });
};
