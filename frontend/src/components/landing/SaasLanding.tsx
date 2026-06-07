"use client";

import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  GitBranch,
  Layers,
  Shield,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

const fade = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

const features = [
  {
    icon: Workflow,
    title: "11-node DAG engine",
    desc: "Repository analysis, bug detection, patching, and validation as a directed acyclic graph with explicit dependencies.",
  },
  {
    icon: Zap,
    title: "Parallel batch execution",
    desc: "Topologically-sorted batches run independent nodes concurrently — bug_detection and repo_analysis in parallel.",
  },
  {
    icon: Shield,
    title: "Deterministic patching",
    desc: "Exact-match string replacement with verify-and-rollback. No LLM guesswork, no ast.unparse drift.",
  },
  {
    icon: Bot,
    title: "4 isolated subagents",
    desc: "BugHunter, RepoAnalyzer, PatchGenerator, and TestValidation agents run in copy-on-write workdirs.",
  },
  {
    icon: Layers,
    title: "Persistent memory",
    desc: "Cross-run learning via ~/.agira/memory_store.json — failures, successes, and repo profiles inform planning.",
  },
  {
    icon: GitBranch,
    title: "Self-healing DAG",
    desc: "4-way failure classification: deterministic, transient, dependency, escalate. Retries only when appropriate.",
  },
];

const steps = [
  { n: "01", title: "Upload repository", desc: "GitHub URL or local path. Agira copies to an isolated workdir." },
  { n: "02", title: "DAG executes", desc: "Planner proposes goals, scheduler runs parallel batches, state machine executes nodes." },
  { n: "03", title: "Issues merged & patched", desc: "Subagent findings merge. Deterministic apply_edit patches with verification." },
  { n: "04", title: "Validate & report", desc: "Tests run, health score computed, JSON + markdown reports generated." },
];

const wins = [
  { vs: "Traditional CI", point: "Reactive pass/fail — Agira proactively audits, repairs, and explains every node." },
  { vs: "LLM chat agents", point: "Non-deterministic patches and retry loops — Agira fails fast with classified recovery." },
  { vs: "Scripted pipelines", point: "Fixed workflows miss context — AdaptivePlanner reactively proposes 15 goals from artifacts." },
];

const dagNodes = [
  "repo_metadata",
  "file_list",
  "dependency_graph",
  "bug_detection ∥ repo_analysis",
  "merge_findings",
  "patch_generation ∥ validation",
  "health_score → report",
];

export function SaasLanding() {
  return (
    <div className="bg-background text-foreground">
      {/* Hero */}
      <section className="landing-glow landing-gradient relative overflow-hidden pt-28 pb-20 md:pt-36 md:pb-28">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(ellipse 70% 60% at 50% 0%, black, transparent)",
          }}
        />
        <div className="relative mx-auto max-w-6xl px-6 text-center">
          <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.1 } } }}>
            <motion.div variants={fade} className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-background/80 px-4 py-1.5 text-xs font-medium text-muted-foreground backdrop-blur">
              <Sparkles className="h-3.5 w-3.5" />
              Autonomous Repository Intelligence
            </motion.div>
            <motion.h1 variants={fade} className="text-4xl font-semibold tracking-tight md:text-6xl lg:text-7xl">
              Audit. Repair. Validate.
              <br />
              <span className="text-muted-foreground">Autonomously.</span>
            </motion.h1>
            <motion.p variants={fade} className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground md:text-xl">
              A deterministic 11-node DAG engine that analyzes repositories, detects bugs, generates verified patches, and produces auditable reports — without retry loops or hallucinated fixes.
            </motion.p>
            <motion.div variants={fade} className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Button asChild size="lg" className="rounded-full px-8">
                <Link href="/analysis">
                  Run your first analysis
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="rounded-full px-8">
                <Link href="#architecture">View architecture</Link>
              </Button>
            </motion.div>
            <motion.p variants={fade} className="mt-8 text-sm text-muted-foreground">
              Trusted by engineering teams shipping autonomous tooling · 71 registered tools · 4 subagents
            </motion.p>
          </motion.div>
        </div>
      </section>

      {/* Problem */}
      <section id="problem" className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">The problem</p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold tracking-tight md:text-4xl">
            CI is reactive. LLM agents are non-deterministic. Neither can autonomously repair a codebase.
          </h2>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {[
              "CI tools run after the fact — no planning, no memory, no repair.",
              "LLM agents hallucinate paths, retry forever, and produce irreproducible patches.",
              "Scripted pipelines can't adapt when dependencies fail or artifacts are missing.",
            ].map((text) => (
              <div key={text} className="rounded-2xl border border-border bg-muted/50 p-6 text-muted-foreground">
                {text}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Solution */}
      <section id="solution" className="border-t border-border bg-muted/30 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">The solution</p>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold tracking-tight md:text-4xl">
            Model software engineering as a DAG — execute deterministically, heal intelligently.
          </h2>
          <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
            Agira combines a reactive planner, parallel scheduler, failure classifier, and persistent memory into one orchestrator that runs to completion on every execution.
          </p>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Features</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">Built for production autonomous execution</h2>
          <div className="mt-14 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-border bg-background p-6 transition-colors hover:border-foreground/20 hover:bg-muted/30"
              >
                <f.icon className="mb-4 h-5 w-5 text-muted-foreground transition-colors group-hover:text-foreground" />
                <h3 className="font-semibold">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="border-t border-border bg-muted/30 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Architecture</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">11-node execution DAG</h2>
          <p className="mt-4 max-w-2xl text-muted-foreground">
            Nodes execute in dependency-respecting batches. Independent paths — like bug_detection and repo_analysis — run in parallel.
          </p>
          <div className="mt-12 rounded-2xl border border-border bg-background p-8 font-mono text-sm">
            {dagNodes.map((node, i) => (
              <div key={node} className="flex items-center gap-4 py-3">
                <span className="w-6 text-muted-foreground">{i + 1}</span>
                <span>{node}</span>
                {i < dagNodes.length - 1 && <span className="ml-auto text-muted-foreground">↓</span>}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">How it works</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">From upload to production report</h2>
          <div className="mt-14 grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((s) => (
              <div key={s.n}>
                <span className="text-4xl font-semibold text-muted-foreground/40">{s.n}</span>
                <h3 className="mt-4 font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Why It Wins */}
      <section id="why-agira" className="border-t border-border bg-muted/30 py-20 md:py-28">
        <div className="mx-auto max-w-6xl px-6">
          <p className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Why Agira wins</p>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">Not another chatbot. Not another linter.</h2>
          <div className="mt-12 space-y-6">
            {wins.map((w) => (
              <div key={w.vs} className="rounded-2xl border border-border bg-background p-6 md:flex md:items-center md:gap-8">
                <span className="shrink-0 text-sm font-medium text-muted-foreground">vs {w.vs}</span>
                <p className="mt-2 md:mt-0">{w.point}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-border py-20 md:py-28">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">
            Ship autonomous repository intelligence today.
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Run the full DAG on your codebase. Get patches, validation results, and an auditable execution timeline.
          </p>
          <Button asChild size="lg" className="mt-10 rounded-full px-10">
            <Link href="/analysis">
              Start Analysis
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-6 md:flex-row">
          <span className="font-semibold">Agira</span>
          <nav className="flex gap-6 text-sm text-muted-foreground">
            <Link href="/analysis" className="hover:text-foreground">Analysis</Link>
            <Link href="/history" className="hover:text-foreground">History</Link>
            <Link href="/settings" className="hover:text-foreground">Settings</Link>
          </nav>
          <p className="text-xs text-muted-foreground">Deterministic · Parallel · Self-Healing</p>
        </div>
      </footer>
    </div>
  );
}