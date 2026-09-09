import { HeroSection } from "@/components/marketing/hero-section";
import { ProblemSection } from "@/components/marketing/problem-section";
import { HowItWorksSection } from "@/components/marketing/how-it-works-section";
import { FeaturesSection } from "@/components/marketing/features-section";
import { GitHubBotSection } from "@/components/marketing/github-bot-section";
import { ByokSection } from "@/components/marketing/byok-section";
import { FindingPreviewSection } from "@/components/marketing/finding-preview-section";
import { DashboardPreviewSection } from "@/components/marketing/dashboard-preview-section";
import { CtaSection } from "@/components/marketing/cta-section";

export default function Home() {
  return (
    <>
      <HeroSection />
      <ProblemSection />
      <HowItWorksSection />
      <FeaturesSection />
      <GitHubBotSection />
      <ByokSection />
      <FindingPreviewSection />
      <DashboardPreviewSection />
      <CtaSection />
    </>
  );
}
