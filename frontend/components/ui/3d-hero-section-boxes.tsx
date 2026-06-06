"use client";

import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  FileCode2,
  FileSearch,
  PlayCircle,
  Rocket,
  ScanSearch,
  Sparkles,
  WandSparkles,
  Zap,
} from "lucide-react";
import Link from "next/link";
import type { MouseEvent } from "react";
import { Navbar } from "@/components/navbar";

const techPills = ["React", "Python", "FastAPI", "LTspice", "AI Powered"];

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

function PageBackground() {
  return (
    <div className="pointer-events-none absolute inset-0">
      <div className="absolute inset-0 bg-[#02040A]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(56,189,248,0.16),transparent_34%),radial-gradient(circle_at_85%_18%,rgba(34,211,238,0.08),transparent_28%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.025)_1px,transparent_1px)] bg-[size:64px_64px]" />
      <div className="absolute inset-x-0 bottom-0 h-80 bg-gradient-to-t from-[#02040A] to-transparent" />
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
    <div className="mx-auto max-w-3xl text-center fade-up">
      {eyebrow ? (
        <p className="mb-3 text-xs font-semibold uppercase tracking-[0.32em] text-sky-300/80">
          {eyebrow}
        </p>
      ) : null}
      <h2 className="text-3xl font-bold tracking-tight text-white sm:text-5xl">
        {title}{" "}
        {highlight ? <span className="text-sky-300">{highlight}</span> : null}
      </h2>
      {description ? (
        <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
          {description}
        </p>
      ) : null}
    </div>
  );
}

function ProductScreenshot() {
  const handlePointerMove = (event: MouseEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width - 0.5) * 10;
    const y = ((event.clientY - rect.top) / rect.height - 0.5) * -10;
    event.currentTarget.style.setProperty("--rx", `${y}deg`);
    event.currentTarget.style.setProperty("--ry", `${x}deg`);
    event.currentTarget.style.setProperty("--tx", `${x * 0.7}px`);
    event.currentTarget.style.setProperty("--ty", `${y * -0.5}px`);
  };

  const handlePointerLeave = (event: MouseEvent<HTMLDivElement>) => {
    event.currentTarget.style.setProperty("--rx", "0deg");
    event.currentTarget.style.setProperty("--ry", "0deg");
    event.currentTarget.style.setProperty("--tx", "0px");
    event.currentTarget.style.setProperty("--ty", "0px");
  };

  return (
    <div
      className="group relative mx-auto w-full max-w-2xl [perspective:1400px]"
      onMouseMove={handlePointerMove}
      onMouseLeave={handlePointerLeave}
    >
      <div className="absolute -inset-px rounded-[18px] bg-[radial-gradient(circle_at_75%_20%,rgba(56,189,248,0.2),transparent_32%)]" />
      <div className="relative overflow-hidden rounded-[18px] border border-white/10 bg-[#050816] shadow-[0_30px_90px_rgba(0,0,0,0.42)] transition-transform duration-200 ease-out will-change-transform group-hover:-translate-y-0.5 lg:[transform:translate3d(var(--tx,0),var(--ty,0),0)_rotateX(var(--rx,0))_rotateY(var(--ry,0))]">
        <div className="flex items-center justify-between border-b border-white/10 bg-[#080B14] px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md border border-sky-300/20 bg-sky-400/10 text-sky-300">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">FM_Modulator.asc</p>
              <p className="text-xs text-slate-500">LTspice export workflow</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="rounded-md border border-white/10 px-2.5 py-1 text-xs text-slate-400">
              100%
            </span>
            <span className="rounded-md bg-sky-400 px-3 py-1 text-xs font-semibold text-[#02040A]">
              Export .asc
            </span>
          </div>
        </div>

        <div className="grid min-h-[420px] grid-cols-1 lg:grid-cols-[180px_1fr]">
          <aside className="border-b border-white/10 bg-[#050816] p-4 lg:border-b-0 lg:border-r">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
              Workflow
            </p>
            <div className="mt-4 space-y-2">
              {["Search sources", "Analyze topology", "Edit component", "Export to LTspice"].map(
                (item, index) => (
                  <div
                    key={item}
                    className="flex items-center gap-2 rounded-md border border-white/8 bg-white/[0.025] px-3 py-2 text-xs text-slate-300"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5 text-sky-300" />
                    {item}
                    {index === 3 ? (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-sky-300" />
                    ) : null}
                  </div>
                ),
              )}
            </div>

            <div className="mt-5 rounded-md border border-white/10 bg-[#080B14] p-3">
              <p className="text-xs font-medium text-white">Prompt edit</p>
              <p className="mt-2 text-xs leading-5 text-slate-500">
                Replace BC547 with 2N2222 and prepare simulation file.
              </p>
            </div>
          </aside>

          <main className="relative overflow-hidden bg-[#03050D]">
            <div className="absolute inset-0 bg-[linear-gradient(rgba(56,189,248,0.08)_1px,transparent_1px),linear-gradient(90deg,rgba(56,189,248,0.08)_1px,transparent_1px)] bg-[size:24px_24px]" />
            <svg
              className="relative h-[420px] w-full text-sky-300"
              viewBox="0 0 620 420"
              role="img"
              aria-label="LTspice circuit schematic preview"
            >
              <g fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2">
                <path d="M82 288V130h110" opacity="0.75" />
                <path d="M192 130h94M346 130h86M432 130v76h70" opacity="0.75" />
                <path d="M82 288h100v-64h82" opacity="0.75" />
                <path d="M346 224h86v-94M432 224v78" opacity="0.75" />
                <path d="M502 206v74" opacity="0.75" />
                <circle cx="82" cy="306" r="18" />
                <path d="M70 306h24M82 294v24" />
                <path d="M192 110v40M206 110v40M286 130h18m-9-18v36" />
                <path d="M304 130h42" />
                <path d="M346 110v40M360 110v40" />
                <path d="M432 104v52M420 104h24M420 156h24" />
                <path d="M264 224c12-28 58-28 70 0c-12 28-58 28-70 0Z" />
                <path d="M298 224h48M306 248l38 28M306 200l38-28" />
                <path d="M502 280h-32M494 292h-16M488 304h-4" />
                <path d="M432 302h-32M424 314h-16M418 326h-4" />
              </g>
              <g fill="currentColor" fontFamily="monospace" fontSize="14">
                <text x="108" y="312">V1 9V</text>
                <text x="180" y="92">C4 100nF</text>
                <text x="364" y="92">R2 4.7k</text>
                <text x="354" y="196">Q1 2N2222</text>
                <text x="512" y="212">Vout</text>
                <text x="454" y="126">L1 10uH</text>
              </g>
              <g fill="currentColor">
                {[82, 192, 304, 346, 432, 502].map((x, index) => (
                  <circle key={index} cx={x} cy={index < 4 ? 130 : index === 4 ? 224 : 206} r="3" />
                ))}
              </g>
            </svg>

            <div className="absolute bottom-4 left-4 right-4 grid gap-3 sm:grid-cols-3">
              {["Netlist clean", "Symbols mapped", "ASC ready"].map((item) => (
                <div
                  key={item}
                  className="rounded-md border border-sky-300/15 bg-[#050816]/95 px-3 py-2 text-xs font-medium text-slate-300"
                >
                  <span className="mr-2 text-sky-300">+</span>
                  {item}
                </div>
              ))}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}

function HeroIntro() {
  return (
    <section className="relative z-10 mx-auto grid min-h-screen w-full max-w-7xl items-center gap-14 px-4 pb-20 pt-28 sm:px-6 lg:grid-cols-[0.92fr_1.08fr] lg:px-8 lg:pt-32">
      <div className="max-w-2xl fade-up">
        <div className="inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-300/5 px-4 py-2 text-sm font-medium text-sky-200">
          <Bot className="h-4 w-4 text-sky-300" />
          AI-Powered Circuit Design
        </div>

        <h1 className="mt-8 text-5xl font-bold leading-[1.02] tracking-tight text-white sm:text-6xl lg:text-7xl">
          From <span className="text-sky-300">Prompt</span> to LTspice.
          <br />
          Build Circuits with <span className="text-sky-300">AI.</span>
        </h1>

        <p className="mt-6 max-w-xl text-lg leading-8 text-slate-400">
          Search real-world circuit designs, convert them into editable
          schematics, modify them with natural language, and export directly to
          LTspice.
        </p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href="/signup"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-400 px-6 py-3.5 text-sm font-semibold text-[#02040A] transition duration-200 hover:-translate-y-0.5 hover:bg-sky-300"
          >
            Start Building
            <Rocket className="h-4 w-4" />
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-white/12 bg-white/[0.03] px-6 py-3.5 text-sm font-semibold text-white transition duration-200 hover:-translate-y-0.5 hover:border-sky-300/35 hover:bg-white/[0.06]"
          >
            <PlayCircle className="h-4 w-4" />
            Watch Demo
          </Link>
        </div>

        <div className="mt-8 flex flex-wrap gap-3">
          {techPills.map((pill) => (
            <span
              key={pill}
              className="rounded-md border border-white/10 bg-[#050816] px-4 py-2 text-sm text-slate-300"
            >
              {pill}
            </span>
          ))}
        </div>
      </div>

      <div className="fade-up [animation-delay:120ms]">
        <ProductScreenshot />
      </div>
    </section>
  );
}

function WorkflowSection() {
  return (
    <section
      id="how-it-works"
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 lg:px-8"
    >
      <div className="section-surface p-6 sm:p-8">
        <SectionHeading
          title="How"
          highlight="SpiceCraft"
          description="A practical workflow that moves from search to simulation without forcing engineers to redraw everything by hand."
        />

        <div className="mt-10 grid gap-4 lg:grid-cols-4">
          {workflowSteps.map((step) => {
            const Icon = step.icon;
            return (
              <div key={step.number} className="engineering-card fade-up">
                <div className="flex items-center justify-between">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-sky-300/20 bg-sky-300/8 text-sky-300">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-sm font-semibold text-sky-300">
                    {step.number}
                  </span>
                </div>
                <h3 className="mt-5 text-xl font-semibold text-white">
                  {step.title}
                </h3>
                <p className="mt-3 text-sm leading-7 text-slate-400">
                  {step.description}
                </p>
                <div className="mt-5 rounded-lg border border-white/8 bg-black/20 px-4 py-3 text-sm text-slate-300">
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
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 lg:px-8"
    >
      <SectionHeading
        title="Why Engineers Love"
        highlight="SpiceCraft"
        description="The product experience stays grounded in real circuit workflows: discovery, understanding, editing, and export."
      />

      <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {featureCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.title} className="engineering-card fade-up">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg border border-sky-300/20 bg-sky-300/8 text-sky-300">
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="mt-5 text-2xl font-semibold text-white">
                {card.title}
              </h3>
              <p className="mt-3 text-sm leading-7 text-slate-400">
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
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 lg:px-8"
    >
      <div className="section-surface p-6 sm:p-8">
        <SectionHeading
          eyebrow="Built with Modern Tech"
          title="Production-ready foundations for"
          highlight="engineering workflows"
        />

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {techStack.map((item) => (
            <div
              key={item.title}
              className="rounded-lg border border-white/10 bg-[#050816] px-5 py-5 transition duration-200 hover:-translate-y-0.5 hover:border-sky-300/25"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
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
      className="relative z-10 mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 lg:px-8"
    >
      <SectionHeading
        eyebrow="Our Roadmap"
        title="Shipping toward a more capable"
        highlight="AI circuit workspace"
      />

      <div className="mt-10 grid gap-4 lg:grid-cols-5">
        {roadmapItems.map((item, index) => (
          <div key={item.version} className="engineering-card relative fade-up">
            {index < roadmapItems.length - 1 ? (
              <div className="absolute -right-2 top-1/2 hidden h-px w-4 bg-sky-300/30 lg:block" />
            ) : null}
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300/80">
              {item.version}
            </p>
            <h3 className="mt-4 text-xl font-semibold text-white">
              {item.title}
            </h3>
            <p className="mt-3 text-sm leading-7 text-slate-400">
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
    <section className="relative z-10 mx-auto w-full max-w-7xl px-4 pb-24 pt-12 sm:px-6 lg:px-8">
      <div className="section-surface relative overflow-hidden px-8 py-10 sm:px-10 lg:px-12">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_88%_20%,rgba(56,189,248,0.14),transparent_32%)]" />
        <div className="relative flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <h2 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
              Stop Drawing Circuits Manually.
              <br />
              <span className="text-sky-300">
                Search. Understand. Edit. Export.
              </span>
            </h2>
          </div>

          <Link
            href="/signup"
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-sky-400 px-6 py-3.5 text-sm font-semibold text-[#02040A] transition duration-200 hover:-translate-y-0.5 hover:bg-sky-300"
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
    <div className="relative overflow-hidden bg-[#02040A] text-white">
      <PageBackground />
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
