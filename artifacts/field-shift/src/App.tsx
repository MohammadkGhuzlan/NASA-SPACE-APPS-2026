import { useEffect, type ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import Landing from '@/pages/landing';
import Farms from '@/pages/farms';
import SelectLocation from '@/pages/select';
import FarmNew from '@/pages/farm-new';
import FarmOverview from '@/pages/farm-overview';
import FarmEdit from '@/pages/farm-edit';
import Planner from '@/pages/planner';
import Sources from '@/pages/sources';
import { Route, Switch, useLocation, Router as WouterRouter } from 'wouter';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

function Router() {
  const [location] = useLocation();
  useEffect(() => {
    const page = location === '/' ? ['Climate-aware crop rotation planning', 'Map your field, understand NASA POWER climate data, and compare your own rotation drafts.']
      : location === '/select' ? ['Select a farm location', 'Search worldwide, enter coordinates, or draw your field boundary.']
      : location === '/sources' ? ['Sources and limitations', 'Understand the provenance, coverage and limitations of Field Shift data.']
      : location === '/farms/new' ? ['Create a farm profile', 'Add your crop history, soil measurements and water constraints.']
      : location.endsWith('/planner') ? ['Crop rotation drafts', 'Compare two farmer-authored alternatives without unverified suitability claims.']
      : location.endsWith('/edit') ? ['Edit farm profile', 'Update your farmer-reported field information.']
      : location === '/farms' ? ['My farms', 'Open your saved farms and explore their environmental context.']
      : ['Farm environmental overview', 'View available climate records, provenance and missing-data warnings.'];
    document.title = `${page[0]} | Field Shift`;
    for (const selector of ['meta[name="description"]', 'meta[property="og:description"]', 'meta[name="twitter:description"]']) {
      document.querySelector(selector)?.setAttribute('content', page[1]!);
    }
    for (const selector of ['meta[property="og:title"]', 'meta[name="twitter:title"]']) {
      document.querySelector(selector)?.setAttribute('content', document.title);
    }
  }, [location]);
  return (
    <RoutedErrorBoundary>
      <Switch>
        <Route path="/" component={Landing} />
        <Route path="/farms" component={Farms} />
        <Route path="/select" component={SelectLocation} />
        <Route path="/farms/new" component={FarmNew} />
        <Route path="/farms/:id/edit" component={FarmEdit} />
        <Route path="/farms/:id/planner" component={Planner} />
        <Route path="/farms/:id" component={FarmOverview} />
        <Route path="/sources" component={Sources} />
        <Route component={NotFound} />
      </Switch>
    </RoutedErrorBoundary>
  );
}

function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
