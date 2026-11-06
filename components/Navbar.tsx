import Link from "next/link";
import LogoIcon from "./LogoIcon";

const links = [
  ["Product", "#product"],
  ["How it works", "#how"],
  ["Channels", "#channels"],
  ["Views", "#views"],
  ["Trust", "#trust"],
  ["Dashboard", "/dashboard"],
];

export default function Navbar() {
  return (
    <nav className="absolute top-0 left-0 right-0 z-20 px-6 py-5">
      <div className="max-w-[88rem] mx-auto flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5">
          <LogoIcon className="w-8 h-8" />
          <span className="text-2xl font-semibold tracking-tight text-navy">
            Conflux <span className="text-flux">HQ</span>
          </span>
        </Link>
        <div className="hidden md:flex items-center gap-8">
          {links.map(([l, h]) => (
            <Link
              key={l}
              href={h}
              className="text-base text-navy-400 hover:text-navy font-medium transition-colors duration-200"
            >
              {l}
            </Link>
          ))}
        </div>
        <Link
          href="/dashboard"
          className="bg-navy text-white text-base font-medium px-7 py-2.5 rounded-full hover:bg-navy-600 transition-colors duration-200 shadow-sm"
        >
          Open Dashboard
        </Link>
      </div>
    </nav>
  );
}
