import {
  Gallery,
  GalleryItem,
  Flex,
  FlexItem,
  Button,
  Alert,
  Progress,
  ProgressSize,
  ProgressMeasureLocation,
} from '@patternfly/react-core';
import { SelectableProductCard } from './selectable-product-card';
import type { ProductData } from '../types';

interface SelectableProductGalleryProps {
  products: ProductData[];
  selectedProducts: Set<string>;
  onSelectionChange: (productId: string, selected: boolean) => void;
  totalSelected: number;
  targetSelections: number;
  onSelectAll?: () => void;
  onClearAll?: () => void;
  showBatchActions?: boolean;
}

export const SelectableProductGallery: React.FC<
  SelectableProductGalleryProps
> = ({
  products,
  selectedProducts,
  onSelectionChange,
  totalSelected,
  targetSelections,
  onSelectAll,
  onClearAll,
  showBatchActions = true,
}) => {
  const progressPercentage = Math.min(
    (totalSelected / targetSelections) * 100,
    100
  );
  const isTargetReached = totalSelected >= targetSelections;

  return (
    <div style={{ width: '100%' }}>
      {/* Progress indicator */}
      <div style={{ marginBottom: 24 }}>
        <Flex
          direction={{ default: 'column' }}
          spaceItems={{ default: 'spaceItemsSm' }}
        >
          <FlexItem>
            <Flex
              justifyContent={{ default: 'justifyContentSpaceBetween' }}
              alignItems={{ default: 'alignItemsCenter' }}
            >
              <FlexItem>
                <h3 style={{ margin: 0, fontSize: '1.2rem' }}>
                  Select at least 10 products you like
                </h3>
              </FlexItem>
              <FlexItem>
                <div
                  style={{
                    fontSize: '1rem',
                    fontWeight: 'bold',
                    color: isTargetReached ? '#27ae60' : '#333',
                  }}
                >
                  {totalSelected} / {targetSelections} selected
                </div>
              </FlexItem>
            </Flex>
          </FlexItem>

          <FlexItem>
            <Progress
              value={progressPercentage}
              title='Overall Progress'
              size={ProgressSize.lg}
              measureLocation={ProgressMeasureLocation.outside}
              variant={isTargetReached ? 'success' : undefined}
            />
          </FlexItem>

          {!isTargetReached && (
            <FlexItem>
              <Alert
                variant='info'
                title={`Select at least ${targetSelections - totalSelected} more products to continue`}
                isInline
              />
            </FlexItem>
          )}

          {isTargetReached && (
            <FlexItem>
              <Alert
                variant='success'
                title="Great! You've selected enough products to complete onboarding."
                isInline
              />
            </FlexItem>
          )}
        </Flex>
      </div>

      {/* Batch action buttons */}
      {showBatchActions && products.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Flex spaceItems={{ default: 'spaceItemsSm' }}>
            {onSelectAll && (
              <FlexItem>
                <Button
                  variant='secondary'
                  size='sm'
                  onClick={onSelectAll}
                  isDisabled={products.every(p =>
                    selectedProducts.has(p.item_id)
                  )}
                >
                  Select All Visible
                </Button>
              </FlexItem>
            )}
            {onClearAll && selectedProducts.size > 0 && (
              <FlexItem>
                <Button variant='link' size='sm' onClick={onClearAll}>
                  Clear All Selections
                </Button>
              </FlexItem>
            )}
          </Flex>
        </div>
      )}

      {/* Product gallery */}
      <div className='gallery-container'>
        <Gallery hasGutter>
          {products.map((product, index) => (
            <GalleryItem key={product.item_id}>
              <SelectableProductCard
                product={product}
                index={index}
                isSelected={selectedProducts.has(product.item_id)}
                onSelectionChange={onSelectionChange}
              />
            </GalleryItem>
          ))}
        </Gallery>
      </div>

      {products.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: '#666' }}>
          <p>No products available for selection.</p>
        </div>
      )}
    </div>
  );
};
