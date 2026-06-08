import { Cpu, Network, Tag } from 'lucide-react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Circuit } from '@/lib/circuitService';

interface Props {
  circuit: Circuit;
}

export function CircuitOverview({ circuit }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Description</p>
          <p className="text-sm leading-6 text-foreground/90">{circuit.description}</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Tag className="h-4 w-4" />
              Category
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{circuit.category}</p>
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Cpu className="h-4 w-4" />
              Components
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {circuit.components.length} items
            </p>
          </div>

          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Network className="h-4 w-4" />
              Wires
            </div>
            <p className="mt-2 text-sm text-muted-foreground">
              {circuit.wires.length} connections
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
