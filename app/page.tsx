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
              Dashboards assign credit.
              <br />
              They don&apos;t measure incremental impact.
            </p>
          </ScrollReveal>

          <div className="max-w-2xl mx-auto mb-16">
            <StaggerChildren className="grid grid-cols-3 gap-4 mb-10" stagger={150}>
              <div className="p-5 rounded-xl border border-blue-500/20 bg-blue-500/5 text-center">
                <p className="text-sm text-blue-400 font-light mb-1">Meta</p>
                <p className="text-xs text-gray-500 font-light">Reports one number</p>
              </div>
              <div className="p-5 rounded-xl border border-emerald-500/20 bg-emerald-500/5 text-center">
                <p className="text-sm text-emerald-400 font-light mb-1">Google</p>
                <p className="text-xs text-gray-500 font-light">Reports another</p>
              </div>
              <div className="p-5 rounded-xl border border-rose-500/20 bg-rose-500/5 text-center">
                <p className="text-sm text-rose-400 font-light mb-1">TikTok</p>
                <p className="text-xs text-gray-500 font-light">Reports something else</p>
              </div>
            </StaggerChildren>

            <ScrollReveal delay={100}>
              <p className="text-center text-gray-500 font-light text-sm mb-10">
                Each platform uses its own attribution logic.
              </p>
            </ScrollReveal>

            <ScrollReveal delay={150}>
              <div className="space-y-4 mb-12">
                <p className="text-gray-400 font-light text-center">
                  When performance shifts, you don&apos;t know:
                </p>
                <StaggerChildren className="space-y-3 max-w-md mx-auto" stagger={120}>
                  {[
                    "What actually drove it",
                    "Which channel created lift",
                    "Whether revenue would have happened anyway",
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-white/5 bg-white/[0.02]">
                      <div className="w-1.5 h-1.5 rounded-full bg-amber-500/70 flex-shrink-0" />
                      <span className="text-gray-400 font-light text-sm">{item}</span>
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

      {/* Section 3 - The Orbital System */}
      <section className="relative z-10 py-32 px-6 bg-gradient-to-b from-transparent via-blue-950/10 to-transparent">
        <div className="max-w-4xl mx-auto">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light text-center mb-12 tracking-tight">
              Orbital Models the System.
            </h2>
          </ScrollReveal>
          
          <ScrollReveal delay={100} className="text-center mb-16">
            <p className="text-xl text-gray-400 font-light mb-8">
              Growth isn&apos;t one metric. It&apos;s a system.
            </p>

            <StaggerChildren className="flex flex-wrap justify-center gap-3 mb-12" stagger={80}>
              {[
                { label: "Revenue", color: "border-amber-500/30 text-amber-400 bg-amber-500/5" },
                { label: "Traffic", color: "border-blue-500/30 text-blue-400 bg-blue-500/5" },
                { label: "Conversion", color: "border-emerald-500/30 text-emerald-400 bg-emerald-500/5" },
                { label: "Seasonality", color: "border-violet-500/30 text-violet-400 bg-violet-500/5" },
                { label: "Spend", color: "border-cyan-500/30 text-cyan-400 bg-cyan-500/5" },
                { label: "Promotions", color: "border-rose-500/30 text-rose-400 bg-rose-500/5" },
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
                Orbital connects your Shopify revenue and order data, adds channel spend 
                and key events, and quantifies how each force contributes to performance.
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
              <p className="text-sm text-white font-light">Modeled incremental impact</p>
            </div>
          </StaggerChildren>
        </div>
      </section>

      {/* Section 4 - What You Get */}
      <section className="relative z-10 py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light text-center mb-20 tracking-tight">
              Orbital Gives You:
            </h2>
          </ScrollReveal>

          <StaggerChildren className="grid md:grid-cols-2 lg:grid-cols-3 gap-6" stagger={100}>
            {[
              {
                title: "Incremental Revenue",
                subtitle: "by Channel",
                desc: "See which channels generate lift — not just credit.",
                icon: "💰",
              },
              {
                title: "Marginal ROI",
                subtitle: "Per Dollar Spent",
                desc: "Understand how additional spend affects revenue.",
                icon: "📈",
              },
              {
                title: "Promotion Lift",
                subtitle: "Measurement",
                desc: "Quantify the true impact of campaigns and events.",
                icon: "🎯",
              },
              {
                title: "Traffic & Conversion",
                subtitle: "Insight",
                desc: "See how growth flows through your funnel.",
                icon: "🔄",
              },
              {
                title: "Budget Reallocation",
                subtitle: "Simulator",
                desc: "Model how shifting spend changes outcomes.",
                icon: "⚖️",
              },
              {
                title: "Anomaly Alerts",
                subtitle: "Real-time",
                desc: "Know when performance deviates from expectation.",
                icon: "🚨",
              },
            ].map((feature, i) => (
              <div 
                key={i}
                className="feature-card group relative p-8 rounded-xl border border-white/10 bg-gradient-to-br from-white/5 to-transparent backdrop-blur-sm hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-300"
              >
                <div className="text-4xl mb-4 group-hover:scale-110 transition-transform duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-light mb-1">{feature.title}</h3>
                <p className="text-gray-500 text-sm font-light mb-3">{feature.subtitle}</p>
                <p className="text-gray-400 text-sm font-light leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </StaggerChildren>
        </div>
      </section>

      {/* Section 5 - Continuous Monitoring */}
      <section className="relative z-10 py-32 px-6 bg-gradient-to-b from-violet-950/10 to-transparent">
        <div className="max-w-5xl mx-auto text-center">
          <ScrollReveal>
            <h2 className="text-4xl md:text-5xl font-light mb-6 tracking-tight">
              Not Just Modeling.
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-blue-400">
                Continuous Intelligence.
              </span>
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={100}>
            <p className="text-xl text-gray-400 max-w-3xl mx-auto mb-6 font-light leading-relaxed">
              Performance changes every day.
            </p>
          </ScrollReveal>

          <ScrollReveal delay={200}>
            <p className="text-lg text-gray-400 max-w-3xl mx-auto font-light leading-relaxed">
              Orbital continuously monitors your business against statistically expected behavior.
              When revenue, traffic, or conversion deviates, you know immediately — and you know why.
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
              Understand the Forces
              <br />
              Behind Your Growth.
            </h2>
          </ScrollReveal>

          <ScrollReveal delay={100} distance={20} duration={700}>
            <p className="text-xl text-gray-400 font-light mb-12 max-w-2xl mx-auto leading-relaxed">
              Orbital is launching soon for Shopify merchants.
              <br />
              Join the waitlist for early access.
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
            <p>&copy; 2026 Orbital. Shopify-first causal intelligence.</p>
          </div>
        </footer>
      </ScrollReveal>
    </main>
  );
}
