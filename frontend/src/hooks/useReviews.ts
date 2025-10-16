import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getProductReviewSummary,
  listProductReviews,
  summarizeProductReviews,
  createProductReview,
  type CreateReviewRequest,
} from '../services/reviews';

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

export const useProductReviewSummarization = (
  productId: string,
  enabled: boolean = false
) => {
  return useQuery({
    queryKey: ['reviews', productId, 'summarization'],
    queryFn: () => summarizeProductReviews(productId),
    enabled: !!productId && enabled,
    staleTime: 10 * 60 * 1000,
  });
};

export const useCreateProductReview = (productId: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateReviewRequest) =>
      createProductReview(productId, payload),
    onSuccess: () => {
      // Refresh reviews and summary after posting
      qc.invalidateQueries({ queryKey: ['reviews', productId] });
      qc.invalidateQueries({ queryKey: ['reviews', productId, 'summary'] });
    },
  });
};
