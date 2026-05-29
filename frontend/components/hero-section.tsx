'use client';

import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { CircuitMockup } from './circuit-mockup';
import { FeaturesSection } from './features-section';

export function HeroSection() {
  return (
    <section className="circuit-bg relative min-h-screen overflow-hidden pt-24 pb-20">
      {/* Animated background blobs */}
      <div className="absolute top-0 -left-32 h-80 w-80 glow-blob glow-blob-purple opacity-30" />
      <div className="absolute bottom-20 right-0 h-96 w-96 glow-blob glow-blob-indigo opacity-20" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 glow-blob glow-blob-cyan opacity-10" />

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 relative z-10">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2 lg:gap-8 items-start">
          {/* Left side content */}
          <div className="space-y-8 flex flex-col justify-center">
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="inline-flex w-fit"
            >
              <div className="flex items-center gap-2 rounded-full border border-indigo-500/50 bg-indigo-500/10 px-4 py-2 text-sm text-indigo-300">
                <div className="h-2 w-2 rounded-full bg-indigo-400" />
                AI-POWERED CIRCUIT DESIGN
              </div>
            </motion.div>

            {/* Main headline */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
              className="space-y-4"
            >
              <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight">
                <span className="text-white">Design Real</span>
                <br />
                <span className="text-white">Circuits.</span>
                <br />
                <span className="gradient-text">Search. Edit. Export.</span>
              </h1>
            </motion.div>

            {/* Subheadline */}
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.2 }}
              className="max-w-md text-lg text-gray-300 leading-relaxed"
            >
              SpiceCraft discovers real-world circuits from trusted sources, converts them into editable schematics, and exports them directly to LTspice.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.3 }}
              className="pt-4"
            >
              <Button
                asChild
                size="lg"
                className="bg-gradient-to-r from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700 text-white rounded-full px-8 h-12 font-semibold shadow-lg hover:shadow-indigo-500/50 transition-all duration-300"
              >
                <Link href="/signup">Start Building</Link>
              </Button>
            </motion.div>

            {/* Features grid */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.4 }}
              className="pt-8"
            >
              <FeaturesSection />
            </motion.div>
          </div>

          {/* Right side - Circuit mockup */}
          <div className="relative h-full min-h-[600px] flex items-center justify-center">
            <CircuitMockup />
          </div>
        </div>
      </div>
    </section>
  );
}
