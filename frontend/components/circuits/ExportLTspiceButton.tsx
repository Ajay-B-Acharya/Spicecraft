'use client';

import { useState } from 'react';
import { Download, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ltspiceExportService } from '@/lib/ltspiceExportService';

type ExportState = 'idle' | 'loading' | 'success' | 'error';

interface Props {
  circuitId: string;
  circuitName: string;
}

/**
 * Self-contained button that exports a circuit as a LTspice .asc file.
 *
 * States:
 *  idle    → "Export LTspice (.asc)"  — ready to click
 *  loading → "Exporting…"             — request in-flight, disabled
 *  success → "Downloaded!"            — shown for 2 s, then resets to idle
 *  error   → short error message      — shown for 4 s, then resets to idle
 */
export function ExportLTspiceButton({ circuitId, circuitName }: Props) {
  const [state, setState] = useState<ExportState>('idle');
  const [errorMessage, setErrorMessage] = useState('');

  const handleExport = async () => {
    if (state === 'loading') return;

    setState('loading');
    setErrorMessage('');

    try {
      // Build a clean filename from the circuit name
      const safeName = circuitName.replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_');
      const filename = `${safeName || circuitId}.asc`;

      await ltspiceExportService.exportAsc(circuitId, filename);

      setState('success');
      setTimeout(() => setState('idle'), 2000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Export failed';
      setErrorMessage(msg);
      setState('error');
      setTimeout(() => setState('idle'), 4000);
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
      <Button
        variant="outline"
        disabled
        className="min-w-[190px] border-rose-500/40 bg-rose-500/10 text-rose-400"
        title={errorMessage}
      >
        <AlertCircle className="mr-2 h-4 w-4 shrink-0" />
        <span className="truncate">{errorMessage || 'Export failed'}</span>
      </Button>
    );
  }

  // idle
  return (
    <Button variant="outline" onClick={handleExport} className="min-w-[190px]">
      <Download className="mr-2 h-4 w-4" />
      Export LTspice (.asc)
    </Button>
  );
}
