import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import type { Circuit } from '@/lib/circuitService';

interface Props {
  circuit: Circuit;
}

export function CircuitCard({ circuit }: Props) {
  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="line-clamp-2 text-lg">{circuit.name}</CardTitle>
          <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
            {circuit.category}
          </span>
        </div>
      </CardHeader>
      <CardContent className="flex-1">
        <p className="line-clamp-4 text-sm leading-6 text-muted-foreground">
          {circuit.description}
        </p>
      </CardContent>
      <CardFooter>
        <Button asChild className="w-full sm:w-auto">
          <Link href={`/circuits/${circuit.id}`}>
            View Circuit
            <ArrowRight className="ml-1.5 h-4 w-4" />
          </Link>
        </Button>
      </CardFooter>
    </Card>
  );
}
