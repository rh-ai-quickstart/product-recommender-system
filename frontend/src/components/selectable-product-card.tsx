import {
  Card,
  CardTitle,
  CardBody,
  CardHeader,
  Divider,
  Flex,
  FlexItem,
  Checkbox,
} from '@patternfly/react-core';
import { StarIcon } from '@patternfly/react-icons';
import type { ProductData } from '../types';

type SelectableProductCardProps = {
  product: ProductData;
  index: number;
  isSelected: boolean;
  onSelectionChange: (productId: string, selected: boolean) => void;
};

export const SelectableProductCard: React.FC<SelectableProductCardProps> = ({
  product,
  index,
  isSelected,
  onSelectionChange,
}) => {
  const curCardCount = index + 1;
  const cardId = `selectable-product-${curCardCount}`;
  const cardTitleId = `selectable-product-${curCardCount}-title`;

  const price = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(product.actual_price);

  const rating = new Intl.NumberFormat('en-US', {
    minimumIntegerDigits: 1,
    minimumFractionDigits: 2,
  }).format(product.rating ?? 0);

  const handleSelectionChange = (checked: boolean) => {
    onSelectionChange(product.item_id, checked);
  };

  return (
    <Card
      id={cardId}
      component='div'
      isClickable
      isSelected={isSelected}
      key={index}
      style={{
        height: 420,
        overflowY: 'auto',
        border: isSelected ? '2px solid #0066cc' : '1px solid #d2d2d2',
        backgroundColor: isSelected ? '#f0f8ff' : 'white',
        position: 'relative',
      }}
      onClick={() => handleSelectionChange(!isSelected)}
    >
      {/* Selection checkbox overlay */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          borderRadius: '4px',
          padding: '4px',
        }}
        onClick={e => e.stopPropagation()}
      >
        <Checkbox
          id={`checkbox-${product.item_id}`}
          isChecked={isSelected}
          onChange={(_event, checked) => handleSelectionChange(checked)}
          aria-label={`Select ${product.product_name}`}
        />
      </div>

      <CardHeader
        className='v6-featured-posts-card-header-img'
        style={{
          minHeight: 200,
          backgroundImage: product.img_link
            ? `url(${product.img_link})`
            : 'none',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundColor: product.img_link ? 'transparent' : '#f5f5f5',
        }}
      >
        {!product.img_link && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: '#666',
              fontSize: '14px',
            }}
          >
            No Image Available
          </div>
        )}
      </CardHeader>

      <CardTitle
        id={cardTitleId}
        style={{ fontSize: '1rem', lineHeight: '1.2' }}
      >
        {product.product_name}
      </CardTitle>

      <CardBody style={{ paddingTop: 8, paddingBottom: 8 }}>
        <Flex
          direction={{ default: 'column' }}
          spaceItems={{ default: 'spaceItemsXs' }}
        >
          <FlexItem>
            <div style={{ fontSize: '0.875rem', color: '#666' }}>
              {product.category}
            </div>
          </FlexItem>

          {product.about_product && (
            <FlexItem>
              <div
                style={{
                  fontSize: '0.875rem',
                  color: '#333',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                  lineHeight: '1.3',
                }}
              >
                {product.about_product}
              </div>
            </FlexItem>
          )}

          <Divider style={{ margin: '8px 0' }} />

          <FlexItem>
            <Flex
              justifyContent={{ default: 'justifyContentSpaceBetween' }}
              alignItems={{ default: 'alignItemsCenter' }}
            >
              <FlexItem>
                <div
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: 'bold',
                    color: '#333',
                  }}
                >
                  {price}
                </div>
                {product.discount_percentage &&
                  product.discount_percentage > 0 && (
                    <div style={{ fontSize: '0.75rem', color: '#e74c3c' }}>
                      {product.discount_percentage.toFixed(0)}% off
                    </div>
                  )}
              </FlexItem>

              {product.rating && product.rating > 0 && (
                <FlexItem>
                  <Flex
                    alignItems={{ default: 'alignItemsCenter' }}
                    spaceItems={{ default: 'spaceItemsXs' }}
                  >
                    <FlexItem>
                      <StarIcon
                        style={{ color: '#f39c12', fontSize: '0.875rem' }}
                      />
                    </FlexItem>
                    <FlexItem>
                      <span style={{ fontSize: '0.875rem', color: '#666' }}>
                        {rating}
                      </span>
                    </FlexItem>
                    {product.rating_count && (
                      <FlexItem>
                        <span style={{ fontSize: '0.75rem', color: '#999' }}>
                          ({product.rating_count})
                        </span>
                      </FlexItem>
                    )}
                  </Flex>
                </FlexItem>
              )}
            </Flex>
          </FlexItem>
        </Flex>
      </CardBody>
    </Card>
  );
};
