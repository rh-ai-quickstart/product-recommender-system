// Composite hooks that combine multiple operations for better DX
import { useAuth } from '../contexts/AuthProvider';
import { useProduct, useProductSearchByText } from './useProducts';
import { usePersonalizedRecommendations } from './useRecommendations';
import type { ProductData } from '../types';
import { useCart, useAddToCart } from './useCart';
import { useRecordProductClick } from './useInteractions';
import { useCallback } from 'react';
import { DEFAULT_SEARCH_RESULTS_COUNT } from '../constants';
/**
 * Hook that provides all product-related actions for a specific product
 * Combines product data, cart operations, and interaction tracking
 * Requires an authenticated user for cart operations
 */
export const useProductActions = (productId: string) => {
  const { user } = useAuth();
  const userId = user?.user_id || '';

  // Data hooks
  const productQuery = useProduct(productId);
  const cartQuery = useCart(userId);

  // Mutation hooks
  const addToCartMutation = useAddToCart();
  const recordClickMutation = useRecordProductClick();

  // Derived state
  const isInCart =
    cartQuery.data?.some(item => item.product_id === productId) ?? false;

  // Composite actions - memoized to prevent infinite loops
  const addToCart = useCallback(
    (quantity: number = 1) => {
      if (!userId) throw new Error('User must be authenticated to add to cart');

      return addToCartMutation.mutate({
        user_id: userId,
        product_id: productId,
        quantity,
      });
    },
    [userId, productId, addToCartMutation]
  );

  const recordClick = useCallback(() => {
    recordClickMutation.mutate(productId);
  }, [productId, recordClickMutation]);

  return {
    // Data
    product: productQuery.data,
    isLoading: productQuery.isLoading,
    error: productQuery.error,

    // State
    isInCart,

    // Actions
    addToCart,
    recordClick,

    // Loading states
    isAddingToCart: addToCartMutation.isPending,

    // Raw mutations for advanced use
    mutations: {
      addToCart: addToCartMutation,
      recordClick: recordClickMutation,
    },
  };
};

/**
 * Lightweight hook for product cards in lists (homepage, search results, catalog)
 * Provides cart actions without fetching product data (assumes you already have it)
 * Optimized for use in multiple product cards simultaneously
 */
export const useProductCardActions = (productId: string) => {
  const { user } = useAuth();
  const userId = user?.user_id || '';

  // Only fetch user's cart data (shared across all cards)
  const cartQuery = useCart(userId);

  // Mutation hooks (can be used by multiple cards simultaneously)
  const addToCartMutation = useAddToCart();
  const recordClickMutation = useRecordProductClick();

  // Derived state for this specific product
  const isInCart =
    cartQuery.data?.some(item => item.product_id === productId) ?? false;

  // Lightweight actions (no product data fetching)
  const addToCart = (quantity: number = 1) => {
    if (!userId) throw new Error('User must be authenticated to add to cart');

    return addToCartMutation.mutate({
      user_id: userId,
      product_id: productId,
      quantity,
    });
  };

  const recordClick = () => {
    recordClickMutation.mutate(productId);
  };

  return {
    // State (no product data - you already have it from the list)
    isInCart,
    isAuthenticated: !!userId,

    // Actions
    addToCart,
    recordClick,

    // Loading states
    isAddingToCart: addToCartMutation.isPending,

    // User-specific loading states (useful for showing which card is being acted upon)
    isCartLoading: cartQuery.isLoading,
  };
};

// ============================
// LIST-LEVEL HOOKS WITH ACTIONS
// ============================

/**
 * Hook for recommendations with built-in cart actions
 * Perfect for homepage - gets recommendations AND provides actions for each product
 */
export const useRecommendationsWithActions = () => {
  const { user } = useAuth();
  const userId = user?.user_id || '';

  // Get personalized recommendations
  const recommendationsQuery = usePersonalizedRecommendations();

  // Get user's cart data once for the entire list
  const cartQuery = useCart(userId);

  // Shared mutation hooks
  const addToCartMutation = useAddToCart();
  const recordClickMutation = useRecordProductClick();

  // Factory function to create actions for any product in the list
  const createProductActions = (productId: string) => {
    const isInCart =
      cartQuery.data?.some(item => item.product_id === productId) ?? false;

    return {
      isInCart,
      isAuthenticated: !!userId,
      addToCart: (quantity: number = 1) => {
        if (!userId)
          throw new Error('User must be authenticated to add to cart');
        return addToCartMutation.mutate({
          user_id: userId,
          product_id: productId,
          quantity,
        });
      },
      recordClick: () => recordClickMutation.mutate(productId),
      isAddingToCart: addToCartMutation.isPending,
    };
  };

  return {
    // List data
    products: recommendationsQuery.data || [],
    isLoading: recommendationsQuery.isLoading,
    error: recommendationsQuery.error,

    // Action factory
    createProductActions,

    // Convenience: products with actions pre-attached
    productsWithActions:
      recommendationsQuery.data?.map((product: ProductData) => ({
        ...product,
        actions: createProductActions(product.item_id.toString()),
      })) || [],

    // Global loading states
    isCartLoading: cartQuery.isLoading,
  };
};

/**
 * Hook for search results with built-in cart actions
 * Perfect for search pages - gets search results AND provides actions for each product
 */
export const useSearchWithActions = (
  query: string,
  enabled: boolean = true
) => {
  const { user } = useAuth();
  const userId = user?.user_id || '';

  // Get the search results
  const searchQuery = useProductSearchByText(
    query,
    DEFAULT_SEARCH_RESULTS_COUNT,
    enabled
  );

  // Get user's cart data once for the entire list
  const cartQuery = useCart(userId);

  // Shared mutation hooks
  const addToCartMutation = useAddToCart();
  const recordClickMutation = useRecordProductClick();

  // Factory function to create actions for any product in the list
  const createProductActions = (productId: string) => {
    const isInCart =
      cartQuery.data?.some(item => item.product_id === productId) ?? false;

    return {
      isInCart,
      isAuthenticated: !!userId,
      addToCart: (quantity: number = 1) => {
        if (!userId)
          throw new Error('User must be authenticated to add to cart');
        return addToCartMutation.mutate({
          user_id: userId,
          product_id: productId,
          quantity,
        });
      },
      recordClick: () => recordClickMutation.mutate(productId),
      isAddingToCart: addToCartMutation.isPending,
    };
  };

  return {
    // List data
    products: searchQuery.data || [],
    isLoading: searchQuery.isLoading,
    error: searchQuery.error,

    // Action factory
    createProductActions,

    // Convenience: products with actions pre-attached
    productsWithActions:
      searchQuery.data?.map((product: ProductData) => ({
        ...product,
        actions: createProductActions(product.item_id.toString()),
      })) || [],

    // Global loading states
    isCartLoading: cartQuery.isLoading,
  };
};
