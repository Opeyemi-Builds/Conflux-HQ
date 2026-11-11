"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import CastDetails from "./CastDetails";
import { ArrowDown, ArrowUpRight } from "lucide-react";

const VIDEO = "https://d2ol7oe51mr4n9.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/45567745-d826-44a2-a5ce-7ef670944e60.mp4";
const panels = [
  { label: "The payment incident workspace", title: ["Every complaint.", "A bigger picture."], text: "Bring customer reports, payment evidence, and the people who can act into one shared workspace.", href: "/dashboard", cta: "Explore Conflux" },
  { label: "From report to understanding", title: ["Follow the evidence.", "Find the next step."], text: "Connect related complaints. Compare payment records. See what the evidence supports and what your team still needs to check.", href: "/dashboard/complaints", cta: "Explore the reports" },
  { label: "From investigation to action", title: ["Give the fix", "a way forward."], text: "Assign responsibility, record the change, and review the evidence behind the outcome. Keep every handoff connected.", href: "/dashboard", cta: "Open your workspace" },
];
const cues = [[0, 0, .18, .29], [.34, .43, .61, .72], [.77, .87, 1.1, 1.2]];
const clamp = (value: number) => Math.max(0, Math.min(1, value));
const ramp = (value: number, start: number, end: number) => {
  const t = end === start ? Number(value >= end) : clamp((value - start) / (end - start));
  return t * t * (3 - 2 * t);
};

export default function CastLanding() {
  const root = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const panelRoot = useRef<HTMLDivElement>(null);
  const meter = useRef<HTMLDivElement>(null);
  const [chapter, setChapter] = useState(0);

  useEffect(() => {
    const clip = video.current!;
    const page = root.current!;
    const sections = Array.from(panelRoot.current!.querySelectorAll<HTMLElement>("[data-chapter]"));
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let target = 0;
    let current = 0;
    let duration = 0;
    let previousChapter = 0;

    const paint = () => {
      const bounds = page.getBoundingClientRect();
      const progress = clamp(-bounds.top / Math.max(1, page.offsetHeight - window.innerHeight));
      page.classList.toggle("cast-story-ended", bounds.bottom <= 0);
      page.classList.toggle("cast-story-finishing", bounds.bottom <= window.innerHeight);
      target = progress * Math.max(0, duration - .05);
      if (meter.current) meter.current.style.transform = `scaleX(${progress})`;
      let visibleChapter = previousChapter;
      sections.forEach((section, index) => {
        if (preference.matches) {
          section.style.opacity = "1";
          section.style.transform = "none";
          section.inert = false;
          section.removeAttribute("aria-hidden");
          return;
        }
        const [start, entered, leaving, end] = cues[index];
        const enter = ramp(progress, start, entered);
        const leave = ramp(progress, leaving, end);
        const opacity = bounds.bottom <= 0 ? 0 : enter * (1 - leave);
        section.style.opacity = String(opacity);
        section.style.transform = `translateY(${(1 - enter) * 22 - leave * 22}px)`;
        section.style.pointerEvents = opacity > .5 ? "auto" : "none";
        section.inert = opacity <= .5;
        section.setAttribute("aria-hidden", String(opacity <= .5));
        if (opacity > .5) visibleChapter = index;
      });
      if (visibleChapter !== previousChapter) {
        previousChapter = visibleChapter;
        setChapter(visibleChapter);
      }
      if (!preference.matches && !frame) frame = requestAnimationFrame(seek);
    };
    const seek = () => {
      frame = 0;
      if (preference.matches || !duration) return;
      current += (target - current) * .14;
      if (!clip.seeking && clip.readyState >= 2) clip.currentTime = current;
      if (Math.abs(target - current) > .025) frame = requestAnimationFrame(seek);
    };
    const metadata = () => {
      duration = Number.isFinite(clip.duration) ? clip.duration : 0;
      paint();
    };
    const loaded = () => { paint(); };
    const unlock = () => {
      if (preference.matches) return;
      void clip.play().then(() => { clip.pause(); paint(); }).catch(() => {});
    };
    clip.addEventListener("loadedmetadata", metadata);
    clip.addEventListener("loadeddata", loaded);
    window.addEventListener("scroll", paint, { passive: true });
    window.addEventListener("resize", paint);
    window.addEventListener("pointerdown", unlock, { once: true, passive: true });
    preference.addEventListener("change", paint);
    if (clip.readyState >= 1) metadata();
    paint();
    return () => {
      cancelAnimationFrame(frame);
      clip.pause();
      clip.removeEventListener("loadedmetadata", metadata);
      clip.removeEventListener("loadeddata", loaded);
      window.removeEventListener("scroll", paint);
      window.removeEventListener("resize", paint);
      window.removeEventListener("pointerdown", unlock);
      preference.removeEventListener("change", paint);
    };
  }, []);

  return <div className="cast-landing"><main><div className="cast-story" ref={root}>
    <div className="cast-stage" aria-hidden="true">
      <div className="cast-backdrop" />
      <video ref={video} src={VIDEO} muted playsInline preload="auto" disablePictureInPicture tabIndex={-1} />
      <div className="cast-veil" /><div className="cast-grain" />
    </div>
    <div className="cast-meter" ref={meter} aria-hidden="true" />
    <header className="cast-header">
      <Link className="cast-brand" href="/" aria-label="Conflux HQ home">
        <Image
          src="/conflux-logo-full.jpg"
          alt="Conflux HQ"
          width={32}
          height={32}
          className="cast-brand-logo"
          priority
        />
        <span>conflux<span className="cast-hq">HQ</span></span>
      </Link>
      <nav aria-label="Main navigation">
        <a href="#platform">The platform</a>
        <a href="#workflow">The workflow</a>
        <Link href="/developers">Developers</Link>
        <Link className="cast-pill" href="/login">Sign in <ArrowUpRight size={14} /></Link>
      </nav>
    </header>
    <div className="cast-panels" ref={panelRoot}>
      {panels.map((panel, index) => <section key={panel.label} data-chapter={index} className="cast-panel">
        <p className="cast-eyebrow"><span />{panel.label}</p>
        {index === 0 ? <h1>{panel.title.map((line) => <span key={line}>{line}</span>)}</h1>
          : <h2>{panel.title.map((line) => <span key={line}>{line}</span>)}</h2>}
        <p className="cast-subtitle">{panel.text}</p>
        <Link className="cast-pill cast-primary" href={panel.href}>{panel.cta}<ArrowUpRight size={17} /></Link>
      </section>)}
    </div>
    <div className="cast-track" aria-hidden="true"><div id="cast-reports" /><div id="cast-actions" /></div>
    <aside className="cast-chapters" aria-label="Page chapters">
      {["The picture", "The evidence", "The next step"].map((label, index) => (
        <a key={label} href={index === 0 ? "#" : index === 1 ? "#cast-reports" : "#cast-actions"}
          aria-current={chapter === index ? "step" : undefined}><span>0{index + 1}</span>{label}</a>
      ))}
    </aside>
    <div className="cast-footer"><span>Bank operations, brought together.</span><span className="cast-scroll">Scroll to explore <ArrowDown size={13} /></span><span>Synthetic demo available</span></div>
  </div><CastDetails /></main></div>;
}
