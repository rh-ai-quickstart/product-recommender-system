import { createFileRoute, Outlet, redirect } from '@tanstack/react-router';
import { Page } from '@patternfly/react-core';
import { AppMasthead } from '../../components/app-masthead';
import { validateToken } from '../../services/auth';

export const Route = createFileRoute('/_protected')({
  beforeLoad: ({ location }) => {
    // Use centralized token validation
    const { shouldRedirect } = validateToken();

    if (shouldRedirect) {
      throw redirect({
        to: '/login',
        search: {
          redirect: location.href,
        },
      });
    }
  },
  component: ProtectedLayout,
});

function ProtectedLayout() {
  return (
    <Page masthead={<AppMasthead />}>
      <Outlet />
    </Page>
  );
}
