import { Cpu } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import type { CircuitComponent } from '@/lib/circuitService';

interface Props {
  components: CircuitComponent[];
  onValueChange: (componentId: string, value: string) => void;
  saving?: boolean;
}

export function CircuitComponentsTable({
  components,
  onValueChange,
  saving = false,
}: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="h-5 w-5" />
          Components
        </CardTitle>
      </CardHeader>
      <CardContent>
        {components.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Component ID</th>
                  <th className="px-4 py-3 font-medium">Component Type</th>
                  <th className="px-4 py-3 font-medium">Component Value</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {components.map((component, index) => (
                  <tr key={`${component.id}-${index}`} className="bg-background/40">
                    <td className="px-4 py-3 font-medium">{component.id}</td>
                    <td className="px-4 py-3 text-muted-foreground">{component.type}</td>
                    <td className="px-4 py-3">
                      <Input
                        value={component.value ?? ''}
                        onChange={(event) =>
                          onValueChange(component.id, event.target.value)
                        }
                        placeholder="-"
                        disabled={saving}
                        className="h-9 bg-muted/10"
                        aria-label={`Component value for ${component.id}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            No components are available for this circuit.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
