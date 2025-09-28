import { useQuery } from '@tanstack/react-query';
import {
  fetchProduct,
  searchProductsByText,
  searchProductsByImageLink,
  searchProductsByImage,
} from '../services/products';
import { DEFAULT_SEARCH_RESULTS_COUNT } from '../constants';

export const useProduct = (productId: string) => {
  return useQuery({
    queryKey: ['products', productId],
    queryFn: () => fetchProduct(productId),
    enabled: !!productId,
    staleTime: 10 * 60 * 1000, // Override: product details change less frequently
  });
};

export const useProductSearchByText = (
  query: string,
  k: number = DEFAULT_SEARCH_RESULTS_COUNT,
  enabled: boolean = true
) => {
  return useQuery({
    queryKey: ['products', 'search', query, k],
    queryFn: () => searchProductsByText(query, k),
    enabled: enabled && !!query && query.trim().length > 0,
    staleTime: 2 * 60 * 1000,
  });
};

export const useProductSearchByImageLink = (
  imageLink: string,
  k: number = 10,
  enabled: boolean = true
) => {
  return useQuery({
    queryKey: ['products', 'search', 'image-link', imageLink, k],
    queryFn: () => searchProductsByImageLink(imageLink, k),
    enabled: enabled && !!imageLink && imageLink.trim().length > 0,
    staleTime: 2 * 60 * 1000,
  });
};

export const useProductSearchByImage = (
  imageFile: File | null,
  k: number = 10,
  enabled: boolean = true
) => {
  return useQuery({
    queryKey: [
      'products',
      'search',
      'image-file',
      imageFile?.name,
      imageFile?.size,
      k,
    ],
    queryFn: () => searchProductsByImage(imageFile!, k),
    enabled: enabled && !!imageFile,
    staleTime: 2 * 60 * 1000,
  });
};
