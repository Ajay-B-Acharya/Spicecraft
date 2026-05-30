import { Button } from '@/components/ui/button';
import { Cpu } from 'lucide-react';
import Link from 'next/link';

export function Navbar() {
  return (
    <nav className="fixed top-0 z-50 w-full border-b border-white/5 bg-background/80 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <div className="rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 p-2">
              <Cpu className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-lg text-white sm:text-xl">SpiceCraft</span>
          </Link>

          {/* Navigation Links */}
          <div className="hidden items-center gap-8 md:flex">
            <Link href="#features" className="text-sm text-gray-300 hover:text-white transition">
              Features
            </Link>
            <Link href="#how-it-works" className="text-sm text-gray-300 hover:text-white transition">
              How It Works
            </Link>
            <Link href="#examples" className="text-sm text-gray-300 hover:text-white transition">
              Examples
            </Link>
            <Link href="#roadmap" className="text-sm text-gray-300 hover:text-white transition">
              Roadmap
            </Link>
            <Link href="#docs" className="text-sm text-gray-300 hover:text-white transition">
              Docs
            </Link>
          </div>

          {/* Right side buttons */}
          <div className="flex items-center gap-4">
            <Button asChild variant="ghost" className="hidden text-gray-300 hover:text-white sm:inline-flex">
              <Link href="/login">Log In</Link>
            </Button>
            <Button
              asChild
              className="bg-gradient-to-r from-indigo-500 to-indigo-600 text-white rounded-full px-6 hover:from-indigo-600 hover:to-indigo-700"
            >
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
        </div>
      </div>
    </nav>
  );
}
