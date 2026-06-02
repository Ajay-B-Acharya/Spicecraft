'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Plus } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { CreateSourceData } from '@/lib/circuitSourceService';

const schema = z.object({
  title: z.string().min(1, 'Title is required').max(255),
  source_name: z.string().max(255).optional(),
  source_url: z.string().url('Must be a valid URL').or(z.literal('')).optional(),
  image_url: z.string().url('Must be a valid URL').or(z.literal('')).optional(),
});

type FormData = z.infer<typeof schema>;

interface Props {
  onCreate: (data: CreateSourceData) => Promise<unknown>;
}

export function CreateSourceDialog({ onCreate }: Props) {
  const [open, setOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: FormData) => {
    try {
      const payload: CreateSourceData = {
        title: data.title,
        ...(data.source_name ? { source_name: data.source_name } : {}),
        ...(data.source_url ? { source_url: data.source_url } : {}),
        ...(data.image_url ? { image_url: data.image_url } : {}),
      };

      await onCreate(payload);
      toast.success('Source added');
      reset();
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add source');
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Add Source
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Circuit Source</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="mt-2 space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="source-title">Title</Label>
            <Input
              id="source-title"
              placeholder="e.g. NE555 Timer Datasheet"
              {...register('title')}
            />
            {errors.title && (
              <p className="text-xs text-destructive">{errors.title.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="source-name">
              Source Name <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="source-name"
              placeholder="e.g. Texas Instruments"
              {...register('source_name')}
            />
            {errors.source_name && (
              <p className="text-xs text-destructive">{errors.source_name.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="source-url">
              Source URL <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="source-url"
              placeholder="https://..."
              {...register('source_url')}
            />
            {errors.source_url && (
              <p className="text-xs text-destructive">{errors.source_url.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="image-url">
              Image URL <span className="text-muted-foreground">(optional)</span>
            </Label>
            <Input
              id="image-url"
              placeholder="https://..."
              {...register('image_url')}
            />
            {errors.image_url && (
              <p className="text-xs text-destructive">{errors.image_url.message}</p>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? 'Adding...' : 'Add Source'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
