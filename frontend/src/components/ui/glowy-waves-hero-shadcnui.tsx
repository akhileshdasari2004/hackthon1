"use client";

import { motion, type Variants } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";

type Point = {
  x: number;
  y: number;
};

interface WaveConfig {
  offset: number;
  amplitude: number;
  frequency: number;
  color: string;
  opacity: number;
}

const highlightPills = ["Autonomous audit", "Deterministic repair", "Full validation"] as const;

const heroStats: { label: string; value: string }[] = [
  { label: "Workflow nodes", value: "11" },
  { label: "Autonomous agents", value: "4" },
  { label: "Hidden failures", value: "0" },
];

const containerVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.8, staggerChildren: 0.12 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.25, 0.1, 0.25, 1] },
  },
};

const statsVariants: Variants = {
  hidden: { opacity: 0, scale: 0.98 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: 0.6, ease: [0.25, 0.1, 0.25, 1], staggerChildren: 0.08 },
  },
};

export function GlowyWavesHero() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const mouseRef = useRef<Point>({ x: 0, y: 0 });
  const targetMouseRef = useRef<Point>({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;

    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    let animationId: number;
    let time = 0;

    const wavePalette: WaveConfig[] = [
      { offset: 0, amplitude: 48, frequency: 0.003, color: "rgba(0, 0, 0, 0.06)", opacity: 0.5 },
      { offset: Math.PI / 2, amplitude: 56, frequency: 0.0026, color: "rgba(110, 110, 115, 0.08)", opacity: 0.4 },
      { offset: Math.PI, amplitude: 40, frequency: 0.0034, color: "rgba(0, 0, 0, 0.04)", opacity: 0.35 },
      { offset: Math.PI * 1.5, amplitude: 52, frequency: 0.0022, color: "rgba(110, 110, 115, 0.06)", opacity: 0.3 },
      { offset: Math.PI * 2, amplitude: 36, frequency: 0.004, color: "rgba(0, 0, 0, 0.03)", opacity: 0.25 },
    ];

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mouseInfluence = prefersReducedMotion ? 6 : 32;
    const influenceRadius = prefersReducedMotion ? 140 : 280;
    const smoothing = prefersReducedMotion ? 0.04 : 0.08;

    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const recenterMouse = () => {
      const centerPoint = { x: canvas.width / 2, y: canvas.height / 2 };
      mouseRef.current = centerPoint;
      targetMouseRef.current = centerPoint;
    };

    const handleResize = () => {
      resizeCanvas();
      recenterMouse();
    };

    const handleMouseMove = (event: MouseEvent) => {
      targetMouseRef.current = { x: event.clientX, y: event.clientY };
    };

    const handleMouseLeave = () => {
      recenterMouse();
    };

    resizeCanvas();
    recenterMouse();

    window.addEventListener("resize", handleResize);
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseleave", handleMouseLeave);

    const drawWave = (wave: WaveConfig) => {
      ctx.save();
      ctx.beginPath();

      for (let x = 0; x <= canvas.width; x += 4) {
        const dx = x - mouseRef.current.x;
        const dy = canvas.height / 2 - mouseRef.current.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const influence = Math.max(0, 1 - distance / influenceRadius);
        const mouseEffect =
          influence * mouseInfluence * Math.sin(time * 0.001 + x * 0.01 + wave.offset);

        const y =
          canvas.height / 2 +
          Math.sin(x * wave.frequency + time * 0.002 + wave.offset) * wave.amplitude +
          Math.sin(x * wave.frequency * 0.4 + time * 0.003) * (wave.amplitude * 0.45) +
          mouseEffect;

        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }

      ctx.lineWidth = 1.5;
      ctx.strokeStyle = wave.color;
      ctx.globalAlpha = wave.opacity;
      ctx.stroke();
      ctx.restore();
    };

    const animate = () => {
      time += 1;

      mouseRef.current.x += (targetMouseRef.current.x - mouseRef.current.x) * smoothing;
      mouseRef.current.y += (targetMouseRef.current.y - mouseRef.current.y) * smoothing;

      const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
      gradient.addColorStop(0, "#ffffff");
      gradient.addColorStop(1, "#f5f5f7");

      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalAlpha = 1;

      wavePalette.forEach(drawWave);

      animationId = window.requestAnimationFrame(animate);
    };

    animationId = window.requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseleave", handleMouseLeave);
      cancelAnimationFrame(animationId);
    };
  }, []);

  return (
    <section
      className="relative isolate flex min-h-screen w-full items-center justify-center overflow-hidden bg-white"
      role="region"
      aria-label="Agira hero"
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" aria-hidden="true" />

      <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center px-6 py-24 text-center md:px-8 lg:px-12">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="w-full"
        >
          <motion.p
            variants={itemVariants}
            className="mb-6 text-sm font-medium tracking-[0.2em] text-[#6E6E73] uppercase"
          >
            The Autonomous Software Engineer
          </motion.p>

          <motion.h1
            variants={itemVariants}
            className="mb-6 text-[clamp(3.5rem,10vw,7.5rem)] leading-[0.95] font-semibold tracking-[-0.04em] text-black"
          >
            Meet Agira.
          </motion.h1>

          <motion.p
            variants={itemVariants}
            className="mx-auto mb-10 max-w-2xl text-[clamp(1.125rem,2.5vw,1.5rem)] leading-relaxed text-[#6E6E73]"
          >
            The first autonomous software engineer that understands, repairs,
            validates and improves entire codebases.
          </motion.p>

          <motion.div
            variants={itemVariants}
            className="mb-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
          >
            <Button
              asChild
              size="lg"
              className="h-12 rounded-full bg-black px-8 text-[15px] font-medium hover:bg-neutral-800"
            >
              <Link href="/analysis" className="group gap-2">
                Start Analysis
                <ArrowRight
                  className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="h-12 rounded-full border-[#E5E5E7] bg-white px-8 text-[15px] font-medium text-black hover:bg-[#F5F5F7]"
            >
              <Link href="#demo">Watch Demo</Link>
            </Button>
          </motion.div>

          <motion.ul
            variants={itemVariants}
            className="mb-12 flex flex-wrap items-center justify-center gap-3"
          >
            {highlightPills.map((pill) => (
              <li
                key={pill}
                className="rounded-full border border-[#E5E5E7] bg-white px-4 py-2 text-xs font-medium tracking-wide text-[#6E6E73]"
              >
                {pill}
              </li>
            ))}
          </motion.ul>

          <motion.div
            variants={statsVariants}
            className="mx-auto grid max-w-2xl gap-8 sm:grid-cols-3"
          >
            {heroStats.map((stat) => (
              <motion.div key={stat.label} variants={itemVariants} className="space-y-1">
                <div className="text-xs font-medium tracking-[0.15em] text-[#6E6E73] uppercase">
                  {stat.label}
                </div>
                <div className="text-3xl font-semibold tracking-tight text-black">
                  {stat.value}
                </div>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.8 }}
        className="absolute bottom-12 left-1/2 z-10 -translate-x-1/2"
      >
        <motion.div
          animate={{ y: [0, 6, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          className="h-10 w-px bg-[#E5E5E7]"
        />
      </motion.div>
    </section>
  );
}
