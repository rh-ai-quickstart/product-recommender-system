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
import { useEffect, useState } from 'react';
import { useProductActions } from '../hooks';
import { Route } from '../routes/_protected/product/$productId';
import {
  useProductReviews,
  useProductReviewSummary,
  useCreateProductReview,
} from '../hooks/useReviews';
import { ReviewSummarizationModal } from './ReviewSummarizationModal';
import { useAuth } from '../contexts/AuthProvider';

const AddReviewInline = ({
  onSubmit,
  isSubmitting,
}: {
  onSubmit: (rating: number, title?: string, comment?: string) => Promise<void>;
  isSubmitting?: boolean;
}) => {
  const [rating, setRating] = useState(5);
  const [title, setTitle] = useState('');
  const [comment, setComment] = useState('');
  const [show, setShow] = useState(false);

  if (!show) {
    return (
      <Button variant='primary' size='sm' onClick={() => setShow(true)}>
        Add Review
      </Button>
    );
  }

  return (
    <div
      style={{
        border: '1px solid #e0e0e0',
        borderRadius: 6,
        padding: '0.5rem',
        maxWidth: 420,
        background: '#fafafa',
        flex: '0 0 auto',
      }}
    >
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={{ fontWeight: 600, fontSize: 12 }}>Rating</label>
        <div>
          <StarRatings
            rating={rating}
            starRatedColor='#f5a623'
            changeRating={(r: number) => setRating(r)}
            numberOfStars={5}
            name='new-rating'
            starDimension='18px'
            starSpacing='2px'
          />
        </div>
      </div>
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={{ fontWeight: 600, fontSize: 12 }}>
          Title (optional)
        </label>
        <input
          type='text'
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder='Short headline'
          style={{ width: '100%', padding: '6px 8px' }}
        />
      </div>
      <div style={{ marginBottom: '0.5rem' }}>
        <label style={{ fontWeight: 600, fontSize: 12 }}>Comment</label>
        <textarea
          value={comment}
          onChange={e => setComment(e.target.value)}
          placeholder='Share your experience'
          rows={3}
          style={{ width: '100%', padding: '6px 8px' }}
        />
      </div>
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <Button
          variant='primary'
          size='sm'
          isDisabled={isSubmitting || comment.trim().length === 0}
          isLoading={isSubmitting}
          onClick={async () => {
            await onSubmit(rating, title.trim() || undefined, comment.trim());
            setTitle('');
            setComment('');
            setRating(5);
            setShow(false);
          }}
        >
          Submit
        </Button>
        <Button variant='link' size='sm' onClick={() => setShow(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
};

export const ProductDetails = () => {
  // loads productId from route /product/$productId
  const { productId } = Route.useLoaderData();

  // Get current user information
  const { user } = useAuth();

  // Use our composite hook for all product actions
  const { product, error, isLoading, addToCart, isAddingToCart, recordClick } =
    useProductActions(productId);

  // Reviews data
  const reviewsQuery = useProductReviews(productId);
  const summaryQuery = useProductReviewSummary(productId);
  const createReview = useCreateProductReview(productId);

  // Check if current user has already reviewed this product
  const userHasReviewed =
    reviewsQuery.data?.some(review => review.userId === user?.user_id) ?? false;

  // State for review summarization modal
  const [showSummarizeModal, setShowSummarizeModal] = useState(false);
  const [shouldSummarize, setShouldSummarize] = useState(false);

  // Handler for summarize button click
  const handleSummarizeClick = () => {
    setShouldSummarize(true);
    setShowSummarizeModal(true);
  };

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
                      rating={
                        summaryQuery.data?.avg_rating || product.rating || 0
                      }
                      starRatedColor='black'
                      numberOfStars={5}
                      name='rating'
                      starDimension='18px'
                      starSpacing='1px'
                    />{' '}
                    {summaryQuery.data?.avg_rating
                      ? summaryQuery.data.avg_rating.toFixed(1)
                      : product.rating
                        ? product.rating.toFixed(1)
                        : '0.0'}
                  </FlexItem>
                  <FlexItem headers='h1'>${product.actual_price}</FlexItem>
                  <FlexItem>{product.about_product}</FlexItem>
                  <FlexItem>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginTop: '1rem',
                      }}
                    >
                      <h3 style={{ margin: 0 }}>Reviews</h3>
                      <div
                        style={{
                          display: 'flex',
                          gap: '0.5rem',
                          alignItems: 'center',
                          flexWrap: 'wrap',
                        }}
                      >
                        {reviewsQuery.data && reviewsQuery.data.length > 0 && (
                          <Button
                            variant='secondary'
                            size='sm'
                            onClick={handleSummarizeClick}
                            style={{
                              background:
                                'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                              color: 'white',
                              border: 'none',
                              fontWeight: '600',
                              boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)',
                              transition: 'all 0.3s ease',
                              transform: 'translateY(0)',
                              alignSelf: 'center',
                            }}
                            onMouseEnter={e => {
                              e.currentTarget.style.transform =
                                'translateY(-2px)';
                              e.currentTarget.style.boxShadow =
                                '0 6px 20px rgba(102, 126, 234, 0.6)';
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.transform = 'translateY(0)';
                              e.currentTarget.style.boxShadow =
                                '0 4px 15px rgba(102, 126, 234, 0.4)';
                            }}
                          >
                            AI Summarize ✨
                          </Button>
                        )}
                        {!userHasReviewed ? (
                          <AddReviewInline
                            onSubmit={async (rating, title, comment) => {
                              await createReview.mutateAsync({
                                rating,
                                title,
                                comment,
                              });
                            }}
                            isSubmitting={createReview.isPending}
                          />
                        ) : (
                          <div
                            style={{
                              padding: '0.5rem',
                              background: '#f0f8ff',
                              border: '1px solid #d4edda',
                              borderRadius: '4px',
                              fontSize: '0.9rem',
                              color: '#155724',
                            }}
                          >
                            ✓ You have already reviewed this product
                          </div>
                        )}
                      </div>
                    </div>
                    {summaryQuery.isLoading ? (
                      <Skeleton width='200px' />
                    ) : (
                      <div style={{ marginBottom: '0.5rem' }}>
                        <strong>{summaryQuery.data?.count || 0}</strong> reviews
                        {summaryQuery.data && (
                          <>
                            {' '}
                            • Average:{' '}
                            <StarRatings
                              rating={summaryQuery.data.avg_rating || 0}
                              starRatedColor='black'
                              numberOfStars={5}
                              name='avg'
                              starDimension='14px'
                              starSpacing='1px'
                            />{' '}
                            {summaryQuery.data.avg_rating?.toFixed(1)}
                          </>
                        )}
                      </div>
                    )}
                    {reviewsQuery.isLoading ? (
                      <Skeleton height='180px' />
                    ) : reviewsQuery.data && reviewsQuery.data.length > 0 ? (
                      <div>
                        {reviewsQuery.data.map(r => (
                          <div key={r.id} style={{ marginBottom: '0.75rem' }}>
                            <div
                              style={{ display: 'flex', alignItems: 'center' }}
                            >
                              <StarRatings
                                rating={r.rating}
                                starRatedColor='black'
                                numberOfStars={5}
                                name={`r-${r.id}`}
                                starDimension='14px'
                                starSpacing='1px'
                              />
                              <span
                                style={{
                                  marginLeft: '0.5rem',
                                  fontWeight: 600,
                                }}
                              >
                                {r.title || 'Review'}
                              </span>
                            </div>
                            <div style={{ fontSize: '0.9rem', color: '#444' }}>
                              {r.comment}
                            </div>
                            <div
                              style={{
                                fontSize: '0.75rem',
                                color: '#777',
                                display: 'flex',
                                justifyContent: 'space-between',
                              }}
                            >
                              <span>By: {r.userName || 'Anonymous'}</span>
                              <span>
                                {new Date(r.created_at).toLocaleDateString()}
                              </span>
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

      {/* Review Summarization Modal */}
      <ReviewSummarizationModal
        productId={productId}
        isOpen={showSummarizeModal}
        onClose={() => {
          setShowSummarizeModal(false);
          setShouldSummarize(false);
        }}
        enabled={shouldSummarize}
      />
    </>
  );
};
