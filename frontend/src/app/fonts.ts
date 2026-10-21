import { Geist, Geist_Mono } from "next/font/google";
import localFont from "next/font/local";

export const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

export const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const satoshiBlack = localFont({
  src: "./fonts/Satoshi-Black.woff2",
  weight: "900",
  style: "normal",
  display: "swap",
  preload: false,
});
