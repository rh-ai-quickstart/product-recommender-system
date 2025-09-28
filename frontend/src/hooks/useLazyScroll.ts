import { useState, useEffect, useCallback, useRef } from 'react';
import type { ProductData } from '../types';
import { DEFAULT_BATCH_SIZE, DEFAULT_INITIAL_BATCH_SIZE } from '../constants';

interface UseLazyScrollOptions {
  initialBatchSize?: number;
  batchSize?: number;
  loadingDelay?: number;
  rootMargin?: string;
  threshold?: number;
}

interface UseLazyScrollReturn {
  displayedProducts: ProductData[];
  isLoadingMore: boolean;
  hasMoreProducts: boolean;
  loadMoreProducts: () => void;
  scrollToTop: () => void;
  loadingRef: React.RefObject<HTMLDivElement>;
  containerRef: React.RefObject<HTMLDivElement>;
  reset: () => void;
}

/**
 * Custom hook for lazy loading products with infinite scroll
 * Supports order by rank and maintains product order
 */
export const useLazyScroll = (
  products: ProductData[],
  options: UseLazyScrollOptions = {}
): UseLazyScrollReturn => {
  const {
    initialBatchSize = DEFAULT_INITIAL_BATCH_SIZE,
    batchSize = DEFAULT_BATCH_SIZE,
    loadingDelay = 300,
    rootMargin = '100px',
    threshold = 0.1,
  } = options;

  const [displayedProducts, setDisplayedProducts] = useState<ProductData[]>([]);
  const [currentIndex, setCurrentIndex] = useState(initialBatchSize);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadingRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const hasMoreProducts = currentIndex < products.length;

  // Reset displayed products when products change
  useEffect(() => {
    setDisplayedProducts(products.slice(0, initialBatchSize));
    setCurrentIndex(initialBatchSize);
  }, [products, initialBatchSize]);

  const loadMoreProducts = useCallback(() => {
    if (!hasMoreProducts || isLoadingMore) return;

    setIsLoadingMore(true);

    // Simulate loading delay for better UX
    setTimeout(() => {
      const nextBatch = products.slice(currentIndex, currentIndex + batchSize);
      setDisplayedProducts(prev => [...prev, ...nextBatch]);
      setCurrentIndex(prev => prev + batchSize);
      setIsLoadingMore(false);
    }, loadingDelay);
  }, [
    products,
    currentIndex,
    hasMoreProducts,
    isLoadingMore,
    batchSize,
    loadingDelay,
  ]);

  const scrollToTop = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const reset = useCallback(() => {
    setDisplayedProducts(products.slice(0, initialBatchSize));
    setCurrentIndex(initialBatchSize);
    setIsLoadingMore(false);
  }, [products, initialBatchSize]);

  // Set up intersection observer for infinite scroll
  useEffect(() => {
    if (!loadingRef.current || !hasMoreProducts) return;

    observerRef.current = new IntersectionObserver(
      entries => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMoreProducts && !isLoadingMore) {
          loadMoreProducts();
        }
      },
      { threshold, rootMargin }
    );

    observerRef.current.observe(loadingRef.current);

    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [hasMoreProducts, isLoadingMore, loadMoreProducts, threshold, rootMargin]);

  return {
    displayedProducts,
    isLoadingMore,
    hasMoreProducts,
    loadMoreProducts,
    scrollToTop,
    loadingRef,
    containerRef,
    reset,
  };
};
