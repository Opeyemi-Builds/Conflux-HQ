import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function PillButton({ href, children, size = "lg" }: { href: string; children: React.ReactNode; size?: "md" | "lg" }) {
  return (
    <Link href={href} className={`group inline-flex items-center gap-3 bg-navy text-white font-medium pl-8 pr-2 py-2 rounded-full hover:bg-navy-600 transition-colors duration-200 ${size === "lg" ? "text-base md:text-lg" : "text-base"}`}>
      {children}
      <span className="bg-flux rounded-full p-2 transition-transform duration-200 group-hover:translate-x-0.5"><ArrowRight className="w-5 h-5 text-white" /></span>
    </Link>
  );
}
