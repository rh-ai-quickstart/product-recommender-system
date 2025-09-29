import { PageSection } from '@patternfly/react-core';
import { createFileRoute } from '@tanstack/react-router';
import { LandingPage } from '../../components/landing-page';

export const Route = createFileRoute('/_protected/')({
  component: Recommendations,
});

function Recommendations() {
  return (
    <PageSection>
      <LandingPage />
    </PageSection>
  );
}
