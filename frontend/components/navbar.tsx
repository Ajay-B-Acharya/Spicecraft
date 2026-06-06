import { Button } from '@/components/ui/button';
import { Cpu } from 'lucide-react';
import Link from 'next/link';

export function Navbar() {
  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/10 bg-[#02040A]/95">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <div className="rounded-md border border-sky-300/25 bg-sky-300/10 p-2">
              <Cpu className="h-5 w-5 text-sky-300" />
            </div>
            <span className="font-bold text-lg text-white sm:text-xl">SpiceCraft</span>
          </Link>

          {/* Navigation Links */}
          <div className="hidden items-center gap-8 md:flex">
            <Link href="#features" className="text-sm text-slate-400 transition duration-200 hover:text-white">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm text-slate-400 transition duration-200 hover:text-white">
              How It Works
            </Link>
            <Link href="#examples" className="text-sm text-slate-400 transition duration-200 hover:text-white">
              Examples
            </Link>
            <Link href="#roadmap" className="text-sm text-slate-400 transition duration-200 hover:text-white">
              Roadmap
            </Link>
            <Link href="#docs" className="text-sm text-slate-400 transition duration-200 hover:text-white">
              Docs
            </Link>
          </div>

          {/* Right side buttons */}
          <div className="flex items-center gap-4">
            <Button asChild variant="ghost" className="hidden text-slate-400 hover:bg-white/5 hover:text-white sm:inline-flex">
              <Link href="/login">Log In</Link>
            </Button>
            <Button
              asChild
              className="rounded-lg bg-sky-400 px-6 text-[#02040A] transition duration-200 hover:-translate-y-0.5 hover:bg-sky-300"
            >
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
        </div>
      </div>
    </nav>
  );
}
