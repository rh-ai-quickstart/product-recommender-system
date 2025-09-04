import { useQuery } from '@tanstack/react-query';
import { getProductReviewSummary, listProductReviews } from '../services/reviews';

export const useProductReviews = (
  productId: string,
  limit: number = 100,
  offset: number = 0
) => {
  return useQuery({
    queryKey: ['reviews', productId, limit, offset],
    queryFn: () => listProductReviews(productId, limit, offset),
    enabled: !!productId,
    staleTime: 60 * 1000,
  });
};

export const useProductReviewSummary = (productId: string) => {
  return useQuery({
    queryKey: ['reviews', productId, 'summary'],
    queryFn: () => getProductReviewSummary(productId),
    enabled: !!productId,
    staleTime: 5 * 60 * 1000,
  });
}; 
