import { PageSection, Title, Spinner, Alert } from '@patternfly/react-core';
import { LazyProductGallery } from './LazyProductGallery';
import { usePersonalizedRecommendations } from '../hooks/useRecommendations';
import { useAuth } from '../contexts/AuthProvider';
import { DEFAULT_BATCH_SIZE, DEFAULT_INITIAL_BATCH_SIZE } from '../constants';

export function LandingPage() {
  const { isAuthenticated } = useAuth();
  const { data, isLoading, error } = usePersonalizedRecommendations();

  const products = data ? data : [];

  // If not authenticated, show a message prompting to log in
  if (!isAuthenticated) {
    return (
      <PageSection hasBodyWrapper={false}>
        <Title headingLevel='h1' style={{ marginTop: '15px' }}>
          Welcome to Product Recommendations
        </Title>
        <Alert variant='info' title='Authentication Required'>
          Please log in to see personalized product recommendations tailored
          just for you!
        </Alert>
      </PageSection>
    );
  }

  if (isLoading) {
    return (
      <PageSection>
        <Spinner size='lg' />
      </PageSection>
    );
  }

  if (error) {
    return (
      <PageSection>
        <Alert variant='danger' title='Error'>
          Sorry, we couldn't load your personalized recommendations right now.
          Please try again later.
        </Alert>
      </PageSection>
    );
  }

  return (
    <>
      <PageSection hasBodyWrapper={false}>
        <Title headingLevel={'h1'} style={{ marginTop: '15px' }}>
          Recommended for You
        </Title>
      </PageSection>

      <LazyProductGallery
        products={products}
        showProductCount={true}
        showScrollToTop={true}
        initialBatchSize={DEFAULT_INITIAL_BATCH_SIZE}
        batchSize={DEFAULT_BATCH_SIZE}
        loadingDelay={0}
      />
    </>
  );
}
