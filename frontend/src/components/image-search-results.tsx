import {
  PageSection,
  Title,
  EmptyState,
  EmptyStateBody,
} from '@patternfly/react-core';
import { LazyProductGallery } from './LazyProductGallery';
import { GallerySkeleton } from './gallery-skeleton';
import {
  useProductSearchByImageLink,
  useProductSearchByImage,
} from '../hooks/useProducts';
import { DEFAULT_SEARCH_RESULTS_COUNT } from '../constants';

interface ImageSearchResultsPageProps {
  type: 'url' | 'file';
  query: string;
  fileId: string;
}

export function ImageSearchResultsPage({
  type,
  query,
  fileId,
}: ImageSearchResultsPageProps) {
  // Get the stored file for file searches
  const getStoredFile = (id: string): File | null => {
    if (!id) return null;
    try {
      const stored = localStorage.getItem(`temp_image_${id}`);
      if (!stored) return null;

      const { name, type, dataUrl } = JSON.parse(stored);
      // Convert base64 back to File
      const byteCharacters = atob(dataUrl.split(',')[1]);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      return new File([byteArray], name, { type });
    } catch (error) {
      console.error('Error retrieving stored file:', error);
      return null;
    }
  };

  const storedFile = type === 'file' ? getStoredFile(fileId) : null;

  // Use appropriate hook based on search type
  const urlResults = useProductSearchByImageLink(
    query,
    DEFAULT_SEARCH_RESULTS_COUNT,
    type === 'url' && !!query
  );

  const fileResults = useProductSearchByImage(
    storedFile,
    DEFAULT_SEARCH_RESULTS_COUNT,
    type === 'file' && !!storedFile
  );

  const { data, error, isLoading } = type === 'url' ? urlResults : fileResults;
  const products = data || [];

  // Determine display query
  const displayQuery =
    type === 'url' ? query : storedFile?.name || 'uploaded image';

  if (!query && !fileId) {
    return (
      <PageSection hasBodyWrapper={false}>
        <EmptyState>
          <Title headingLevel='h4' size='lg'>
            No search parameters provided
          </Title>
          <EmptyStateBody>
            Please provide an image URL or upload a file to search for similar
            products.
          </EmptyStateBody>
        </EmptyState>
      </PageSection>
    );
  }

  if (type === 'file' && !storedFile) {
    return (
      <PageSection hasBodyWrapper={false}>
        <EmptyState>
          <Title headingLevel='h4' size='lg'>
            Image file not found
          </Title>
          <EmptyStateBody>
            The uploaded image could not be found. Please try uploading again.
          </EmptyStateBody>
        </EmptyState>
      </PageSection>
    );
  }

  if (isLoading) {
    return (
      <PageSection hasBodyWrapper={false}>
        <Title headingLevel={'h1'} style={{ marginTop: '15px' }}>
          Image Search Results for "{displayQuery}"
        </Title>
        <GallerySkeleton count={8} />
      </PageSection>
    );
  }

  if (error) {
    return (
      <PageSection hasBodyWrapper={false}>
        <Title headingLevel={'h1'} style={{ marginTop: '15px' }}>
          Image Search Results for "{displayQuery}"
        </Title>
        <EmptyState>
          <Title headingLevel='h4' size='lg'>
            Error searching for similar products
          </Title>
          <EmptyStateBody>
            There was an error while searching for similar products. Please try
            again.
            {error instanceof Error && (
              <div
                style={{
                  marginTop: '8px',
                  fontStyle: 'italic',
                  fontSize: '14px',
                  opacity: 0.8,
                }}
              >
                {error.message}
              </div>
            )}
          </EmptyStateBody>
        </EmptyState>
      </PageSection>
    );
  }

  return (
    <>
      <PageSection hasBodyWrapper={false}>
        <Title headingLevel={'h1'} style={{ marginTop: '15px' }}>
          Image Search Results for "{displayQuery}"
        </Title>

        {products.length === 0 ? (
          <EmptyState>
            <Title headingLevel='h4' size='lg'>
              No similar products found
            </Title>
            <EmptyStateBody>
              No similar products found for "{displayQuery}". Try a different
              image or search criteria.
            </EmptyStateBody>
          </EmptyState>
        ) : (
          <LazyProductGallery
            products={products}
            showProductCount={true}
            showScrollToTop={true}
          />
        )}
      </PageSection>
    </>
  );
}
