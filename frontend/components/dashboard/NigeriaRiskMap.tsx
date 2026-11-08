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
import { ISSUE_LABEL } from "@/lib/types";

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
  channel: string;
  time: string;
  summary: string;
  incidentId?: string | null;
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

// Nigerian geographic city & state coordinate lookup
const CITY_COORDS: Record<string, { name: string; state: string; zone: string; lat: number; lng: number }> = {
  lagos: { name: "Lagos / VI / Ikeja", state: "Lagos", zone: "South-West", lat: 6.52, lng: 3.38 },
  ikeja: { name: "Ikeja / Lagos", state: "Lagos", zone: "South-West", lat: 6.60, lng: 3.35 },
  abuja: { name: "Abuja FCT", state: "FCT", zone: "North-Central", lat: 9.07, lng: 7.40 },
  fct: { name: "Abuja FCT", state: "FCT", zone: "North-Central", lat: 9.07, lng: 7.40 },
  ibadan: { name: "Ibadan", state: "Oyo", zone: "South-West", lat: 7.38, lng: 3.95 },
  kano: { name: "Kano", state: "Kano", zone: "North-West", lat: 12.00, lng: 8.59 },
  "port harcourt": { name: "Port Harcourt", state: "Rivers", zone: "South-South", lat: 4.82, lng: 7.05 },
  rivers: { name: "Port Harcourt", state: "Rivers", zone: "South-South", lat: 4.82, lng: 7.05 },
  enugu: { name: "Enugu", state: "Enugu", zone: "South-East", lat: 6.45, lng: 7.54 },
  kaduna: { name: "Kaduna", state: "Kaduna", zone: "North-West", lat: 10.51, lng: 7.41 },
  benin: { name: "Benin City", state: "Edo", zone: "South-South", lat: 6.34, lng: 5.62 },
  onitsha: { name: "Onitsha / Aba", state: "Anambra", zone: "South-East", lat: 6.15, lng: 6.78 },
  warri: { name: "Warri / Asaba", state: "Delta", zone: "South-South", lat: 5.52, lng: 5.75 },
  jos: { name: "Jos", state: "Plateau", zone: "North-Central", lat: 9.90, lng: 8.86 },
  ilorin: { name: "Ilorin", state: "Kwara", zone: "North-Central", lat: 8.48, lng: 4.54 },
  abeokuta: { name: "Abeokuta", state: "Ogun", zone: "South-West", lat: 7.15, lng: 3.34 },
  maiduguri: { name: "Maiduguri", state: "Borno", zone: "North-East", lat: 11.83, lng: 13.15 },
  sokoto: { name: "Sokoto", state: "Sokoto", zone: "North-West", lat: 13.06, lng: 5.23 },
  calabar: { name: "Calabar", state: "Cross River", zone: "South-South", lat: 4.95, lng: 8.32 },
};

const cityHubs = [
  { name: "Lagos / VI / Ikeja", state: "Lagos", lat: 6.52, lng: 3.38 },
  { name: "Abuja FCT", state: "FCT", lat: 9.07, lng: 7.40 },
  { name: "Ibadan", state: "Oyo", lat: 7.38, lng: 3.95 },
  { name: "Kano", state: "Kano", lat: 12.00, lng: 8.59 },
  { name: "Port Harcourt", state: "Rivers", lat: 4.82, lng: 7.05 },
  { name: "Benin City", state: "Edo", lat: 6.34, lng: 5.62 },
  { name: "Enugu", state: "Enugu", lat: 6.45, lng: 7.54 },
  { name: "Onitsha / Aba", state: "Anambra", lat: 6.15, lng: 6.78 },
  { name: "Kaduna", state: "Kaduna", lat: 10.51, lng: 7.41 },
  { name: "Warri / Asaba", state: "Delta", lat: 5.52, lng: 5.75 },
  { name: "Jos", state: "Plateau", lat: 9.90, lng: 8.86 },
  { name: "Ilorin", state: "Kwara", lat: 8.48, lng: 4.54 },
  { name: "Abeokuta", state: "Ogun", lat: 7.15, lng: 3.34 },
  { name: "Maiduguri", state: "Borno", lat: 11.83, lng: 13.15 },
  { name: "Sokoto", state: "Sokoto", lat: 13.06, lng: 5.23 },
  { name: "Calabar", state: "Cross River", lat: 4.95, lng: 8.32 },
];

function hashString(str: string): [number, number] {
  let h1 = 2166136261;
  let h2 = 16777619;
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    h1 ^= c;
    h1 = Math.imul(h1, 16777619);
    h2 ^= c * (i + 1);
    h2 = Math.imul(h2, 2166136261);
  }
  const u1 = ((h1 >>> 0) % 10000) / 10000;
  const u2 = ((h2 >>> 0) % 10000) / 10000;
  return [u1, u2];
}

export default function NigeriaRiskMap() {
  const { complaints, summary, incidents } = useDash();
  const [selectedRisk, setSelectedRisk] = useState<RiskLevel>("all");
  const [selectedChannel, setSelectedChannel] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [activePoint, setActivePoint] = useState<GeoComplaint | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [showExecutiveBrief, setShowExecutiveBrief] = useState(true);

  // Map live backend complaints directly onto Nigerian geographic coordinates
  const geoComplaintsData = useMemo<GeoComplaint[]>(() => {
    return complaints.map((c, idx) => {
      const regionKey = (c.region || "Lagos").toLowerCase().trim();
      const hub = CITY_COORDS[regionKey] || CITY_COORDS.lagos;
      const [u1, u2] = hashString(`${c.id}-${idx}`);
      const maxRadius = hub.state === "Lagos" ? 0.42 : hub.state === "FCT" ? 0.48 : 0.62;
      const radius = Math.sqrt(u1) * maxRadius;
      const angle = u2 * Math.PI * 2;
      const lat = hub.lat + Math.sin(angle) * radius;
      const lng = hub.lng + Math.cos(angle) * radius;

      return {
        id: `GEO-${c.id}-${idx}`,
        city: hub.name,
        state: hub.state,
        zone: hub.zone,
        lat,
        lng,
        risk: c.severity || "medium",
        issue: ISSUE_LABEL[c.issue] || c.issue,
        amount: c.amount ? `₦${c.amount.toLocaleString()}` : "₦0",
        channel: c.channel,
        time: c.time,
        summary: c.text,
        incidentId: c.incidentId,
        status: c.severity === "critical" ? "active" : c.severity === "high" ? "investigating" : "quarantined",
      };
    });
  }, [complaints]);

  const availableChannels = useMemo(() => {
    return Array.from(new Set(geoComplaintsData.map((p) => p.channel)));
  }, [geoComplaintsData]);

  // Filtered dots
  const filteredPoints = useMemo(() => {
    return geoComplaintsData.filter((p) => {
      const matchRisk = selectedRisk === "all" || p.risk === selectedRisk;
      const matchChannel = selectedChannel === "all" || p.channel === selectedChannel;
      const matchSearch =
        !searchQuery ||
        p.city.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.state.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.issue.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.summary.toLowerCase().includes(searchQuery.toLowerCase());
      return matchRisk && matchChannel && matchSearch;
    });
  }, [geoComplaintsData, selectedRisk, selectedChannel, searchQuery]);

  // Regional metrics calculation from live backend data
  const totalMoneyAtRisk = summary?.money_at_risk
    ? `₦${(Number(summary.money_at_risk) / 1000000).toFixed(2)}M`
    : `₦${(
        complaints.reduce((acc, c) => acc + (c.amount || 0), 0) / 1000000
      ).toFixed(2)}M`;
  const criticalCount = geoComplaintsData.filter((p) => p.risk === "critical").length;
  const highCount = geoComplaintsData.filter((p) => p.risk === "high").length;

  const regionalStats = useMemo(() => {
    const byRegion = new Map<string, { count: number; exposure: number; topIssue: string }>();
    complaints.forEach((c) => {
      const reg = c.region || "Lagos";
      const cur = byRegion.get(reg) || { count: 0, exposure: 0, topIssue: ISSUE_LABEL[c.issue] || c.issue };
      cur.count += 1;
      cur.exposure += c.amount || 0;
      byRegion.set(reg, cur);
    });
    return byRegion;
  }, [complaints]);

  const lagosCount = regionalStats.get("Lagos")?.count || 0;
  const lagosPercentage =
    complaints.length > 0 ? `${((lagosCount / complaints.length) * 100).toFixed(1)}%` : "0%";

  const primaryIncidentHref = incidents[0] ? `/dashboard/incidents/${incidents[0].id}` : "/dashboard/complaints";

  const getDotColor = (risk: GeoComplaint["risk"]) => {
    switch (risk) {
      case "critical":
        return "#DC2626";
      case "high":
        return "#E8651A";
      case "medium":
        return "#8B5CF6";
      case "low":
        return "#10B981";
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
            Real-time multi-channel incident density across Nigerian states + FCT ({geoComplaintsData.length} live backend records).
          </p>
        </div>

        {/* Quick Filter Pills & Search */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-navy/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search city, state, issue..."
              className="pl-8 pr-3 py-1.5 rounded-full text-xs bg-white border border-navy/10 text-navy outline-none focus:border-flux w-44 md:w-52"
            />
          </div>

          <select
            value={selectedChannel}
            onChange={(e) => setSelectedChannel(e.target.value)}
            className="px-3 py-1.5 rounded-full text-xs font-medium bg-white border border-navy/10 text-navy outline-none focus:border-flux"
          >
            <option value="all">All Channels</option>
            {availableChannels.map((ch) => (
              <option key={ch} value={ch}>
                {ch}
              </option>
            ))}
          </select>

          <div className="flex items-center bg-navy/[0.04] p-1 rounded-full border border-navy/[0.06]">
            {(["all", "critical", "high", "medium", "low"] as RiskLevel[]).map((level) => (
              <button
                key={level}
                onClick={() => setSelectedRisk(level)}
                className={`px-3 py-1 rounded-full text-xs font-semibold capitalize transition-all ${
                  selectedRisk === level
                    ? "bg-navy text-white shadow-sm"
                    : "text-navy/60 hover:text-navy"
                }`}
              >
                {level}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Top Executive KPI Strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-y lg:divide-y-0 divide-navy/[0.06] border-b border-navy/[0.06] bg-white">
        <div className="p-4 px-6">
          <p className="text-xs font-medium text-navy/50">Total Disputed Value on Map</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-navy">{totalMoneyAtRisk}</span>
            <span className="text-xs font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">Live Exposure</span>
          </div>
        </div>
        <div className="p-4 px-6">
          <p className="text-xs font-medium text-navy/50">Critical &amp; High Severity Clusters</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-flux">{criticalCount + highCount}</span>
            <span className="text-xs text-navy/50">of {geoComplaintsData.length} mapped</span>
          </div>
        </div>
        <div className="p-4 px-6">
          <p className="text-xs font-medium text-navy/50">Primary Epicenter</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-navy">Lagos ({lagosPercentage})</span>
            <span className="text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full">{lagosCount} cases</span>
          </div>
        </div>
        <div className="p-4 px-6">
          <p className="text-xs font-medium text-navy/50">Active Incidents</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-2xl font-bold text-emerald-700">{incidents.length} Open</span>
            <span className="text-xs text-navy/50">AI Correlated</span>
          </div>
        </div>
      </div>

      {/* Main Map Canvas + Floating Overlays */}
      <div className="relative bg-[#F5EDF0] min-h-[480px] lg:min-h-[560px] flex items-center justify-center overflow-hidden select-none">
        <div
          className="w-full h-full flex items-center justify-center transition-transform duration-300 ease-out"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          <svg
            viewBox="0 0 1000 750"
            className="w-full h-full max-h-[600px] object-contain"
          >
            <defs>
              <radialGradient id="lagosGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#DC2626" stopOpacity="0.38" />
                <stop offset="100%" stopColor="#DC2626" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="phGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#E8651A" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#E8651A" stopOpacity="0" />
              </radialGradient>
              <pattern id="mapGrid" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#D8C2CB" strokeWidth="0.4" strokeOpacity="0.6" />
              </pattern>
            </defs>

            {/* Map Background */}
            <rect width="1000" height="750" fill="#F6EEF2" />
            <rect width="1000" height="750" fill="url(#mapGrid)" />

            {/* Atlantic Ocean / Gulf of Guinea */}
            <path
              d="M 0,585 Q 90,590 190,625 T 340,715 L 445,705 Q 510,730 600,750 L 0,750 Z"
              fill="#DCEEF8"
              opacity="0.7"
            />
            <text x="80" y="695" fill="#6996B3" fontSize="13" fontStyle="italic" fontWeight="500" letterSpacing="1">
              GULF OF GUINEA · ATLANTIC OCEAN
            </text>

            {/* Neighboring Country Borders */}
            <g stroke="#C8A4B6" strokeWidth="1.2" strokeDasharray="4,4" fill="none">
              <path d="M 110,0 L 118,175 L 95,380 L 70,588" />
              <path d="M 118,175 L 310,60 L 550,95 L 780,70 L 920,0" />
              <path d="M 885,155 L 820,310 L 725,465 L 610,550 L 495,695" />
            </g>

            {/* Neighbor Labels */}
            <g fill="#8A7982" fontSize="12" fontWeight="500">
              <text x="18" y="340">BÉNIN</text>
              <text x="360" y="38">NIGER REPUBLIC</text>
              <text x="690" y="620">CAMEROUN</text>
              <text x="865" y="75">TCHAD</text>
            </g>

            {/* Nigeria National Boundary Outline */}
            <path
              d="M 72,585
                 L 68,480 L 82,390 L 65,305 L 95,215 L 118,130
                 L 175,78 L 245,75 L 315,105 L 405,92 L 495,98 L 595,125 L 705,105 L 815,82 L 885,135
                 L 865,220 L 815,305 L 775,365 L 735,445 L 690,505 L 605,530 L 545,585 L 495,675
                 L 430,695 L 365,712 L 305,695 L 250,635 L 185,595 L 115,588 Z"
              fill="#FAF6F8"
              stroke="#B98EA2"
              strokeWidth="3"
            />

            {/* Internal State & Geopolitical Zone Boundaries */}
            <g stroke="#D6B8C6" strokeWidth="1" fill="none" opacity="0.85">
              <path d="M 95,215 L 240,235 L 365,245 L 495,230 L 635,240 L 845,220" />
              <path d="M 82,390 L 210,375 L 345,390 L 475,380 L 615,405 L 755,395" />
              <path d="M 68,480 L 185,485 L 295,505 L 415,510 L 545,525" />
              <path d="M 245,75 L 240,235 L 210,375 L 185,485 L 185,595" />
              <path d="M 405,92 L 365,245 L 345,390 L 295,505 L 305,695" />
              <path d="M 595,125 L 555,260 L 475,380 L 415,510 L 430,695" />
              <path d="M 705,105 L 665,255 L 615,405 L 545,585" />
              <rect x="365" y="340" width="75" height="62" rx="6" stroke="#9D7589" strokeWidth="1.4" fill="#F3E8EE" />
            </g>

            {/* River Niger & River Benue Confluence */}
            <path
              d="M 115,235 Q 210,310 295,385 T 385,445 L 365,695 M 755,365 Q 560,410 385,445"
              fill="none"
              stroke="#B8D8EB"
              strokeWidth="3.5"
              strokeLinecap="round"
              opacity="0.7"
            />

            {/* Live Hotspot Pulsing Rings */}
            <circle cx="82" cy="570" r="75" fill="url(#lagosGlow)" />
            <circle cx="82" cy="570" r="42" fill="none" stroke="#DC2626" strokeWidth="1.5" className="animate-ping" style={{ transformOrigin: "82px 570px", animationDuration: "2.4s" }} />
            <circle cx="372" cy="689" r="45" fill="url(#phGlow)" />
            <circle cx="400" cy="373" r="40" fill="url(#phGlow)" />

            {/* Live Backend Complaint Dots */}
            {filteredPoints.map((point) => {
              const { x, y } = project(point.lng, point.lat);
              const isSelected = activePoint?.id === point.id;
              const color = getDotColor(point.risk);

              return (
                <g key={point.id} onClick={() => setActivePoint(point)} className="cursor-pointer group">
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
                    stroke="#FFFFFF"
                    strokeWidth="2.5"
                    paintOrder="stroke"
                  >
                    {city.state === "FCT" ? "Abuja" : city.state}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        {/* Floating Map Legend */}
        <div className="absolute bottom-4 left-4 rounded-2xl bg-white/95 backdrop-blur-md border border-navy/10 p-3.5 shadow-lg text-xs space-y-2 max-w-[230px]">
          <div className="font-bold text-navy flex items-center justify-between">
            <span>RISK SEVERITY KEY</span>
            <span className="text-[10px] font-mono text-navy/50">LIVE STREAM</span>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#DC2626] inline-block border border-white shadow-sm" />
              <span className="text-navy/80 font-medium">Critical (Fraud / Unreversed)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#E8651A] inline-block border border-white shadow-sm" />
              <span className="text-navy/80 font-medium">High (USSD / App Spike)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#8B5CF6] inline-block border border-white shadow-sm" />
              <span className="text-navy/80 font-medium">Medium (POS / ATM Dispense)</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-[#10B981] inline-block border border-white shadow-sm" />
              <span className="text-navy/80 font-medium">Low (Fee / Login Inquiry)</span>
            </div>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 bg-white/95 backdrop-blur-md border border-navy/10 p-1.5 rounded-2xl shadow-lg">
          <button
            onClick={() => setZoomLevel((z) => Math.min(z + 0.25, 2.2))}
            className="w-8 h-8 rounded-xl flex items-center justify-center text-navy hover:bg-navy/5 transition-colors"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.max(z - 0.25, 1))}
            className="w-8 h-8 rounded-xl flex items-center justify-center text-navy hover:bg-navy/5 transition-colors"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setZoomLevel(1);
              setSelectedRisk("all");
              setSelectedChannel("all");
              setSearchQuery("");
              setActivePoint(null);
            }}
            className="w-8 h-8 rounded-xl flex items-center justify-center text-navy hover:bg-navy/5 transition-colors"
            title="Reset map"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
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
                    <p className="text-xs text-navy/55">{activePoint.zone} · {activePoint.id.slice(0, 12)}</p>
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
                  <span>Time: <b>{activePoint.time}</b></span>
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
                  href={activePoint.incidentId ? `/dashboard/incidents/${activePoint.incidentId}` : primaryIncidentHref}
                  className="flex-1 text-center py-2 px-3 rounded-xl bg-navy text-white text-xs font-semibold hover:bg-navy-600 transition-colors flex items-center justify-center gap-1.5"
                >
                  Inspect Incident <ExternalLink className="w-3.5 h-3.5" />
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
              Executive Bank Briefing · Live Database Regional Synthesis
            </div>
            <h3 className="text-lg font-bold text-navy">
              Top At-Risk Banking Corridors &amp; Exposure
            </h3>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-navy/55">Showing {filteredPoints.length} live complaints geocoded across Nigeria</span>
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
            {[
              { region: "Lagos", zone: "South-West Epicenter", badge: "Critical", tone: "red" },
              { region: "Abuja", zone: "Federal Capital", badge: "High", tone: "orange" },
              { region: "Kano", zone: "North-West Hub", badge: "High", tone: "navy" },
              { region: "Port Harcourt", zone: "South-South Hub", badge: "High", tone: "red" },
            ].map((card) => {
              const stat = regionalStats.get(card.region) || { count: 0, exposure: 0, topIssue: "Failed transfer" };
              const expM = `₦${(stat.exposure / 1_000_000).toFixed(2)}M`;
              return (
                <div
                  key={card.region}
                  className={`rounded-2xl border p-4 ${
                    card.tone === "red"
                      ? "border-red-200 bg-red-50/50"
                      : card.tone === "orange"
                      ? "border-orange-200 bg-orange-50/50"
                      : "border-navy/10 bg-navy/[0.02]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-navy/70">{card.zone}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-white border border-navy/10 text-navy">
                      {card.badge}
                    </span>
                  </div>
                  <p className="text-lg font-bold text-navy">{card.region} Corridor</p>
                  <p className="text-xs text-navy/60 mb-2">{stat.count} live database complaints</p>
                  <div className="border-t border-navy/10 pt-2 flex items-center justify-between text-xs font-semibold">
                    <span className="text-navy/70">
                      Exposure: <b>{expM}</b>
                    </span>
                    <span className="text-flux">{stat.topIssue}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
