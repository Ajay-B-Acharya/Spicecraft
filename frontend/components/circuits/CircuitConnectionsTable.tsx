import { Network } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { CircuitWire } from '@/lib/circuitService';

interface Props {
  wires: CircuitWire[];
}

export function CircuitConnectionsTable({ wires }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Network className="h-5 w-5" />
          Connections
        </CardTitle>
      </CardHeader>
      <CardContent>
        {wires.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[420px] text-sm">
              <thead className="bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Source</th>
                  <th className="px-4 py-3 font-medium">Destination</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {wires.map((wire, index) => (
                  <tr key={`${wire.source}-${wire.destination}-${index}`} className="bg-background/40">
                    <td className="px-4 py-3 font-medium">{wire.source}</td>
                    <td className="px-4 py-3 text-muted-foreground">{wire.destination}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
            No wire connections are available for this circuit.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
