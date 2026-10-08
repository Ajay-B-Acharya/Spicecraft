'use client';

import { useEffect, useRef, useState } from 'react';
import { Download, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ltspiceExportService } from '@/lib/ltspiceExportService';

type ExportState = 'idle' | 'loading' | 'success' | 'error';

interface Props {
  circuitId: string;
  circuitName: string;
  disabled?: boolean;
}

/**
 * Self-contained button that exports a circuit as a LTspice .asc file.
 *
 * States:
 *  idle    → "Export LTspice (.asc)"  — ready to click
 *  loading → "Exporting…"             — request in-flight, disabled
 *  success → "Downloaded!"            — shown for 2 s, then resets to idle
 *  error   → persistent diagnostics with explicit retry
 */
export function ExportLTspiceButton({ circuitId, circuitName, disabled = false }: Props) {
  const [state, setState] = useState<ExportState>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const inFlight = useRef(false);
  const revision = useRef(0);
  const resetTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    revision.current++;
    setState('idle');
    setErrorMessage('');
    return () => {
      revision.current++;
      clearTimeout(resetTimer.current);
    };
  }, [circuitId]);

  const handleExport = async () => {
    if (inFlight.current || disabled) return;
    inFlight.current = true;
    const started = revision.current;
    clearTimeout(resetTimer.current);
    setState('loading');
    setErrorMessage('');

    try {
      // Build a clean filename from the circuit name
      const safeName = circuitName.replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_');
      const filename = `${safeName || circuitId}.asc`;

      await ltspiceExportService.exportAsc(circuitId, filename);

      if (started !== revision.current) return;
      setState('success');
      resetTimer.current = setTimeout(() => setState('idle'), 2000);
    } catch (err) {
      if (started !== revision.current) return;
      const msg = err instanceof Error ? err.message : 'Export failed';
      setErrorMessage(msg);
      setState('error');
    } finally {
      inFlight.current = false;
    }
  };

  if (state === 'loading') {
    return (
      <Button variant="outline" disabled className="min-w-[190px]">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        Exporting…
      </Button>
    );
  }

  if (state === 'success') {
    return (
      <Button
        variant="outline"
        disabled
        className="min-w-[190px] border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
      >
        <CheckCircle2 className="mr-2 h-4 w-4" />
        Downloaded!
      </Button>
    );
  }

  if (state === 'error') {
    return (
      <div className="max-w-xl space-y-2">
        <p role="alert" className="whitespace-pre-wrap break-words text-sm text-rose-400">{errorMessage}</p>
        <Button variant="outline" onClick={handleExport} disabled={disabled}>
          <AlertCircle className="mr-2 h-4 w-4 shrink-0" />
          Retry export
        </Button>
      </div>
    );
  }

  // idle
  return (
    <Button variant="outline" onClick={handleExport} disabled={disabled} className="min-w-[190px]">
      <Download className="mr-2 h-4 w-4" />
      Export LTspice (.asc)
    </Button>
  );
}
