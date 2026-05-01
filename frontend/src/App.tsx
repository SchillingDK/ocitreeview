import React, { useRef, useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import TreeView from './TreeView';
import { TreeResponse } from './types';
import './App.css';

const queryClient = new QueryClient();

const API_BASE = 'http://localhost:8010';

// Default estimated load time for the very first fetch (ms).
const DEFAULT_ESTIMATE_MS = 30_000;

function formatCachedAt(cachedAt: string): string {
  const dt = new Date(cachedAt);
  return dt.toLocaleString('da-DK', { dateStyle: 'short', timeStyle: 'medium', timeZone: 'Europe/Copenhagen' })
    + ' ' + dt.toLocaleTimeString('da-DK', { timeZoneName: 'short', timeZone: 'Europe/Copenhagen' }).split(' ').pop();
}

function formatCacheAge(cachedAt: string): string {
  const then = new Date(cachedAt);
  const diffMs = Date.now() - then.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs} hour${diffHrs === 1 ? '' : 's'} ago`;
  return `${Math.floor(diffHrs / 24)} day${Math.floor(diffHrs / 24) === 1 ? '' : 's'} ago`;
}

function formatElapsed(ms: number): string {
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  return `${Math.floor(ms / 60_000)}m ${Math.round((ms % 60_000) / 1000)}s`;
}

interface LoadingBarProps {
  estimateMs: number;
}

const LoadingBar: React.FC<LoadingBarProps> = ({ estimateMs }) => {
  const [pct, setPct] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());
  const rafRef = useRef<number>(0);

  useEffect(() => {
    startRef.current = Date.now();
    const tick = () => {
      const elapsedMs = Date.now() - startRef.current;
      setElapsed(elapsedMs);
      // Ease toward 95% asymptotically so the bar never reaches 100% on its own.
      const raw = elapsedMs / estimateMs;
      const capped = 1 - Math.exp(-raw * 1.5);
      setPct(Math.min(capped * 95, 95));
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [estimateMs]);

  return (
    <div className="progress-bar" title={`Loading… ${formatElapsed(elapsed)} elapsed`}>
      <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      <span className="progress-bar-label">
        {formatElapsed(elapsed)}
        {estimateMs > 0 && (
          <> / ~{formatElapsed(estimateMs)}</>
        )}
      </span>
    </div>
  );
};

function OCITree() {
  const forceRef = useRef(false);
  const fetchStartRef = useRef<number | null>(null);
  const estimateRef = useRef<number>(DEFAULT_ESTIMATE_MS);
  const [estimateMs, setEstimateMs] = useState(DEFAULT_ESTIMATE_MS);

  const { data, isLoading, isError, refetch, isFetching } = useQuery<TreeResponse>({
    queryKey: ['oci-tree'],
    queryFn: async () => {
      fetchStartRef.current = Date.now();
      const force = forceRef.current;
      forceRef.current = false;
      const url = force ? `${API_BASE}/api/tree?force=true` : `${API_BASE}/api/tree`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      // Record how long this fetch actually took and use it as the next estimate.
      if (fetchStartRef.current !== null) {
        const duration = Date.now() - fetchStartRef.current;
        estimateRef.current = duration;
      }
      return json;
    },
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  const handleReload = () => {
    setEstimateMs(estimateRef.current);
    forceRef.current = true;
    refetch();
  };

  // On initial load, use the default estimate.
  useEffect(() => {
    if (isLoading) setEstimateMs(estimateRef.current);
  }, [isLoading]);

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="app-title">☁️ OCI Tree View</span>
        <div className="header-right">
          {data?.cached_at && !isFetching && (
            <span className="cache-age" title={`Data fetched from OCI at ${data.cached_at}`}>
              Data from OCI: {formatCachedAt(data.cached_at)} ({formatCacheAge(data.cached_at)})
            </span>
          )}
          <button
            className="refresh-btn"
            onClick={handleReload}
            disabled={isFetching}
          >
            {isFetching ? '⏳ Loading…' : '🔄 Reload from OCI'}
          </button>
        </div>
      </header>
      {isFetching && <LoadingBar estimateMs={estimateMs} />}
      <main className="app-main">
        {isLoading && !isFetching && <p className="status-msg">Loading OCI resources…</p>}
        {isError && (
          <p className="status-msg error">
            Failed to load data. Make sure the backend is running on{' '}
            <code>{API_BASE}</code>.
          </p>
        )}
        {data && data.regions.map((region) => (
          <div key={region.region}>
            {region.error && (
              <p className="status-msg error">
                ⚠️ <strong>{region.region}</strong>: {region.error}
              </p>
            )}
            <TreeView
              regionName={region.region}
              nodes={region.children}
            />
          </div>
        ))}
      </main>
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <OCITree />
    </QueryClientProvider>
  );
}

export default App;
