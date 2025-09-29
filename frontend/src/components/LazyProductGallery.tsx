import React from 'react';
import { Spinner, Button, ButtonVariant } from '@patternfly/react-core';
import { ArrowUpIcon } from '@patternfly/react-icons';
import { GalleryView } from './Gallery';
import { useLazyScroll } from '../hooks/useLazyScroll';
import type { ProductData } from '../types';
import { DEFAULT_BATCH_SIZE, DEFAULT_INITIAL_BATCH_SIZE } from '../constants';

interface LazyProductGalleryProps {
  products: ProductData[];
  title?: string;
  showProductCount?: boolean;
  showScrollToTop?: boolean;
  initialBatchSize?: number;
  batchSize?: number;
  loadingDelay?: number;
  className?: string;
}

/**
 * Reusable component for displaying products with lazy scroll
 * Supports order by rank and maintains product order
 */
export const LazyProductGallery: React.FC<LazyProductGalleryProps> = ({
  products,
  title,
  showProductCount = true,
  showScrollToTop = true,
  initialBatchSize = DEFAULT_INITIAL_BATCH_SIZE,
  batchSize = DEFAULT_BATCH_SIZE,
  loadingDelay = 300,
  className,
}) => {
  const {
    displayedProducts,
    isLoadingMore,
    hasMoreProducts,
    scrollToTop,
    loadingRef,
    containerRef,
    showScrollToTop: hookShowScrollToTop,
  } = useLazyScroll(products, {
    initialBatchSize,
    batchSize,
    loadingDelay,
  });

  return (
    <div className={className}>
      {title && (
        <div ref={containerRef}>
          <h2
            style={{
              textAlign: 'center',
              marginBottom: '24px',
              color: '#2c3e50',
              fontWeight: '600',
            }}
          >
            {title}
          </h2>
          {showProductCount && (
            <div
              style={{
                marginBottom: '16px',
                textAlign: 'center',
                color: '#666',
              }}
            >
              Showing {displayedProducts.length} of {products.length} products
            </div>
          )}
        </div>
      )}

      <GalleryView products={displayedProducts} />

      {/* Loading indicator for infinite scroll */}
      {hasMoreProducts && (
        <div
          ref={loadingRef}
          style={{
            textAlign: 'center',
            marginTop: '32px',
            marginBottom: '32px',
            padding: '20px',
          }}
        >
          {isLoadingMore && (
            <div>
              <Spinner size='md' />
              <div style={{ marginTop: '8px', color: '#666' }}>
                Loading more products...
              </div>
            </div>
          )}
        </div>
      )}

      {!hasMoreProducts && products.length > 0 && (
        <div
          style={{
            textAlign: 'center',
            marginTop: '32px',
            color: '#666',
            fontStyle: 'italic',
          }}
        >
          All {products.length} products have been loaded
        </div>
      )}

      {/* Return to Top Button */}
      {(showScrollToTop || hookShowScrollToTop) && (
        <Button
          variant={ButtonVariant.primary}
          onClick={scrollToTop}
          icon={<ArrowUpIcon />}
          style={{
            position: 'fixed',
            bottom: '30px',
            right: '30px',
            zIndex: 9999,
            borderRadius: '50%',
            width: '60px',
            height: '60px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            background: 'linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)',
            border: 'none',
            color: 'white',
            fontSize: '12px',
            fontWeight: 'bold',
          }}
        >
          Top
        </Button>
      )}
    </div>
  );
};
