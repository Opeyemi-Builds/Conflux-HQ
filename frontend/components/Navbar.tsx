"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Menu, X } from "lucide-react";

const links = [
  { label: "Platform", href: "#platform" },
  { label: "Workflow", href: "#workflow" },
  { label: "Your team", href: "#teams" },
  { label: "FAQ", href: "#faq" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState("");
  const [hovered, setHovered] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    const scroll = () => setScrolled(window.scrollY > 24);
    scroll();
    window.addEventListener("scroll", scroll, { passive: true });
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) setActive("#" + entry.target.id);
      }
    }, { rootMargin: "-15% 0px -55% 0px" });
    for (const link of links) {
      const section = document.querySelector(link.href);
      if (section) observer.observe(section);
    }
    return () => {
      window.removeEventListener("scroll", scroll);
      observer.disconnect();
    };
  }, []);

  return <header className="conflux-nav-wrap" onKeyDown={(event) => {
    if (event.key === "Escape") {
      setOpen(false);
      document.getElementById("landing-menu-toggle")?.focus();
    }
  }}>
    <motion.div initial={reduced ? false : { opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
      className={`conflux-nav ${scrolled ? "is-scrolled" : ""}`}>
      <Link className="landing-brand" href="/" aria-label="Conflux HQ home">
        <span className="brand-mark overflow-hidden">
          <Image
            src="/conflux-logo-full.jpg"
            alt="Conflux HQ"
            width={30}
            height={30}
            className="rounded-md object-contain"
            priority
          />
        </span>
        conflux<span className="brand-hq">HQ</span>
      </Link>
      <nav className="landing-desktop-nav" aria-label="Main navigation" onMouseLeave={() => setHovered("")}>
        {links.map((link) => <a key={link.href} href={link.href}
          onMouseEnter={() => setHovered(link.href)}
          onFocus={() => setHovered(link.href)} onBlur={() => setHovered("")}
          aria-current={active === link.href ? "location" : undefined}>
          {(hovered || active) === link.href && <motion.span className="nav-highlight"
            layoutId="landing-nav-highlight" transition={{ duration: reduced ? 0 : 0.25, ease: "easeOut" }} />}
          <span>{link.label}</span>
        </a>)}
      </nav>
      <div className="nav-actions">
        <Link className="nav-signin" href="/login">Sign in</Link>
        <Link className="nav-cta" href="/dashboard">Open workspace <ArrowUpRight size={15} /></Link>
        <button id="landing-menu-toggle" className="landing-menu-toggle" type="button"
          aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open}
          aria-controls="landing-mobile-menu" onClick={() => setOpen(!open)}>
          {open ? <X size={21} /> : <Menu size={21} />}
        </button>
      </div>
    </motion.div>
    <AnimatePresence>
      {open && <motion.nav id="landing-mobile-menu" className="landing-mobile-nav" aria-label="Mobile navigation"
        initial={reduced ? false : { opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
        exit={{ opacity: 0, height: 0 }} transition={{ duration: reduced ? 0 : 0.25 }}>
        {links.map((link, index) => <motion.a key={link.href} href={link.href} onClick={() => setOpen(false)}
          initial={reduced ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
          transition={{ delay: reduced ? 0 : index * 0.04 }}>{link.label}<ArrowUpRight size={16} /></motion.a>)}
        <Link href="/login" onClick={() => setOpen(false)}>Sign in <ArrowUpRight size={16} /></Link>
      </motion.nav>}
    </AnimatePresence>
  </header>;
}
