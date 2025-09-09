import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setPreferences, getCategories } from '../services/preferences';
import type { PreferencesRequest, CategoryTree } from '../types';
import { useNavigate } from '@tanstack/react-router';

export const useCategoryTree = () => {
  return useQuery<CategoryTree[]>({
    queryKey: ['categoryTree'],
    queryFn: async () => {
      const result = await getCategories();
      console.log('Category tree:', result);
      return result; // Return full CategoryTree objects
    },
    staleTime: 10 * 60 * 1000,
  });
};

export const useSetPreferences = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (preferences: PreferencesRequest) =>
      setPreferences(preferences),
    onSuccess: async authResponse => {
      // Update user data in cache with new preferences
      queryClient.setQueryData(['currentUser'], authResponse.user);

      // Invalidate recommendations cache to force refresh with new category-based recommendations
      queryClient.invalidateQueries({
        queryKey: ['recommendations'],
      });

      // Get redirect path from URL params or default to home
      const searchParams = new URLSearchParams(window.location.search);
      const redirectPath = searchParams.get('redirect') || '/';
      navigate({ to: redirectPath });
    },
  });
};

// Re-export the type for convenience
export type { PreferencesRequest };
