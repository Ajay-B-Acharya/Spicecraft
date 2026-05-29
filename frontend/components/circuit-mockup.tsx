'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { X, Download, Check, Zap, Maximize2, Share2, Settings2, Copy, Grid3x3, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function CircuitMockup() {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.6, delay: 0.3 }}
      className="floating relative h-full w-full max-w-2xl"
    >
      {/* Glow effects */}
      <div className="absolute -top-20 -right-20 h-40 w-40 glow-blob glow-blob-indigo" />
      <div className="absolute -bottom-32 -left-32 h-64 w-64 glow-blob glow-blob-cyan opacity-20" />

      {/* Main container */}
      <div className="pulse-border relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900/50 to-slate-800/30 p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-gradient-to-br from-indigo-500 to-purple-600">
              <Zap className="h-4 w-4 text-white" />
            </div>
            <span className="text-sm font-semibold text-white">SpiceCraft</span>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" className="h-8 bg-transparent border-white/20 text-white hover:bg-white/10">
              Auto Layout
            </Button>
            <Button size="sm" className="h-8 bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:from-indigo-700 hover:to-purple-700">
              Export .asc
            </Button>
            <button className="text-gray-400 hover:text-white transition">
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex gap-6">
          {/* Left Panel - AI Assistant */}
          <div className="w-48 space-y-4 border-r border-white/10 pr-6">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-xs font-semibold text-white">
                <Zap className="h-3 w-3 text-indigo-400" />
                AI Assistant
              </div>
            </div>

            {/* Chat bubbles */}
            <div className="space-y-3 max-h-60 overflow-y-auto">
              <div className="rounded-lg bg-indigo-600/30 border border-indigo-500/30 p-3">
                <p className="text-xs text-white">I want a frequency modulation circuit</p>
              </div>
              <div className="space-y-2">
                <div className="flex items-center gap-1 text-xs text-cyan-400">
                  <RefreshCw className="h-3 w-3 animate-spin" />
                  Searching sources...
                </div>
                <div className="text-xs text-gray-400">Found 8 relevant circuits from trusted sources</div>
              </div>
            </div>

            {/* Input */}
            <div className="mt-auto space-y-2 border-t border-white/10 pt-4">
              <input
                type="text"
                placeholder="Ask or edit anything..."
                className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-gray-500 focus:border-indigo-500/50 focus:outline-none"
              />
            </div>
          </div>

          {/* Right Panel - Schematic */}
          <div className="flex-1">
            <svg className="h-80 w-full" viewBox="0 0 600 500" xmlns="http://www.w3.org/2000/svg">
              {/* Grid */}
              <defs>
                <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                  <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(99,102,241,0.1)" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="600" height="500" fill="url(#grid)" />

              {/* Ground symbols */}
              <g id="gnd">
                <line x1="0" y1="0" x2="0" y2="8" stroke="rgba(99,102,241,0.8)" strokeWidth="1.5" />
                <line x1="-6" y1="8" x2="6" y2="8" stroke="rgba(99,102,241,0.8)" strokeWidth="1.5" />
                <line x1="-4" y1="12" x2="4" y2="12" stroke="rgba(99,102,241,0.8)" strokeWidth="1.5" />
                <line x1="-2" y1="16" x2="2" y2="16" stroke="rgba(99,102,241,0.8)" strokeWidth="1.5" />
              </g>

              {/* Voltage source */}
              <circle cx="100" cy="350" r="20" fill="none" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
              <text x="100" y="356" textAnchor="middle" fontSize="10" fill="rgba(99,102,241,0.8)">9V</text>

              {/* Wire */}
              <line x1="100" y1="330" x2="100" y2="200" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
              <line x1="100" y1="200" x2="200" y2="200" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />

              {/* R1 (10k) */}
              <g>
                <line x1="200" y1="200" x2="200" y2="160" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <rect x="190" y="140" width="20" height="20" fill="none" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <text x="230" y="152" fontSize="12" fill="rgba(99,102,241,0.7)">R1 10k</text>
              </g>

              {/* R2 (4.7k) */}
              <g>
                <line x1="400" y1="200" x2="400" y2="160" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <rect x="390" y="140" width="20" height="20" fill="none" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <text x="420" y="152" fontSize="12" fill="rgba(99,102,241,0.7)">R2 4.7k</text>
              </g>

              {/* C1 */}
              <g>
                <line x1="250" y1="120" x2="350" y2="120" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <line x1="300" y1="100" x2="300" y2="140" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <line x1="290" y1="110" x2="310" y2="110" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <line x1="290" y1="130" x2="310" y2="130" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <text x="305" y="95" fontSize="12" fill="rgba(99,102,241,0.7)">C4 100nF</text>
              </g>

              {/* Inductor */}
              <g>
                <path d="M 450 160 Q 460 160 465 150 Q 470 160 475 150" fill="none" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <line x1="475" y1="150" x2="475" y2="120" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <text x="490" y="145" fontSize="12" fill="rgba(99,102,241,0.7)">L1 10µH</text>
              </g>

              {/* Transistor (BC547) */}
              <circle cx="350" cy="320" r="15" fill="none" stroke="rgba(6,182,212,0.6)" strokeWidth="1.5" />
              <circle cx="350" cy="320" r="8" fill="none" stroke="rgba(6,182,212,0.5)" strokeWidth="1" />
              <text x="370" y="325" fontSize="12" fill="rgba(6,182,212,0.7)">Q1 BC547</text>

              {/* C2 */}
              <g>
                <line x1="500" y1="200" x2="500" y2="240" stroke="rgba(99,102,241,0.5)" strokeWidth="1.5" />
                <line x1="490" y1="260" x2="510" y2="260" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <line x1="490" y1="280" x2="510" y2="280" stroke="rgba(99,102,241,0.6)" strokeWidth="1.5" />
                <text x="515" y="275" fontSize="12" fill="rgba(99,102,241,0.7)">C1 10nF</text>
              </g>

              {/* Output label */}
              <text x="520" y="150" fontSize="14" fontWeight="bold" fill="rgba(99,102,241,0.8)">Vout</text>

              {/* Connection nodes */}
              <circle cx="100" cy="200" r="3" fill="rgba(99,102,241,0.8)" />
              <circle cx="200" cy="200" r="3" fill="rgba(99,102,241,0.8)" />
              <circle cx="400" cy="200" r="3" fill="rgba(99,102,241,0.8)" />
              <circle cx="300" cy="120" r="3" fill="rgba(99,102,241,0.8)" />
            </svg>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 flex items-center justify-between border-t border-white/10 pt-4">
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <Grid3x3 className="h-4 w-4" />
            <span>100%</span>
          </div>
          <div className="flex items-center gap-2">
            <button className="rounded p-1 hover:bg-white/10 text-gray-400 hover:text-white transition">
              <RefreshCw className="h-4 w-4" />
            </button>
            <button className="rounded p-1 hover:bg-white/10 text-gray-400 hover:text-white transition">
              <Share2 className="h-4 w-4" />
            </button>
            <button className="rounded p-1 hover:bg-white/10 text-gray-400 hover:text-white transition">
              <Settings2 className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
