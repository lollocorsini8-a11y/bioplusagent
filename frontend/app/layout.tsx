import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display", weight: ["500", "700"] });
const body = IBM_Plex_Sans({ subsets: ["latin"], variable: "--font-body", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "BioPulse-Agent · prontezza e recupero dell'atleta",
  description: "Agente IA per il monitoraggio biometrico e la prevenzione dello stress atletico (bioERGOtech).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="it" className={`${display.variable} ${body.variable}`}>
      <body>{children}</body>
    </html>
  );
}
