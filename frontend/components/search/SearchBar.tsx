'use client';

import { useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

interface Props {
  defaultValue?: string;
  loading?: boolean;
  onSearch: (query: string) => Promise<void> | void;
}

export function SearchBar({ defaultValue = '', loading = false, onSearch }: Props) {
  const [value, setValue] = useState(defaultValue);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await onSearch(value);
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Search FM transmitter BC547, LM358 datasheet, LTspice examples..."
          className="h-11 pl-10"
        />
      </div>
      <Button type="submit" className="h-11 px-6" disabled={loading}>
        {loading ? 'Searching...' : 'Search'}
      </Button>
    </form>
  );
}
