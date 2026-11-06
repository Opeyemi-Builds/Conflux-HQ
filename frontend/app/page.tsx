import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Info from "@/components/Info";
import Channels from "@/components/Channels";
import UseModes from "@/components/UseModes";
import Footer from "@/components/Footer";
export default function Home() {
  return (
    <main className="flex flex-col bg-cream">
      <div className="h-screen flex flex-col overflow-hidden"><Navbar /><Hero /></div>
      <Info /><Channels /><UseModes /><Footer />
    </main>
  );
}
