'use client';

import Link from 'next/link';
import { ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

interface Props {
  title: string;
  description: string;
  accentLabel: string;
}

export function RoutePlaceholder({ title, description, accentLabel }: Props) {
  return (
    <div className="space-y-6">
      <div className="overflow-hidden rounded-3xl border bg-gradient-to-br from-background via-background to-muted/30 p-8 shadow-sm">
        <div className="max-w-2xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-muted-foreground">
            {accentLabel}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {title}
          </h1>
          <p className="max-w-xl text-sm text-muted-foreground sm:text-base">
            {description}
          </p>
          <div className="pt-2">
            <Button asChild>
              <Link href="/dashboard">
                Back to Dashboard
                <ArrowRight className="ml-2 h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>
      </div>

      <Card className="border-dashed">
        <CardContent className="flex min-h-48 items-center justify-center p-8 text-center">
          <div className="max-w-md space-y-2">
            <p className="text-sm font-medium">Placeholder page</p>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
