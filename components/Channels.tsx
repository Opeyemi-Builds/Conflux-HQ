const items = [
  ["X", "700 18px Arial"], ["Instagram", "italic 600 17px Georgia"], ["Facebook", "700 15px Verdana"], ["Email", "500 16px Palatino, serif"],
  ["Call transcripts", "700 14px 'Courier New', monospace"], ["Branches", "600 16px Trebuchet MS"], ["In-app chat", "700 16px Arial"], ["USSD", "900 16px 'Arial Black'"],
];
export default function Channels() {
  const track = [...items, ...items];
  return (
    <section id="channels" className="bg-cream px-6 py-6">
      <div className="max-w-[88rem] mx-auto grid grid-cols-1 md:grid-cols-4 gap-8 items-center">
        <p className="text-navy/70 text-base leading-relaxed">Every channel, one feed.<br />Pidgin, Yoruba, Hausa, Igbo and English.</p>
        <div className="marquee-wrap md:col-span-3 overflow-hidden" style={{ maskImage: "linear-gradient(90deg,transparent,#000 8%,#000 92%,transparent)" }}>
          <div className="backers-track">{track.map(([n, f], i) => (<span key={i} className="mx-10 shrink-0 text-navy/50 whitespace-nowrap" style={{ font: f }}>{n}</span>))}</div>
        </div>
      </div>
    </section>
  );
}
