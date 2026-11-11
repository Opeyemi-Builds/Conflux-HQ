import type { Metadata } from "next";
import CastLanding from "@/components/CastLanding";
import "./cast-landing.css";

export const metadata: Metadata = {
  title: "Conflux HQ — Every complaint. A bigger picture.",
  description: "Bring customer reports, payment evidence, and the people who can act into one shared workspace.",
};

export default function Home() {
  return <CastLanding />;
}
