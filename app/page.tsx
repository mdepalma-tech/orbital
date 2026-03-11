import { AuthButton } from "@/components/auth-button";
import { BackgroundEffects } from "@/components/background-effects";
import { HeroSectionLoader } from "@/components/orbital-3d/HeroSectionLoader";
import { ScrollReveal, StaggerChildren } from "@/components/scroll-reveal";
import { WaitlistForm } from "@/components/waitlist-form";
import { hasEnvVars } from "@/lib/utils";
import Link from "next/link";
import { Suspense } from "react";

export default function Home() {
  return (
    <main className="relative min-h-screen bg-[#0B0F14] text-white overflow-hidden">
      {/* Background Elements */}
      <BackgroundEffects />

      {/* Navigation */}
      <nav className="relative z-50 w-full border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <Link href="/" className="text-xl font-light tracking-wider">
            ORBITAL
          </Link>
          <div className="flex items-center gap-6">
            {hasEnvVars && (
              <Suspense>
                <AuthButton />
              </Suspense>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section - 3D Orbital Animation */}
      <HeroSectionLoader />

      {/* Section 2 - The Problem */}
      <section className="relative z-10 py-32 px-6">
        <div className="max-w-5xl mx-auto">
          <ScrollReveal className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-light mb-6 tracking-tight">
              Attribution Shows Motion.
              <br />
              <span className="text-gray-500">Not Gravity.</span>
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto font-light leading-relaxed">
              Every platform takes credit.
              <br />
              None of them show you what actually created demand.
            </p>
          </ScrollReveal>

          <div className="max-w-2xl mx-auto mb-16">
            <StaggerChildren className="grid grid-cols-3 gap-4 mb-10" stagger={150}>
              <div className="p-5 rounded-xl border border-blue-500/20 bg-blue-500/5 text-center">
                <p className="text-sm text-blue-400 font-light mb-1">Meta Ads</p>
                <p className="text-xs text-gray-500 font-light">Takes credit</p>
              </div>
              <div className="p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center">
                <p className="text-sm text-emerald-400 font-light mb-1">Google Ads</p>
                <p className="text-xs text-gray-500 font-light">Also takes credit</p>
              </div>
              <div className="p-5 rounded-xl border border-rose-500/20 bg-rose-500/5 text-center">
                <p className="text-sm text-rose-400 font-light mb-1">TikTok Ads</p>
                <p className="text-xs text-gray-500 font-light">Claims credit too</p>
              </div>
            </StaggerChildren>

            <ScrollReveal delay={100}>
              <p className="text-center text-gray-500 font-light text-sm mb-10">
                Each platform sees only its slice. None see the full picture.
              </p>
            </ScrollReveal>

            <ScrollReveal delay={150}>
              <div className="space-y-4 mb-12">
                <p className="text-gray-400 font-light text-center">
                  When performance shifts, you still can&apos;t answer:
                </p>
                <StaggerChildren className="space-y-3 max-w-xl mx-auto" stagger={120}>
                  {[
                    "Whether your Meta spend is creating new customers — or reaching people who'd have bought anyway",
                    "Why revenue dropped last Tuesday — was it traffic, conversion rate, or average order value?",
                    "Which channels build long-term customers and which ones only ever convert once",
                  ].map((item, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500/70 flex-shrink-0 mt-1.5" />
                      <span className="text-gray-400 font-light text-sm leading-relaxed">{item}</span>
                    </div>
                  ))}
                </StaggerChildren>
              </div>
            </ScrollReveal>

            <ScrollReveal delay={200}>
              <p className="text-center text-gray-300 font-light text-lg">
                Orbital measures contribution at the <span className="text-white">system level</span> — not the platform level.
              </p>
            </ScrollReveal>
          </div>

          <ScrollReveal>
            <div className="relative h-48 opacity-30">
              <div className="chaotic-orbits">
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-64 h-64 border border-dashed border-red-500/30 rounded-full animate-spin-slow" />
                  <div className="absolute w-48 h-48 border border-dashed border-orange-500/30 rounded-full animate-spin-reverse" />
                  <div className="absolute w-32 h-32 border border-dashed border-yellow-500/30 rounded-full animate-spin-slow" />
                </div>
              </div>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* Section 3 - How It Works */}
      <section id="how-it-works" className="relative z-10 py-32 px-6 bg-gradient-to-b from-transparent via-blue-950/10 to-transparent">
        <div className="max-w-4xl mx-auto">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light text-center mb-12 tracking-tight">
              One Model. Every Force.
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={100} className="text-center mb-16">
            <p className="text-xl text-gray-400 font-light mb-4 max-w-2xl mx-auto leading-relaxed">
              Revenue doesn&apos;t come from one place. It emerges from demand creation, funnel mechanics, retention, and seasonality — all interacting at once.
            </p>
            <p className="text-base text-gray-500 font-light mb-10">
              Orbital models them together.
            </p>

            <StaggerChildren className="flex flex-wrap justify-center gap-3 mb-12" stagger={80}>
              {[
                { label: "Revenue", color: "border-amber-500/30 text-amber-400 bg-amber-500/5" },
                { label: "Traffic", color: "border-blue-500/30 text-blue-400 bg-blue-500/5" },
                { label: "Conversion", color: "border-emerald-500/30 text-emerald-400 bg-emerald-500/5" },
                { label: "Seasonality", color: "border-violet-500/30 text-violet-400 bg-violet-500/5" },
                { label: "Ad Spend", color: "border-cyan-500/30 text-cyan-400 bg-cyan-500/5" },
                { label: "Promotions", color: "border-rose-500/30 text-rose-400 bg-rose-500/5" },
                { label: "Retention", color: "border-indigo-500/30 text-indigo-400 bg-indigo-500/5" },
                { label: "LTV", color: "border-orange-500/30 text-orange-400 bg-orange-500/5" },
              ].map((item, i) => (
                <span
                  key={i}
                  className={`px-4 py-2 rounded-full border text-sm font-light ${item.color}`}
                >
                  {item.label}
                </span>
              ))}
            </StaggerChildren>
          </ScrollReveal>

          <ScrollReveal delay={150}>
            <div className="max-w-3xl mx-auto space-y-6 mb-16">
              <p className="text-gray-400 font-light text-lg text-center leading-relaxed">
                Connect your Shopify store and Orbital handles the rest — ingesting your revenue, order data, and ad spend to build a unified model of your business.
              </p>
            </div>
          </ScrollReveal>

          <StaggerChildren className="grid grid-cols-3 gap-6 max-w-xl mx-auto" stagger={150}>
            <div className="text-center">
              <div className="w-1 h-1 rounded-full bg-red-500/50 mx-auto mb-3" />
              <p className="text-sm text-gray-500 font-light">Not last click</p>
            </div>
            <div className="text-center">
              <div className="w-1 h-1 rounded-full bg-red-500/50 mx-auto mb-3" />
              <p className="text-sm text-gray-500 font-light">Not blended attribution</p>
            </div>
            <div className="text-center">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mx-auto mb-3" />
              <p className="text-sm text-white font-light">Modeled system-level impact</p>
            </div>
          </StaggerChildren>
        </div>
      </section>

      {/* Section 4 - What Orbital Reveals */}
      <section className="relative z-10 py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light text-center mb-4 tracking-tight">
              What Orbital Reveals.
            </h2>
            <p className="text-center text-gray-500 font-light text-base mb-20 max-w-xl mx-auto">
              Six lenses. One unified system. Everything you need to run a smarter brand.
            </p>
          </ScrollReveal>

          <StaggerChildren className="grid md:grid-cols-2 lg:grid-cols-3 gap-6" stagger={100}>
            {[
              {
                title: "Where Demand Actually Comes From",
                subtitle: "Incremental Channel Attribution",
                desc: "See which channels generate real, new demand — not just credit. Orbital isolates incremental revenue per channel, separating genuine lift from revenue that would have happened regardless.",
                accent: "bg-amber-500/70",
                border: "hover:border-amber-500/40 hover:shadow-amber-500/10",
              },
              {
                title: "Why Your Funnel Moves",
                subtitle: "Traffic & Conversion Diagnostics",
                desc: "When revenue shifts, Orbital tells you whether it came from traffic, conversion rate, or average order value — and traces the change back to its source: a campaign, a promotion, a pricing update.",
                accent: "bg-blue-500/70",
                border: "hover:border-blue-500/40 hover:shadow-blue-500/10",
              },
              {
                title: "The True Value of Each Customer",
                subtitle: "LTV & Retention by Channel",
                desc: "Not all customers are equal. Orbital models cohort retention and lifetime value by acquisition channel — so you can see which channels build lasting customers, and which ones only convert once.",
                accent: "bg-emerald-500/70",
                border: "hover:border-emerald-500/40 hover:shadow-emerald-500/10",
              },
              {
                title: "Your Real Unit Economics",
                subtitle: "CAC, Margin & Payback Period",
                desc: "Track your true acquisition cost, contribution margin, and payback period — by channel. Orbital optimizes for profit, not just revenue. Because a sale that costs more than it earns isn't growth.",
                accent: "bg-violet-500/70",
                border: "hover:border-violet-500/40 hover:shadow-violet-500/10",
              },
              {
                title: "What's Coming Next",
                subtitle: "Revenue Forecasting",
                desc: "Forward projections built on your trend, seasonality, planned spend, and upcoming events. A reliable revenue forecast for inventory planning, cash flow, and knowing what to expect before it happens.",
                accent: "bg-cyan-500/70",
                border: "hover:border-cyan-500/40 hover:shadow-cyan-500/10",
              },
              {
                title: "Where to Put Your Next Dollar",
                subtitle: "Budget Optimization",
                desc: "Model how shifting spend across channels changes your outcomes. Find the allocation that maximizes incremental contribution — not platform-reported ROAS, not vanity metrics.",
                accent: "bg-rose-500/70",
                border: "hover:border-rose-500/40 hover:shadow-rose-500/10",
              },
            ].map((feature, i) => (
              <div
                key={i}
                className={`group relative p-8 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent backdrop-blur-sm hover:shadow-lg transition-all duration-300 ${feature.border}`}
              >
                <div className={`w-8 h-0.5 rounded-full ${feature.accent} mb-6 group-hover:w-12 transition-all duration-300`} />
                <h3 className="text-lg font-light mb-1.5 leading-snug">{feature.title}</h3>
                <p className="text-gray-600 text-xs font-light mb-4 tracking-wide uppercase">{feature.subtitle}</p>
                <p className="text-gray-400 text-sm font-light leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </StaggerChildren>
        </div>
      </section>

      {/* Integrations */}
      <section className="relative z-10 py-16 px-6 border-y border-white/5">
        <div className="max-w-4xl mx-auto">
          <ScrollReveal className="text-center mb-10">
            <p className="text-xs text-gray-600 font-light tracking-widest uppercase">Connects to your stack</p>
          </ScrollReveal>
          <StaggerChildren className="flex flex-wrap justify-center items-center gap-3" stagger={80}>
            <div className="px-6 py-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 flex items-center gap-2.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <p className="text-sm text-emerald-400 font-light">Shopify</p>
            </div>
            {[
              { name: "Meta Ads", textClass: "text-blue-500/50", borderClass: "border-blue-500/15" },
              { name: "Google Ads", textClass: "text-amber-500/50", borderClass: "border-amber-500/15" },
              { name: "Email", textClass: "text-violet-500/50", borderClass: "border-violet-500/15" },
              { name: "TikTok Ads", textClass: "text-rose-500/50", borderClass: "border-rose-500/15" },
            ].map(({ name, textClass, borderClass }) => (
              <div key={name} className={`px-6 py-3 rounded-lg border ${borderClass} bg-white/[0.015] flex items-center gap-2.5`}>
                <p className={`text-sm font-light ${textClass}`}>{name}</p>
                <span className="text-xs text-gray-700 font-light">coming soon</span>
              </div>
            ))}
          </StaggerChildren>
        </div>
      </section>

      {/* Section 5 - Continuous Intelligence */}
      <section className="relative z-10 py-32 px-6 bg-gradient-to-b from-violet-950/10 to-transparent">
        <div className="max-w-5xl mx-auto text-center">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light mb-6 tracking-tight">
              Not Just a Model.
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-blue-400">
                Continuous Intelligence.
              </span>
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={100}>
            <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8 font-light leading-relaxed">
              Your business changes every day. A campaign launches. A product sells out. A promotion ends. Seasonality kicks in.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={200}>
            <p className="text-lg text-gray-400 max-w-3xl mx-auto font-light leading-relaxed mb-8">
              Orbital monitors your business continuously — comparing what actually happened against what was statistically expected. When revenue, traffic, or conversion deviates from the model, you know immediately. And you know exactly why.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={300}>
            <p className="text-base text-gray-500 max-w-2xl mx-auto font-light leading-relaxed mb-12">
              Not a one-time report. Not a static dashboard. A system that watches your business every single day.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={400}>
            <div className="flex flex-col sm:flex-row justify-center gap-8">
              <p className="text-gray-500 font-light">Stable when performance is stable.</p>
              <p className="text-gray-400 font-light">Alert when it isn&apos;t.</p>
            </div>
          </ScrollReveal>
        </div>
      </section>

      {/* Final CTA + Waitlist */}
      <section id="waitlist" className="relative z-10 py-40 px-6 scroll-mt-16">
        <div className="max-w-4xl mx-auto text-center">
          <ScrollReveal distance={60} duration={900}>
            <h2 className="text-5xl md:text-6xl font-light mb-6 tracking-tight leading-tight">
              Stop Guessing.
              <br />
              Start Knowing.
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={100} distance={20} duration={700}>
            <p className="text-xl text-gray-400 font-light mb-12 max-w-2xl mx-auto leading-relaxed">
              Orbital is launching soon for Shopify merchants.
              <br />
              Join the waitlist for early access and be first to see what&apos;s actually driving your growth.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={200} distance={20} duration={800}>
            <WaitlistForm />
          </ScrollReveal>
        </div>
      </section>

      {/* Footer */}
      <ScrollReveal distance={20} duration={500}>
        <footer className="relative z-10 border-t border-white/5 py-8">
          <div className="max-w-7xl mx-auto px-6 text-center text-gray-600 text-sm font-light">
            <p>&copy; 2026 Orbital. Know what moves your business.</p>
          </div>
        </footer>
      </ScrollReveal>
    </main>
  );
}
