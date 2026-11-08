"use client";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HourlyBucket } from "@/lib/types";

const tip = {
  contentStyle: {
    borderRadius: 12,
    border: "1px solid rgba(20,35,63,.08)",
    boxShadow: "0 10px 30px -10px rgba(20,35,63,.25)",
    fontSize: 12,
  },
};
const axis = {
  tick: { fill: "#6B7894", fontSize: 12 },
  axisLine: false,
  tickLine: false,
} as const;

export function SpikeChart({
  series,
  labels,
  phase = 4,
  release,
  releaseLabel = "Release v4.2.1",
  height = 280,
}: {
  series: number[];
  labels?: string[];
  phase?: number;
  release?: boolean;
  releaseLabel?: string;
  height?: number;
}) {
  const resolvedLabels =
    labels && labels.length === series.length
      ? labels
      : series.map((_, idx) => {
          const totalMin = 9 * 60 + 30 + idx * 5;
          const hh = String(Math.floor(totalMin / 60) % 24).padStart(2, "0");
          const mm = String(totalMin % 60).padStart(2, "0");
          return `${hh}:${mm}`;
        });
  const releaseIdx = Math.min(6, Math.floor(series.length / 3));
  const shown = phase >= 2 ? series.length : phase === 1 ? releaseIdx + 4 : Math.max(1, releaseIdx - 1);
  const data = resolvedLabels.map((t, i) => ({ t, v: i < shown ? series[i] : null }));
  const refX = resolvedLabels[releaseIdx] || resolvedLabels[0];

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ left: -20, right: 8, top: 10 }}>
        <defs>
          <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#E8651A" stopOpacity={0.45} />
            <stop offset="100%" stopColor="#E8651A" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke="#14233F" strokeOpacity={0.06} />
        <XAxis dataKey="t" {...axis} interval={Math.max(1, Math.floor(resolvedLabels.length / 7))} />
        <YAxis {...axis} />
        <Tooltip {...tip} />
        {release && phase >= 1 && refX && (
          <ReferenceLine
            x={refX}
            stroke="#14233F"
            strokeDasharray="4 4"
            label={{
              value: releaseLabel,
              position: "insideTopLeft",
              fill: "#14233F",
              fontSize: 12,
              fontWeight: 600,
            }}
          />
        )}
        <Area
          type="monotone"
          dataKey="v"
          name="Complaints / bucket"
          stroke="#E8651A"
          strokeWidth={2.5}
          fill="url(#g)"
          isAnimationActive
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function HourlyStack({ data, phase = 4 }: { data: HourlyBucket[]; phase?: number }) {
  const shown = phase >= 2 ? data : data.slice(0, Math.max(2, Math.floor(data.length * 0.65)));
  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={shown} margin={{ left: -20, right: 8 }}>
        <CartesianGrid vertical={false} stroke="#14233F" strokeOpacity={0.06} />
        <XAxis dataKey="h" {...axis} />
        <YAxis {...axis} />
        <Tooltip {...tip} />
        <Area
          type="monotone"
          stackId="1"
          dataKey="failed_transfer"
          name="Failed transfer"
          stroke="#E8651A"
          fill="#E8651A"
          fillOpacity={0.85}
        />
        <Area
          type="monotone"
          stackId="1"
          dataKey="fraud_scam"
          name="Fraud / scam"
          stroke="#14233F"
          fill="#14233F"
          fillOpacity={0.9}
        />
        <Area
          type="monotone"
          stackId="1"
          dataKey="card_atm"
          name="Card / ATM"
          stroke="#3D5A80"
          fill="#3D5A80"
          fillOpacity={0.7}
        />
        <Area
          type="monotone"
          stackId="1"
          dataKey="double_debit"
          name="Double debit / POS"
          stroke="#F4A261"
          fill="#F4A261"
          fillOpacity={0.8}
        />
        <Area
          type="monotone"
          stackId="1"
          dataKey="other"
          name="Other / Login / Fees"
          stroke="#B8C2D6"
          fill="#B8C2D6"
          fillOpacity={0.7}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function Bars({
  data,
  color = "#E8651A",
  horizontal = false,
  height = 260,
}: {
  data: { name: string; value: number }[];
  color?: string;
  horizontal?: boolean;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={horizontal ? "vertical" : "horizontal"}
        margin={{ left: horizontal ? 20 : -20, right: 12 }}
      >
        <CartesianGrid horizontal={!horizontal} vertical={horizontal} stroke="#14233F" strokeOpacity={0.06} />
        {horizontal ? (
          <>
            <XAxis type="number" {...axis} />
            <YAxis type="category" dataKey="name" {...axis} width={110} />
          </>
        ) : (
          <>
            <XAxis dataKey="name" {...axis} />
            <YAxis {...axis} />
          </>
        )}
        <Tooltip {...tip} cursor={{ fill: "rgba(20,35,63,.04)" }} />
        <Bar dataKey="value" fill={color} radius={horizontal ? [0, 8, 8, 0] : [8, 8, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLine({ data }: { data: { d: string; min: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ left: -20, right: 12 }}>
        <CartesianGrid vertical={false} stroke="#14233F" strokeOpacity={0.06} />
        <XAxis dataKey="d" {...axis} />
        <YAxis {...axis} />
        <Tooltip {...tip} />
        <Line
          type="monotone"
          dataKey="min"
          name="Volume / Trend"
          stroke="#14233F"
          strokeWidth={2.5}
          dot={{ r: 4, fill: "#E8651A", stroke: "#fff", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
