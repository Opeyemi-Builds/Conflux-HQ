"use client";

import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  SlidersHorizontal,
  Search,
  X,
  Radio,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { useDash } from "./Provider";

export type RiskLevel = "all" | "critical" | "high" | "medium" | "low";

export interface GeoComplaint {
  id: string;
  city: string;
  state: string;
  zone: string;
  lat: number;
  lng: number;
  risk: "critical" | "high" | "medium" | "low";
  issue: string;
  amount: string;
  channel: "USSD" | "Mobile App" | "POS" | "ATM" | "Web";
  time: string;
  summary: string;
  status: "active" | "investigating" | "quarantined";
}

// Projection: Longitude (2.4 -> 14.9), Latitude (4.0 -> 14.1) mapped to (1000 x 750)
function project(lng: number, lat: number) {
  const minLng = 2.4;
  const maxLng = 14.9;
  const minLat = 4.0;
  const maxLat = 14.1;
  const x = ((lng - minLng) / (maxLng - minLng)) * 1000;
  const y = ((maxLat - lat) / (maxLat - minLat)) * 750;
  return { x, y };
}

// Major Nigerian cities and geographic reference anchors
const cityHubs = [
  { name: "Lagos / VI / Ikeja", state: "Lagos", lat: 6.52, lng: 3.38, complaints: 482, risk: "critical", amount: "₦28.4M", trend: "+640% spike" },
  { name: "Abuja FCT", state: "FCT", lat: 9.07, lng: 7.40, complaints: 194, risk: "high", amount: "₦8.9M", trend: "+180% surge" },
  { name: "Ibadan", state: "Oyo", lat: 7.38, lng: 3.95, complaints: 112, risk: "high", amount: "₦4.2M", trend: "+95% rise" },
  { name: "Kano", state: "Kano", lat: 12.00, lng: 8.59, complaints: 98, risk: "high", amount: "₦3.7M", trend: "+60% rise" },
  { name: "Port Harcourt", state: "Rivers", lat: 4.82, lng: 7.05, complaints: 88, risk: "critical", amount: "₦4.6M", trend: "+120% surge" },
  { name: "Benin City", state: "Edo", lat: 6.34, lng: 5.62, complaints: 54, risk: "medium", amount: "₦1.8M", trend: "steady" },
  { name: "Enugu", state: "Enugu", lat: 6.45, lng: 7.54, complaints: 46, risk: "medium", amount: "₦1.4M", trend: "+15% rise" },
  { name: "Onitsha / Aba", state: "Anambra", lat: 6.15, lng: 6.78, complaints: 62, risk: "critical", amount: "₦3.1M", trend: "+85% spike" },
  { name: "Kaduna", state: "Kaduna", lat: 10.51, lng: 7.41, complaints: 48, risk: "medium", amount: "₦1.5M", trend: "steady" },
  { name: "Warri / Asaba", state: "Delta", lat: 5.52, lng: 5.75, complaints: 52, risk: "high", amount: "₦2.3M", trend: "+45% rise" },
  { name: "Jos", state: "Plateau", lat: 9.90, lng: 8.86, complaints: 28, risk: "low", amount: "₦850K", trend: "normal" },
  { name: "Ilorin", state: "Kwara", lat: 8.48, lng: 4.54, complaints: 32, risk: "medium", amount: "₦920K", trend: "normal" },
  { name: "Abeokuta", state: "Ogun", lat: 7.15, lng: 3.34, complaints: 44, risk: "high", amount: "₦1.6M", trend: "+75% rise" },
  { name: "Maiduguri", state: "Borno", lat: 11.83, lng: 13.15, complaints: 26, risk: "medium", amount: "₦780K", trend: "normal" },
  { name: "Sokoto", state: "Sokoto", lat: 13.06, lng: 5.23, complaints: 22, risk: "low", amount: "₦640K", trend: "normal" },
  { name: "Calabar", state: "Cross River", lat: 4.95, lng: 8.32, complaints: 24, risk: "low", amount: "₦710K", trend: "normal" },
];

// Seeded pseudorandom clustered complaint points across Nigeria
function generateGeoComplaints(): GeoComplaint[] {
  const points: GeoComplaint[] = [];
  const channels: Array<"USSD" | "Mobile App" | "POS" | "ATM" | "Web"> = ["USSD", "Mobile App", "POS", "ATM", "Web"];
  const quotes = [
    "Money debited via USSD to Access Bank but beneficiary never received credit!",
    "My money don enter voicemail! Debited twice at Ikeja supermarket.",
    "ATM swallowed ₦40,000 cash and deducted my balance without cash dispensing.",
    "Abeg reverse my ₦150,000 transfer, switch timeout on app since 10:12am.",
    "POS transaction failed at fuel station but SMS debit alert immediately arrived.",
    "Multiple debits of ₦50,000 each on USSD *901#, money hanging on switch.",
    "Fake alert received, suspicious OTP request detected and flagged.",
    "Failed transfer to Zenith Bank, customer service line busy for 40 mins.",
  ];

  let seed = 42;
  const pseudo = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };

  cityHubs.forEach((hub, hIdx) => {
    const dotCount = Math.min(Math.round(hub.complaints / 1.6), 180);
    for (let i = 0; i < dotCount; i++) {
      const radius = pseudo() * (hub.state === "Lagos" ? 0.38 : hub.state === "FCT" ? 0.45 : 0.6);
      const angle = pseudo() * Math.PI * 2;
      const lat = hub.lat + Math.sin(angle) * radius;
      const lng = hub.lng + Math.cos(angle) * radius;

      // Deterministic risk distribution
      const rVal = pseudo();
      let risk: "critical" | "high" | "medium" | "low" = "low";
      if (hub.risk === "critical") {
        risk = rVal < 0.55 ? "critical" : rVal < 0.85 ? "high" : "medium";
      } else if (hub.risk === "high") {
        risk = rVal < 0.25 ? "critical" : rVal < 0.65 ? "high" : "medium";
      } else {
        risk = rVal < 0.15 ? "high" : rVal < 0.5 ? "medium" : "low";
      }

      const amounts = ["₦15,000", "₦35,000", "₦50,000", "₦85,000", "₦120,000", "₦250,000", "₦500,000"];
      const amount = amounts[Math.floor(pseudo() * amounts.length)];
      const channel = channels[Math.floor(pseudo() * channels.length)];
      const summary = quotes[Math.floor(pseudo() * quotes.length)];
      const minute = String(10 + Math.floor(pseudo() * 45)).padStart(2, "0");

      points.push({
        id: `GEO-${hIdx}-${i}`,
        city: hub.name,
        state: hub.state,
        zone: hub.state === "Lagos" || hub.state === "Oyo" || hub.state === "Ogun" ? "South-West" : hub.state === "FCT" || hub.state === "Plateau" || hub.state === "Kwara" ? "North-Central" : hub.state === "Rivers" || hub.state === "Edo" || hub.state === "Delta" || hub.state === "Cross River" ? "South-South" : hub.state === "Kano" || hub.state === "Kaduna" || hub.state === "Sokoto" ? "North-West" : "South-East",
        lat,
        lng,
        risk,
        issue: risk === "critical" ? "Switch Reversal Failure" : risk === "high" ? "USSD Failed Transfer" : risk === "medium" ? "POS / ATM Dispense Trap" : "Account Fee Discrepancy",
        amount,
        channel,
        time: `10:${minute}`,
        summary,
        status: risk === "critical" ? "active" : risk === "high" ? "investigating" : "quarantined",
      });
    }
  });

  return points;
}

const geoComplaintsData = generateGeoComplaints();

export default function NigeriaRiskMap() {
  const [selectedRisk, setSelectedRisk] = useState<RiskLevel>("all");
  const [selectedChannel, setSelectedChannel] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activePoint, setActivePoint] = useState<GeoComplaint | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [showExecutiveBrief, setShowExecutiveBrief] = useState(true);

  // Filtered dots
  const filteredPoints = useMemo(() => {
    return geoComplaintsData.filter((p) => {
      const matchRisk = selectedRisk === "all" || p.risk === selectedRisk;
      const matchChannel = selectedChannel === "all" || p.channel === selectedChannel;
      const matchSearch =
        !searchQuery ||
        p.city.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.state.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.issue.toLowerCase().includes(searchQuery.toLowerCase());
      return matchRisk && matchChannel && matchSearch;
    });
  }, [selectedRisk, selectedChannel, searchQuery]);

  // Regional metrics calculation
  const { summary } = useDash();
  const totalMoneyAtRisk = summary?.money_at_risk
    ? `₦${(Number(summary.money_at_risk) / 1000000).toFixed(2)}M`
    : "₦48.25M";
  const criticalCount = geoComplaintsData.filter((p) => p.risk === "critical").length;
  const highCount = geoComplaintsData.filter((p) => p.risk === "high").length;
  const lagosPercentage = "64.2%";

  // Color mapping matching reference image
  const getDotColor = (risk: GeoComplaint["risk"]) => {
    switch (risk) {
      case "critical":
        return "#DC2626"; // Crimson Red
      case "high":
        return "#E8651A"; // Brand Flame Orange
      case "medium":
        return "#8B5CF6"; // Violet/Purple
      case "low":
        return "#10B981"; // Emerald/Teal
    }
  };

  return (
    <div id="geo-risk-map" className="rounded-3xl bg-white border border-navy/[0.08] shadow-sm overflow-hidden flex flex-col mb-6">
      {/* Top Header Bar */}
      <div className="px-6 py-5 border-b border-navy/[0.06] flex flex-wrap items-center justify-between gap-4 bg-[#FAFBF8]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping" />
            <span className="text-xs uppercase font-bold tracking-wider text-flux">National Geospatial Intelligence</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-navy">
            Nigeria Complaint &amp; Financial Threat Map
          </h2>
          <p className="text-sm text-navy/60">
            Real-time multi-channel incident density across all 36 States + FCT.
          </p>
        </div>

        {/* Quick Filter Pills & Search */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-navy/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search state / city..."
              className="text-xs pl-8 pr-3 py-1.5 rounded-full bg-white border border-navy/15 text-navy outline-none focus:border-flux w-40 md:w-48"
            />
          </div>

          {/* Channel Dropdown */}
          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="text-xs px-3 py-1.5 rounded-full bg-white border border-navy/15 text-navy outline-none focus:border-flux"
          >
            <option value="all">All Channels</option>
            <option value="USSD">USSD (*901#)</option>
            <option value="Mobile App">Mobile App</option>
            <option value="POS">POS Terminal</option>
            <option value="ATM">ATM Dispense</option>
          </select>

          {(
            [
              ["all", "All (" + geoComplaintsData.length + ")"],
              ["critical", "Critical (" + criticalCount + ")", "text-red-700 bg-red-50 border-red-200"],
              ["high", "High Spike (" + highCount + ")", "text-orange-700 bg-orange-50 border-orange-200"],
              ["medium", "Medium", "text-purple-700 bg-purple-50 border-purple-200"],
              ["low", "Normal", "text-emerald-700 bg-emerald-50 border-emerald-200"],
            ] as const
          ).map(([r, label, customClass]) => {
            const isSelected = selectedRisk === r;
            return (
              <button
                key={r}
                onClick={() => setSelectedRisk(r)}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full transition-all border ${
                  isSelected
                    ? "bg-navy text-white border-navy shadow-sm"
                    : customClass || "bg-white text-navy/70 border-navy/15 hover:bg-navy/5"
                }`}
              >
                {label}
              </button>
            );
          })}

          <div className="hidden xl:flex items-center gap-2 pl-2 border-l border-navy/10 text-xs">
            <span className="text-navy/50">Capital at Risk:</span>
            <span className="font-bold text-red-700">{totalMoneyAtRisk}</span>
            <span className="text-navy/40">({lagosPercentage} Lagos)</span>
          </div>
        </div>
      </div>

      {/* Main Map Container */}
      <div className="relative w-full h-[540px] md:h-[620px] bg-[#EBEAE3] overflow-hidden select-none">
        {/* Ocean Background / Water Label */}
        <div className="absolute bottom-0 left-0 right-0 h-44 bg-[#C9E4E8]/60 pointer-events-none border-t border-[#A2D2DA]">
          <span className="absolute bottom-4 left-8 text-xs font-semibold uppercase tracking-widest text-[#4A7D87]/70 italic">
            Gulf of Guinea · Atlantic Ocean
          </span>
        </div>

        {/* Surrounding Neighbor Labels */}
        <div className="absolute top-10 left-6 text-xs font-bold tracking-wider text-navy/40 uppercase pointer-events-none">
          Bénin Republic (Niamey / Cotonou)
        </div>
        <div className="absolute top-6 left-1/2 -translate-x-1/2 text-xs font-bold tracking-wider text-navy/40 uppercase pointer-events-none">
          Niger Republic (Zinder / Maradi)
        </div>
        <div className="absolute top-12 right-10 text-xs font-bold tracking-wider text-navy/40 uppercase pointer-events-none">
          Tchad (N&apos;Djamena)
        </div>
        <div className="absolute bottom-28 right-8 text-xs font-bold tracking-wider text-navy/40 uppercase pointer-events-none">
          Cameroun (Garoua / Bamenda)
        </div>

        {/* Map SVG Canvas */}
        <motion.div
          className="w-full h-full cursor-grab active:cursor-grabbing"
          animate={{ scale: zoomLevel }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        >
          <svg
            viewBox="0 0 1000 750"
            className="w-full h-full object-contain"
            preserveAspectRatio="xMidYMid meet"
          >
            <defs>
              {/* Hotspot Radial Glow */}
              <radialGradient id="lagosGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#DC2626" stopOpacity="0.45" />
                <stop offset="60%" stopColor="#DC2626" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#DC2626" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="phGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#E8651A" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#E8651A" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Nigeria Mainland Polygon Fill */}
            <path
              d="M 38 570 L 82 570 L 152 587 L 192 613 L 216 639 L 256 665 L 292 705 L 308 728 L 348 716 L 380 720 L 412 713 L 448 705 L 492 694 L 504 639 L 520 605 L 540 552 L 568 527 L 606 509 L 648 535 L 700 550 L 728 502 L 760 453 L 800 401 L 832 349 L 864 297 L 896 260 L 912 193 L 952 133 L 960 89 L 944 67 L 888 59 L 832 63 L 792 56 L 728 74 L 632 67 L 568 85 L 504 74 L 472 63 L 432 74 L 388 70 L 328 48 L 280 33 L 232 22 L 192 48 L 144 108 L 100 182 L 104 227 L 92 316 L 108 368 L 84 390 L 76 409 L 56 446 L 28 491 L 24 535 Z"
              fill="#F4F3EE"
              stroke="#B3B0A3"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />

            {/* State Grid & Regional Lines (Subtle cartographic vectors) */}
            <g stroke="#CFCBC0" strokeWidth="1" strokeDasharray="3 3" fill="none">
              {/* North-South dividing lines */}
              <path d="M 400 70 L 380 720" />
              <path d="M 600 70 L 520 605" />
              <path d="M 232 22 L 216 639" />
              {/* East-West dividing lines */}
              <path d="M 76 409 L 896 260" />
              <path d="M 56 446 L 700 550" />
            </g>

            {/* River Niger & Benue Confluence Vector */}
            <path
              d="M 100 182 Q 220 320, 360 420 L 390 460 Q 370 540, 292 705 M 896 260 Q 640 400, 390 460"
              fill="none"
              stroke="#B8DBE0"
              strokeWidth="3.5"
              strokeLinecap="round"
            />

            {/* Live Hotspot Pulsing Rings */}
            {/* Lagos Hotspot (INC-0421 Epicenter) */}
            <circle cx="82" cy="570" r="75" fill="url(#lagosGlow)" />
            <circle cx="82" cy="570" r="42" fill="none" stroke="#DC2626" strokeWidth="1.5" className="animate-ping" style={{ transformOrigin: "82px 570px", animationDuration: "2.4s" }} />

            {/* Port Harcourt Hotspot */}
            <circle cx="372" cy="689" r="45" fill="url(#phGlow)" />

            {/* Abuja Hotspot */}
            <circle cx="400" cy="373" r="40" fill="url(#phGlow)" />

            {/* Clustered Threat & Complaint Dots */}
            {filteredPoints.map((point) => {
              const { x, y } = project(point.lng, point.lat);
              const isSelected = activePoint?.id === point.id;
              const color = getDotColor(point.risk);

              return (
                <g key={point.id} onClick={() => setActivePoint(point)} className="cursor-pointer group">
                  {/* Subtle outer glow on hover */}
                  <circle
                    cx={x}
                    cy={y}
                    r={isSelected ? 9 : 4.5}
                    fill={color}
                    fillOpacity={isSelected ? 1 : 0.82}
                    stroke="#FFFFFF"
                    strokeWidth={isSelected ? 2.5 : 0.8}
                    className="transition-transform duration-150 hover:scale-150"
                  />
                </g>
              );
            })}

            {/* Prominent City Labels */}
            {cityHubs.map((city) => {
              const { x, y } = project(city.lng, city.lat);
              return (
                <g key={city.name} pointerEvents="none">
                  <circle cx={x} cy={y} r="3" fill="#14233F" />
                  <text
                    x={x + 7}
                    y={y + 4}
                    fill="#14233F"
                    fontSize="11"
                    fontWeight="700"
                    fontFamily="inherit"
                    className="select-none"
                    style={{ textShadow: "0 1px 3px rgba(255,255,255,0.9)" }}
                  >
                    {city.name.split("/")[0].trim()}
                  </text>
                </g>
              );
            })}
          </svg>
        </motion.div>

        {/* Map Control Buttons (Zoom / Reset / Hotspot center) */}
        <div className="absolute bottom-5 right-5 flex flex-col gap-2 z-10">
          <button
            onClick={() => setZoomLevel((z) => Math.min(z + 0.3, 2.5))}
            className="w-10 h-10 rounded-xl bg-white/95 backdrop-blur shadow-md border border-navy/10 flex items-center justify-center text-navy hover:bg-white transition-colors"
            title="Zoom In"
            aria-label="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.max(z - 0.3, 0.9))}
            className="w-10 h-10 rounded-xl bg-white/95 backdrop-blur shadow-md border border-navy/10 flex items-center justify-center text-navy hover:bg-white transition-colors"
            title="Zoom Out"
            aria-label="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setZoomLevel(1);
              setActivePoint(null);
            }}
            className="w-10 h-10 rounded-xl bg-white/95 backdrop-blur shadow-md border border-navy/10 flex items-center justify-center text-navy hover:bg-white transition-colors"
            title="Reset View"
            aria-label="Reset View"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>

        {/* Legend Overlay at Bottom-Left */}
        <div className="absolute bottom-5 left-5 bg-white/90 backdrop-blur-md border border-navy/10 rounded-2xl p-3 shadow-md z-10 flex flex-wrap items-center gap-3 text-xs text-navy/80">
          <span className="font-semibold text-navy">Threat Severity:</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#DC2626]" /> Critical (₦500k+ / Reversals)</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#E8651A]" /> High (USSD Spikes)</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#8B5CF6]" /> Medium (POS/ATM Traps)</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-[#10B981]" /> Low (Inquiries)</span>
        </div>

        {/* Selected Dot Interactive Tooltip HUD */}
        <AnimatePresence>
          {activePoint && (
            <motion.div
              initial={{ opacity: 0, y: 15, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              className="absolute top-6 right-6 w-80 md:w-96 rounded-2xl bg-white/95 backdrop-blur-xl border border-navy/15 p-5 shadow-2xl z-20"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: getDotColor(activePoint.risk) }}
                  />
                  <div>
                    <h4 className="font-bold text-navy text-base leading-tight">
                      {activePoint.city}
                    </h4>
                    <p className="text-xs text-navy/55">{activePoint.zone} · Ref {activePoint.id}</p>
                  </div>
                </div>
                <button
                  onClick={() => setActivePoint(null)}
                  className="text-navy/40 hover:text-navy p-1 rounded-lg"
                  aria-label="Close details"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="bg-navy/5 rounded-xl p-3 mb-3">
                <div className="flex items-center justify-between text-xs text-navy/60 mb-1">
                  <span>Channel: <b>{activePoint.channel}</b></span>
                  <span>Flagged at: <b>{activePoint.time}</b></span>
                </div>
                <div className="text-xs font-semibold text-navy mb-1">{activePoint.issue}</div>
                <p className="text-xs text-navy/75 italic leading-relaxed">
                  &ldquo;{activePoint.summary}&rdquo;
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 text-center mb-3">
                <div className="rounded-xl bg-red-50 border border-red-100 py-2">
                  <p className="text-[11px] font-medium text-red-600">Disputed Amount</p>
                  <p className="text-base font-bold text-red-700">{activePoint.amount}</p>
                </div>
                <div className="rounded-xl bg-navy/5 border border-navy/10 py-2">
                  <p className="text-[11px] font-medium text-navy/60">Risk Classification</p>
                  <p className="text-base font-bold text-navy capitalize">{activePoint.risk}</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  href="/dashboard/incidents/INC-0421"
                  className="flex-1 text-center py-2 px-3 rounded-xl bg-navy text-white text-xs font-semibold hover:bg-navy-600 transition-colors flex items-center justify-center gap-1.5"
                >
                  Investigate Switch Log <ExternalLink className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/dashboard/complaints"
                  className="py-2 px-3 rounded-xl border border-navy/15 text-navy text-xs font-semibold hover:bg-navy/5 transition-colors"
                >
                  View Feed
                </Link>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Bank Leadership Briefing & Regional Hotspot Analysis */}
      <div className="p-6 bg-white border-t border-navy/[0.06]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold text-navy/50 uppercase tracking-wider mb-1">
              <Radio className="w-3.5 h-3.5 text-flux" />
              Executive Bank Briefing · Geospatial Risk Synthesis
            </div>
            <h3 className="text-lg font-bold text-navy">
              Top At-Risk Banking Corridors &amp; Exposure
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-navy/55">Showing {filteredPoints.length} active complaints geocoded across Nigeria</span>
            <button
              onClick={() => setShowExecutiveBrief((s) => !s)}
              className="text-xs font-medium text-flux hover:underline flex items-center gap-1"
            >
              <SlidersHorizontal className="w-3 h-3" />
              {showExecutiveBrief ? "Collapse Summary" : "Expand Summary"}
            </button>
          </div>
        </div>

        {showExecutiveBrief && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Lagos Hub */}
            <div className="rounded-2xl border border-red-200 bg-red-50/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-red-700">South-West Epicenter</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-800">Critical</span>
              </div>
              <p className="text-lg font-bold text-navy">Lagos State Corridor</p>
              <p className="text-xs text-navy/60 mb-2">Ikeja, VI, Lekki, Mainland (482 complaints)</p>
              <div className="border-t border-red-200/60 pt-2 flex items-center justify-between text-xs font-semibold">
                <span className="text-navy/70">Exposure: <b>₦28.4M</b></span>
                <span className="text-red-700">Switch B Timeout</span>
              </div>
            </div>

            {/* Abuja Hub */}
            <div className="rounded-2xl border border-orange-200 bg-orange-50/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-orange-700">Federal Capital</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-orange-100 text-orange-800">High</span>
              </div>
              <p className="text-lg font-bold text-navy">Abuja FCT Area</p>
              <p className="text-xs text-navy/60 mb-2">Garki, Wuse, Maitama (194 complaints)</p>
              <div className="border-t border-orange-200/60 pt-2 flex items-center justify-between text-xs font-semibold">
                <span className="text-navy/70">Exposure: <b>₦8.9M</b></span>
                <span className="text-orange-700">App Transfers</span>
              </div>
            </div>

            {/* Kano & North */}
            <div className="rounded-2xl border border-navy/10 bg-navy/[0.02] p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-navy/60">North-West Hub</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-navy/10 text-navy/70">Medium</span>
              </div>
              <p className="text-lg font-bold text-navy">Kano &amp; Kaduna</p>
              <p className="text-xs text-navy/60 mb-2">Dala, Fagge, Central (146 complaints)</p>
              <div className="border-t border-navy/10 pt-2 flex items-center justify-between text-xs font-semibold">
                <span className="text-navy/70">Exposure: <b>₦5.2M</b></span>
                <span className="text-navy/80">NIBSS Settlement</span>
              </div>
            </div>

            {/* Port Harcourt & Delta */}
            <div className="rounded-2xl border border-red-200 bg-red-50/50 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold uppercase tracking-wider text-red-700">South-South Hub</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-800">Critical</span>
              </div>
              <p className="text-lg font-bold text-navy">Port Harcourt &amp; Warri</p>
              <p className="text-xs text-navy/60 mb-2">Trans-Amadi, Oil Hubs (140 complaints)</p>
              <div className="border-t border-red-200/60 pt-2 flex items-center justify-between text-xs font-semibold">
                <span className="text-navy/70">Exposure: <b>₦6.9M</b></span>
                <span className="text-red-700">POS Reconciliation</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
