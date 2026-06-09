import { AlertCircle, Save } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ExportLTspiceButton } from '@/components/circuits/ExportLTspiceButton';

interface Props {
  circuitId: string;
  circuitName: string;
  hasUnsavedChanges: boolean;
  onSave: () => Promise<void> | void;
  saving: boolean;
}

export function CircuitEditorActions({
  circuitId,
  circuitName,
  hasUnsavedChanges,
  onSave,
  saving,
}: Props) {
  return (
    <div className="flex flex-col gap-3 sm:items-end">
      <div className="flex flex-wrap items-center gap-3">
        <Badge
          variant={hasUnsavedChanges ? 'secondary' : 'outline'}
          className={hasUnsavedChanges ? 'border-amber-500/30 bg-amber-500/10 text-amber-200' : ''}
        >
          <AlertCircle className="h-3.5 w-3.5" />
          {hasUnsavedChanges ? 'Unsaved Changes' : 'All Changes Saved'}
        </Badge>

        <ExportLTspiceButton circuitId={circuitId} circuitName={circuitName} />

        <Button onClick={onSave} disabled={!hasUnsavedChanges || saving}>
          <Save className="mr-2 h-4 w-4" />
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
      <p className="text-sm text-muted-foreground">
        Component value edits stay local until saved.
      </p>
    </div>
  );
}
