import {
  Button,
  Card,
  CardBody,
  CardFooter,
  CardTitle,
  Flex,
  FlexItem,
  Skeleton,
} from '@patternfly/react-core';
import StarRatings from 'react-star-ratings';
import { useEffect } from 'react';
import { useProductActions } from '../hooks';
import { Route } from '../routes/_protected/product/$productId';
import { useProductReviews, useProductReviewSummary } from '../hooks/useReviews';

export const ProductDetails = () => {
  // loads productId from route /product/$productId
  const { productId } = Route.useLoaderData();

  // Use our composite hook for all product actions
  const { product, error, isLoading, addToCart, isAddingToCart, recordClick } =
    useProductActions(productId);

  // Reviews data
  const reviewsQuery = useProductReviews(productId);
  const summaryQuery = useProductReviewSummary(productId);

  // Record that user viewed this product when component mounts or productId changes
  useEffect(() => {
    if (product && !isLoading) {
      recordClick();
    }
  }, [product, isLoading, productId]); // Removed recordClick from deps to prevent infinite loop

  if (error || !product) {
    return <div>Error fetching product</div>;
  }

  return (
    <>
      {isLoading ? (
        <Skeleton style={{ flex: 1, minWidth: 0, height: '100%' }} />
      ) : (
        <>
          <FlexItem style={{ flex: 1, minWidth: 0, height: '100%' }}>
            <Card style={{ height: '100%' }}>
              <CardBody style={{ height: '100%', padding: 0 }}>
                <img
                  src={product.img_link}
                  alt={product.product_name}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    display: 'block',
                  }}
                />
              </CardBody>
            </Card>
          </FlexItem>
          <FlexItem style={{ flex: 1, minWidth: 0, height: '100%' }}>
            <Card isPlain style={{ height: '100%' }}>
              <CardTitle style={{ fontSize: '2rem', fontWeight: 'bold' }}>
                {product.product_name}
              </CardTitle>
              <CardBody>
                <Flex direction={{ default: 'column' }}>
                  <FlexItem>
                    <StarRatings
                      rating={product.rating}
                      starRatedColor='black'
                      numberOfStars={5}
                      name='rating'
                      starDimension='18px'
                      starSpacing='1px'
                    />{' '}
                    {product.rating}
                  </FlexItem>
                  <FlexItem headers='h1'>${product.actual_price}</FlexItem>
                  <FlexItem>{product.about_product}</FlexItem>
                  <FlexItem>
                    <h3 style={{ marginTop: '1rem' }}>Reviews</h3>
                    {summaryQuery.isLoading ? (
                      <Skeleton width="200px" />
                    ) : (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <strong>{summaryQuery.data?.count || 0}</strong> reviews
                        {summaryQuery.data && (
                          <>
                            {' '}• Average:{' '}
                            <StarRatings
                              rating={summaryQuery.data.avg_rating || 0}
                              starRatedColor='black'
                              numberOfStars={5}
                              name='avg'
                              starDimension='14px'
                              starSpacing='1px'
                            />
                            {' '}
                            {summaryQuery.data.avg_rating?.toFixed(1)}
                          </>
                        )}
                      </div>
                    )}
                    {reviewsQuery.isLoading ? (
                      <Skeleton height="180px" />
                    ) : reviewsQuery.data && reviewsQuery.data.length > 0 ? (
                      <div>
                        {reviewsQuery.data.map(r => (
                          <div key={r.id} style={{ marginBottom: '0.75rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <StarRatings
                                rating={r.rating}
                                starRatedColor='black'
                                numberOfStars={5}
                                name={`r-${r.id}`}
                                starDimension='14px'
                                starSpacing='1px'
                              />
                              <span style={{ marginLeft: '0.5rem', fontWeight: 600 }}>
                                {r.title || 'Review'}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.9rem', color: '#444' }}>{r.comment}</div>
                            <div style={{ fontSize: '0.75rem', color: '#777' }}>
                              {new Date(r.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div>No reviews yet.</div>
                    )}
                  </FlexItem>
                </Flex>
              </CardBody>
              <CardFooter>
                <Flex>
                  <FlexItem>
                    <Button
                      variant='secondary'
                      onClick={() => addToCart(1)}
                      isLoading={isAddingToCart}
                      isDisabled={isAddingToCart}
                    >
                      {isAddingToCart ? 'Adding...' : 'Add to Cart'}
                    </Button>
                  </FlexItem>
                </Flex>
              </CardFooter>
            </Card>
          </FlexItem>
        </>
      )}
    </>
  );
};
