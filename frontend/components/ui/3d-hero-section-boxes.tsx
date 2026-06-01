"use client";

import { CircuitMockup } from "@/components/circuit-mockup";
import { DottedSurface } from "@/components/ui/dotted-surface";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  FileCode2,
  FileSearch,
  PlayCircle,
  Rocket,
  ScanSearch,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { Navbar } from "@/components/navbar";
import Spline from "@splinetool/react-spline";

const techPills = ["React", "Python", "FastAPI", "LTspice", "AI Powered"];
const hoverCubes = [
  {
    className:
      "-left-6 top-10 h-10 w-10 border-violet-400/60 bg-violet-500/10 delay-0",
  },
  {
    className:
      "left-14 -top-6 h-6 w-6 border-sky-400/60 bg-sky-400/10 delay-75",
  },
  {
    className:
      "right-10 top-8 h-12 w-12 border-fuchsia-400/60 bg-fuchsia-500/10 delay-100",
  },
  {
    className:
      "-right-5 top-1/3 h-7 w-7 border-indigo-300/60 bg-indigo-400/10 delay-150",
  },
  {
    className:
      "left-8 bottom-12 h-8 w-8 border-cyan-300/60 bg-cyan-400/10 delay-200",
  },
  {
    className:
      "right-16 -bottom-5 h-11 w-11 border-violet-300/60 bg-violet-300/10 delay-300",
  },
];

const workflowSteps = [
  {
    number: "1",
    title: "Search",
    description:
      "Describe the circuit you need in natural language and let SpiceCraft interpret the request.",
    example: '"I need a frequency modulation circuit"',
    icon: FileSearch,
  },
  {
    number: "2",
    title: "Discover",
    description:
      "Search trusted electronics sources and collect real circuits that match your goal.",
    example: "Electronics Hub, Circuit Digest, RF Wireless World",
    icon: ScanSearch,
  },
  {
    number: "3",
    title: "Edit",
    description:
      "Modify the design with simple prompts and update components without redrawing manually.",
    example: '"Replace BC547 with 2N2222"',
    icon: WandSparkles,
  },
  {
    number: "4",
    title: "Export",
    description:
      "Export a clean `.asc` file and move straight into LTspice simulation.",
    example: "FM_Modulator.asc ready to simulate",
    icon: FileCode2,
  },
];

const featureCards = [
  {
    title: "Search Real Circuits",
    description:
      "Find real-world circuit designs from trusted electronics websites in seconds.",
    icon: ScanSearch,
  },
  {
    title: "Understand Schematics",
    description:
      "AI analyzes components, connections, and values to help decode any circuit quickly.",
    icon: BrainCircuit,
  },
  {
    title: "Edit with Prompts",
    description:
      "Modify circuits naturally with prompt-based changes instead of complex CAD workflows.",
    icon: Sparkles,
  },
  {
    title: "LTspice Ready",
    description:
      "Export clean, simulation-ready `.asc` files that drop directly into LTspice.",
    icon: FileCode2,
  },
];

const techStack = [
  { title: "Frontend", subtitle: "React + TypeScript" },
  { title: "Backend", subtitle: "Python + FastAPI" },
  { title: "AI Engine", subtitle: "LLM + Computer Vision" },
  { title: "Export", subtitle: "LTspice .asc" },
];

const roadmapItems = [
  {
    version: "V1",
    title: "Search + Export",
    description: "Search circuits and export them to LTspice `.asc`.",
  },
  {
    version: "V2",
    title: "Image Recognition",
    description: "Convert circuit images into editable schematics.",
  },
  {
    version: "V3",
    title: "Prompt Editing",
    description: "Modify circuits using natural language instructions.",
  },
  {
    version: "V4",
    title: "Circuit Validation",
    description: "Validate designs and prepare them for simulation faster.",
  },
  {
    version: "V5",
    title: "AI Circuit Design",
    description: "Generate optimized circuits directly from requirements.",
  },
];

function HeroSplineBackground() {
  return (
    <div className="absolute inset-0 bg-[#020617]">
      {/* Dotted wave shader — primary background effect */}
      <DottedSurface className="absolute inset-0 z-0" />
      {/* Soft colour glows on top of the dots */}
      <div className="pointer-events-none absolute inset-0 z-10 bg-[radial-gradient(ellipse_80%_50%_at_50%_0%,rgba(99,102,241,0.22),transparent),radial-gradient(ellipse_60%_40%_at_80%_30%,rgba(168,85,247,0.16),transparent)]" />
      {/* Bottom fade so sections below blend cleanly */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-40 bg-gradient-to-t from-[#020617] to-transparent" />
      {/* Subtle Spline overlay — dimmed so it doesn't hide the dots */}
      <Spline
        className="pointer-events-none absolute inset-0 z-20 h-full w-full opacity-10"
        scene="https://prod.spline.design/dJqTIQ-tE3ULUPMi/scene.splinecode"
      />
    </div>
  );
}

function SectionHeading({
  eyebrow,
  title,
  highlight,
  description,
}: {
  eyebrow?: string;
  title: string;
  highlight?: string;
  description?: string;
}) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      {eyebrow ? (
        <p className="mb-3 text-sm font-medium uppercase tracking-[0.35em] text-indigo-300/80">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
        {title}{" "}
        {highlight ? (
          <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-blue-400 bg-clip-text text-transparent">
            {highlight}
          </span>
        ) : null}
      </h2>
      {description ? (
        <p className="mx-auto mt-4 max-w-2xl text-sm leading-7 text-slate-300/80 sm:text-base">
          {description}
        </p>
      ) : null}
    </div>
  );
}

function HeroIntro() {
  return (
    <section className="relative z-10 mx-auto grid min-h-screen w-full max-w-7xl items-center gap-12 px-4 pb-20 pt-28 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:px-8 lg:pt-32">
      <div className="max-w-2xl">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-slate-950/50 px-4 py-2 text-sm text-indigo-200 shadow-[0_0_20px_rgba(99,102,241,0.15)] backdrop-blur-md">
          <Bot className="h-4 w-4 text-violet-400" />
          AI-Powered Circuit Design
        </div>

        <h1 className="mt-8 text-5xl font-semibold leading-[1.05] tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
          From{" "}
          <span className="bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
            Prompt
          </span>{" "}
          to LTspice.
          <br />
          Build Circuits with{" "}
          <span className="bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent">
            AI.
          </span>
        </h1>

        <p className="mt-6 max-w-xl text-lg leading-8 text-slate-300/85">
          Search real-world circuit designs, convert them into editable
          schematics, modify them with natural language, and export directly to
          LTspice.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/signup"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_10px_35px_rgba(99,102,241,0.35)] transition hover:scale-[1.02]"
          >
            Start Building
            <Rocket className="h-4 w-4" />
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center justify-center gap-2 rounded-2xl border border-white/15 bg-slate-950/55 px-6 py-3.5 text-sm font-semibold text-white backdrop-blur-md transition hover:border-white/30 hover:bg-white/8"
          >
            <PlayCircle className="h-4 w-4" />
            Watch Demo
          </Link>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          {techPills.map((pill) => (
            <span
              key={pill}
              className="rounded-xl border border-white/10 bg-slate-950/55 px-4 py-2 text-sm text-slate-200/85 backdrop-blur-md"
            >
              {pill}
            </span>
          ))}
        </div>
      </div>

      <div className="group relative">
        <div className="pointer-events-none absolute -inset-6 rounded-[32px] bg-[radial-gradient(circle,rgba(99,102,241,0.24),transparent_58%)] blur-3xl transition duration-500 group-hover:scale-105 group-hover:opacity-100" />
        {hoverCubes.map((cube) => (
          <div
            key={cube.className}
            className={`pointer-events-none absolute rounded-[0.85rem] border opacity-0 shadow-[0_0_30px_rgba(99,102,241,0.2)] transition-all duration-500 ease-out group-hover:translate-y-0 group-hover:scale-100 group-hover:rotate-12 group-hover:opacity-100 ${cube.className} translate-y-4 scale-75`}
          />
        ))}
        <div className="relative transition-transform duration-500 group-hover:-translate-y-1">
          <CircuitMockup />
        </div>
      </div>
    </section>
  );
}

function WorkflowSection() {
  return (
    <section
      id="how-it-works"
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8"
    >
      <div className="rounded-[28px] border border-white/10 bg-slate-950/45 p-6 shadow-[0_0_0_1px_rgba(255,255,255,0.03),0_25px_80px_rgba(2,6,23,0.35)] backdrop-blur-md sm:p-8">
        <SectionHeading
          title="How"
          highlight="SpiceCraft"
          description="A practical workflow that moves from search to simulation without forcing engineers to redraw everything by hand."
        />

        <div className="mt-10 grid gap-5 lg:grid-cols-4">
          {workflowSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div
                key={step.number}
                className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(2,6,23,0.76))] p-5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-indigo-400/30 bg-indigo-500/10 text-indigo-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-lg font-semibold text-violet-300">
                    {step.number}
                  </span>
                </div>
                <h3 className="mt-5 text-xl font-semibold text-white">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-300/80">
                  {step.description}
                </p>
                <div className="mt-5 rounded-2xl border border-white/8 bg-slate-900/70 px-4 py-3 text-sm text-slate-200/85">
                  {step.example}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function FeatureSection() {
  return (
    <section
      id="features"
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8"
    >
      <SectionHeading
        title="Why Engineers Love"
        highlight="SpiceCraft"
        description="The product experience stays grounded in real circuit workflows: discovery, understanding, editing, and export."
      />

      <div className="mt-10 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {featureCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.title}
              className="rounded-[26px] border border-white/10 bg-slate-950/50 p-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] backdrop-blur-md"
            >
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-indigo-400/25 bg-gradient-to-br from-indigo-500/15 to-fuchsia-500/10 text-sky-300">
                <Icon className="h-7 w-7" />
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-white">
                {card.title}
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-300/80">
                {card.description}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function TechSection() {
  return (
    <section
      id="docs"
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8"
    >
      <div className="rounded-[28px] border border-white/10 bg-slate-950/45 p-6 backdrop-blur-md sm:p-8">
        <SectionHeading
          eyebrow="Built with Modern Tech"
          title="Production-ready foundations for"
          highlight="engineering workflows"
        />

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {techStack.map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-white/10 bg-slate-900/65 px-5 py-5"
            >
              <p className="text-sm font-medium uppercase tracking-[0.25em] text-violet-300/80">
                {item.title}
              </p>
              <p className="mt-3 text-lg font-semibold text-white">
                {item.subtitle}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RoadmapSection() {
  return (
    <section
      id="roadmap"
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 lg:px-8"
    >
      <SectionHeading
        eyebrow="Our Roadmap"
        title="Shipping toward a more capable"
        highlight="AI circuit workspace"
      />

      <div className="mt-10 grid gap-5 lg:grid-cols-5">
        {roadmapItems.map((item, index) => (
          <div
            key={item.version}
            className="relative rounded-[24px] border border-white/10 bg-slate-950/50 p-5 backdrop-blur-md"
          >
            {index < roadmapItems.length - 1 ? (
              <div className="absolute -right-3 top-1/2 hidden h-px w-6 bg-gradient-to-r from-violet-400/60 to-sky-400/60 lg:block" />
            ) : null}
            <p className="text-sm font-medium uppercase tracking-[0.3em] text-violet-300/80">
              {item.version}
            </p>
            <h3 className="mt-4 text-xl font-semibold text-white">
              {item.title}
            </h3>
            <p className="mt-3 text-sm leading-7 text-slate-300/80">
              {item.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section className="relative z-10 mx-auto w-full max-w-7xl px-4 pb-24 pt-10 sm:px-6 lg:px-8">
      <div className="relative overflow-hidden rounded-[30px] border border-white/10 bg-[linear-gradient(135deg,rgba(15,23,42,0.88),rgba(30,27,75,0.72),rgba(2,6,23,0.92))] px-8 py-10 shadow-[0_35px_100px_rgba(0,0,0,0.35)] sm:px-10 lg:px-12">
        <div className="absolute right-0 top-0 h-full w-full bg-[radial-gradient(circle_at_bottom_right,rgba(99,102,241,0.35),transparent_32%),radial-gradient(circle_at_bottom_right,rgba(168,85,247,0.28),transparent_22%)]" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <h2 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
              Stop Drawing Circuits Manually.
              <br />
              <span className="bg-gradient-to-r from-sky-400 via-violet-400 to-fuchsia-400 bg-clip-text text-transparent">
                Search. Understand. Edit. Export.
              </span>
            </h2>
          </div>

          <Link
            href="/signup"
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-indigo-500 via-violet-500 to-fuchsia-500 px-6 py-3.5 text-sm font-semibold text-white shadow-[0_12px_35px_rgba(99,102,241,0.35)] transition hover:scale-[1.02]"
          >
            Start Building with SpiceCraft
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}

export function HeroSectionBoxes() {
  return (
    <div className="relative overflow-hidden bg-black">
      <HeroSplineBackground />
      <Navbar />

      <div className="relative">
        <HeroIntro />
        <WorkflowSection />
        <FeatureSection />
        <TechSection />
        <RoadmapSection />
        <FinalCta />
      </div>
    </div>
  );
}
