"use client";

import { ArrowRight, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";
import Spline from "@splinetool/react-spline";

function HeroSplineBackground() {
  return (
    <div className="relative h-screen w-full overflow-hidden">
      <Spline
        className="h-screen w-full"
        scene="https://prod.spline.design/dJqTIQ-tE3ULUPMi/scene.splinecode"
      />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "linear-gradient(to right, rgba(0, 0, 0, 0.82), transparent 30%, transparent 70%, rgba(0, 0, 0, 0.82)), linear-gradient(to bottom, rgba(3, 7, 18, 0.08) 20%, rgba(0, 0, 0, 0.94) 92%)",
        }}
      />
    </div>
  );
}

function ScreenshotSection({
  screenshotRef,
}: {
  screenshotRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <section className="relative z-10 mx-auto -mt-[10vh] w-full max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
      <div
        ref={screenshotRef}
        className="mx-auto w-full overflow-hidden rounded-[28px] border border-white/10 bg-slate-950 shadow-[0_30px_80px_rgba(0,0,0,0.45)] md:w-[84%] lg:w-[72%]"
      >
        <img
          src="https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=80"
          alt="Product interface preview"
          className="block h-auto w-full"
        />
      </div>
    </section>
  );
}

function HeroContent() {
  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col justify-between gap-10 px-4 py-24 text-white sm:px-6 lg:flex-row lg:items-center lg:px-8">
      <div className="w-full lg:w-1/2">
        <h1 className="max-w-3xl text-4xl font-semibold leading-tight tracking-[-0.04em] sm:text-5xl md:text-6xl lg:text-7xl">
          We&apos;re Building
          <br />
          Cool Experiences
        </h1>
        <p className="mt-5 text-sm uppercase tracking-[0.35em] text-slate-300/80">
          AI / WEB3 / UI / 3D / MOTION
        </p>
      </div>

      <div className="flex w-full flex-col items-start lg:w-1/2 lg:pl-10">
        <p className="mb-7 max-w-md text-base leading-7 text-slate-200/80 sm:text-lg">
          Crafting awesome stories and sharp product experiences that help bold
          brands stand out.
        </p>

        <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
          <Link
            href="/login"
            className="inline-flex w-full items-center justify-center rounded-2xl border border-white/80 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white hover:text-black sm:w-auto"
          >
            Contact Us
          </Link>
          <Link
            href="/signup"
            className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-6 py-3 text-sm font-semibold text-black transition hover:scale-[1.02] sm:w-auto"
          >
            <Plus className="h-4 w-4 text-cyan-500" />
            Get Started
          </Link>
        </div>
      </div>
    </div>
  );
}

function Navbar() {
  return (
    <nav className="fixed inset-x-0 top-0 z-20">
      <div className="mx-auto flex max-w-7xl items-center justify-between rounded-b-2xl border border-white/10 bg-slate-950/30 px-4 py-4 backdrop-blur-md sm:px-6 lg:px-8">
        <div className="flex items-center gap-6 lg:gap-8">
          <Link href="/" className="flex items-center gap-2 text-white">
            <Sparkles className="h-7 w-7" />
            <span className="text-sm font-semibold uppercase tracking-[0.3em]">
              Spice Craft
            </span>
          </Link>

          <div className="hidden items-center gap-6 md:flex">
            <a href="#" className="text-sm text-slate-300 transition hover:text-white">
              Home
            </a>
            <a href="#" className="text-sm text-slate-300 transition hover:text-white">
              Cases
            </a>
            <a href="#" className="text-sm text-slate-300 transition hover:text-white">
              Library
            </a>
            <a href="#" className="text-sm text-slate-300 transition hover:text-white">
              Resources
            </a>
          </div>
        </div>

        <Link
          href="/signup"
          className="inline-flex items-center gap-2 rounded-full border border-white px-5 py-2 text-sm text-white transition hover:bg-white hover:text-black"
        >
          Let&apos;s Talk
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </nav>
  );
}

export function HeroSectionBoxes() {
  const screenshotRef = useRef<HTMLDivElement>(null);
  const heroContentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleScroll = () => {
      const screenshotElement = screenshotRef.current;
      const heroContentElement = heroContentRef.current;

      if (!screenshotElement || !heroContentElement) {
        return;
      }

      requestAnimationFrame(() => {
        const scrollPosition = window.pageYOffset;
        screenshotElement.style.transform = `translateY(-${scrollPosition * 0.15}px)`;

        const maxScroll = 360;
        const opacity = 1 - Math.min(scrollPosition / maxScroll, 1);
        heroContentElement.style.opacity = opacity.toString();
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="relative bg-black">
      <Navbar />

      <div className="relative min-h-screen">
        <div className="absolute inset-0 z-0">
          <HeroSplineBackground />
        </div>

        <div
          ref={heroContentRef}
          className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none"
        >
          <HeroContent />
        </div>
      </div>

      <div className="relative z-10 bg-black pb-24">
        <ScreenshotSection screenshotRef={screenshotRef} />
      </div>
    </div>
  );
}
