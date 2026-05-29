import { Navbar } from '@/components/navbar';
import { HeroSection } from '@/components/hero-section';
import { TrustSection } from '@/components/trust-section';

export default function Home() {
  return (
    <main className="min-h-screen bg-background text-foreground">
      <Navbar />
      <HeroSection />
      <TrustSection />
    </main>
  );
}
