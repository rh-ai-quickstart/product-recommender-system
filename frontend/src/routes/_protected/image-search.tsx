import { PageSection } from '@patternfly/react-core';
import { createFileRoute } from '@tanstack/react-router';
import { ImageSearchResultsPage } from '../../components/image-search-results';

export const Route = createFileRoute('/_protected/image-search')({
  component: ImageSearch,
  validateSearch: (search: Record<string, unknown>) => ({
    type: search.type as 'url' | 'file',
    query: search.query as string,
    fileId: search.fileId as string,
  }),
});

function ImageSearch() {
  const { type, query, fileId } = Route.useSearch();

  return (
    <PageSection hasBodyWrapper={false}>
      <ImageSearchResultsPage type={type} query={query} fileId={fileId} />
    </PageSection>
  );
}
