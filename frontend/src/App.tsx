import { BarChart3, Bot, History, Loader2, SlidersHorizontal, WifiOff } from "lucide-react";
import { lazy, Suspense, useEffect } from "react";
import { AssistantPanel } from "@/components/ai/AssistantPanel";
import { AssumptionsPanel } from "@/components/layout/AssumptionsPanel";
import { ComponentNav } from "@/components/layout/ComponentNav";
import { HistoryPanel } from "@/components/layout/HistoryPanel";
import { StatusBar } from "@/components/layout/StatusBar";
import { TopBar } from "@/components/layout/TopBar";
import { EngineeringPanel } from "@/components/panels/EngineeringPanel";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CarViewer } from "@/components/viewer/CarViewer";
import { API_BASE } from "@/lib/api";
import { useStore, type BottomTab } from "@/store";

const Dashboard = lazy(() => import("@/components/dashboard/Dashboard"));

function BootScreen({ error }: { error: string | null }) {
  const boot = useStore((s) => s.boot);
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="max-w-md text-center">
        {error ? (
          <>
            <WifiOff className="mx-auto mb-3 size-8 text-sev-critical" aria-hidden />
            <h1 className="text-lg font-semibold text-ink">Cannot reach the simulation backend</h1>
            <p className="mt-2 text-sm text-ink-2">{error}</p>
            <p className="mt-1 text-xs text-ink-3">
              Expected API at <code className="font-mono">{API_BASE || window.location.origin}/api/v1</code>. No simulated data is shown without the backend. On a free hosting tier
              the server may take up to a minute to wake up.
            </p>
            <Button className="mt-4" onClick={() => void boot()}>
              Retry
            </Button>
          </>
        ) : (
          <div className="flex items-center gap-2 text-sm text-ink-2">
            <Loader2 className="size-4 animate-spin text-accent" /> Connecting to the simulation backend…
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const car = useStore((s) => s.car);
  const bootError = useStore((s) => s.bootError);
  const simError = useStore((s) => s.simError);
  const bottomTab = useStore((s) => s.bottomTab);
  const setBottomTab = useStore((s) => s.setBottomTab);
  const boot = useStore((s) => s.boot);

  useEffect(() => {
    void boot();
  }, [boot]);

  if (!car) return <BootScreen error={bootError} />;

  return (
    <div className="flex min-h-full flex-col">
      <TopBar />
      {simError && (
        <div className="flex items-center gap-2 border-b border-sev-critical/40 bg-sev-critical/10 px-4 py-1.5 text-xs text-ink" role="alert" data-testid="sim-error">
          <WifiOff className="size-3.5 text-sev-critical" aria-hidden /> Simulation failed: {simError}. Results shown are from the last successful run.
        </div>
      )}
      <StatusBar />
      <main className="grid flex-1 grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)_380px]">
        <aside className="order-2 max-h-[340px] border-b border-line bg-panel lg:order-1 lg:max-h-none lg:border-b-0 lg:border-r">
          <ComponentNav />
        </aside>
        <section className="order-1 h-[52vh] min-h-[380px] lg:order-2 lg:h-[calc(100vh-150px)]" aria-label="3D car viewer">
          <CarViewer assetUrl={car.asset_url} />
        </section>
        <aside className="order-3 overflow-y-auto border-l border-line bg-panel lg:h-[calc(100vh-150px)]" aria-label="Engineering panel">
          <EngineeringPanel />
        </aside>
      </main>
      <section className="border-t border-line bg-bg" aria-label="Analysis">
        <Tabs value={bottomTab} onValueChange={(v) => setBottomTab(v as BottomTab)}>
          <TabsList className="sticky top-0 z-10 bg-bg">
            <TabsTrigger value="dashboard">
              <BarChart3 /> Performance dashboard
            </TabsTrigger>
            <TabsTrigger value="assistant">
              <Bot /> AI engineer
            </TabsTrigger>
            <TabsTrigger value="assumptions">
              <SlidersHorizontal /> Assumptions
            </TabsTrigger>
            <TabsTrigger value="history">
              <History /> History
            </TabsTrigger>
          </TabsList>
          <TabsContent value="dashboard">
            <Suspense fallback={<p className="p-6 text-sm text-ink-3">Loading charts…</p>}>
              <Dashboard />
            </Suspense>
          </TabsContent>
          <TabsContent value="assistant" className="mx-auto max-w-4xl">
            <AssistantPanel />
          </TabsContent>
          <TabsContent value="assumptions">
            <AssumptionsPanel />
          </TabsContent>
          <TabsContent value="history">
            <HistoryPanel />
          </TabsContent>
        </Tabs>
      </section>
      <footer className="border-t border-line px-4 py-3 text-[11px] text-ink-3">
        ApexVision AV-1 is an original, generic open-wheel concept and is not affiliated with or modelled on any real team or car. All results are MODEL-ESTIMATED from simplified engineering models: not
        CFD, not wind-tunnel data and not validated against a real vehicle. 3D damage is a kinematic visual representation, not a fracture model.
      </footer>
    </div>
  );
}
