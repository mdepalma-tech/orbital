# 🎨 Orbital Visual Style Guide

## Color Palette

### Primary Colors
```
Background Black:     #0B0F14
Text White:           #FFFFFF
Text Gray:            #9CA3AF
Text Muted:           #6B7280
```

### Accent Colors
```
Electric Blue:        #3B82F6  (Primary brand color)
Soft Violet:          #8B5CF6  (Secondary accent)
Muted Amber:          #F59E0B  (Revenue emphasis)
Cyan:                 #06B6D4  (Traffic/data)
Emerald:              #10B981  (Positive metrics)
```

### Opacity Layers
```
Border:               rgba(255, 255, 255, 0.10)
Glass Card:           rgba(255, 255, 255, 0.05)
Hover Glow:           rgba(59, 130, 246, 0.50)
Subtle Shadow:        rgba(59, 130, 246, 0.20)
```

---

## Typography

### Font Family
**Inter** (Google Fonts)
- Light (300) - Body text, descriptions
- Regular (400) - Standard text
- Medium (500) - Emphasis
- Semi-Bold (600) - Headings

### Type Scale
```
Hero Title:           text-5xl md:text-7xl (48px → 72px)
Section Title:        text-4xl md:text-5xl (36px → 48px)
Subheading:           text-xl md:text-2xl (20px → 24px)
Body Large:           text-lg md:text-xl (18px → 20px)
Body:                 text-base (16px)
Small:                text-sm (14px)
```

### Tracking
```
Wide:                 tracking-wider (0.05em)
Tight:                tracking-tight (-0.025em)
```

---

## Spacing System

### Section Padding
```
Vertical:             py-32 (128px)
Horizontal:           px-6 (24px)
```

### Container Max Width
```
Standard:             max-w-5xl (1024px)
Wide:                 max-w-6xl (1152px)
Extra Wide:           max-w-7xl (1280px)
```

### Gap Sizes
```
Small:                gap-4 (16px)
Medium:               gap-6 (24px)
Large:                gap-12 (48px)
Extra Large:          gap-20 (80px)
```

---

## Animation Timing

### Durations
```
Fast:                 150ms
Standard:             300ms
Slow:                 600ms
Orbital Rotation:     20-35s
Pulse:                4s
```

### Easing
```
Default:              cubic-bezier(0.4, 0, 0.2, 1)
Linear:               linear
Ease-in-out:          ease-in-out
```

---

## Component Patterns

### Glass Card
```css
background: linear-gradient(to-br, rgba(255,255,255,0.05), transparent)
border: 1px solid rgba(255,255,255,0.10)
backdrop-filter: blur(sm)
border-radius: 0.75rem (12px)
```

### Primary CTA Button
```css
background: linear-gradient(to-r, #3B82F6, #8B5CF6)
padding: 1rem 2rem (16px 32px)
border-radius: 0.5rem (8px)
box-shadow: 0 0 30px rgba(59, 130, 246, 0.5) on hover
transition: all 300ms
hover: scale(1.05)
```

### Secondary CTA Button
```css
border: 1px solid rgba(255,255,255,0.20)
padding: 1rem 2rem (16px 32px)
border-radius: 0.5rem (8px)
background: transparent
hover: rgba(255,255,255,0.05)
transition: all 300ms
```

---

## Icon Usage

### Emoji Icons (Current)
```
🔌 Connect/Integration
📊 Data/Analytics
🧠 Intelligence/AI
💰 Revenue/Money
📈 Growth/Metrics
🎯 Targeting/Precision
🔄 Conversion/Cycle
⚖️ Balance/Optimization
🚨 Alerts/Monitoring
```

### Icon Guidelines
- Size: text-3xl to text-4xl (30-36px)
- Centered in containers
- Scale on hover: scale(1.1)
- Transition: 300ms

---

## Orbital System Specifications

### Core Element
```
Size:                 64px diameter (w-16 h-16)
Glow Size:            128px diameter (w-32 h-32)
Background:           Gradient blue-400 → violet-400 → blue-500
Shadow:               0 0 30px rgba(59, 130, 246, 0.5)
Animation:            Pulse 4s infinite
```

### Orbit Rings
```
Orbit 1:              280px diameter, 20s rotation
Orbit 2:              350px diameter, 25s rotation reverse
Orbit 3:              420px diameter, 30s rotation
Orbit 4:              490px diameter, 35s rotation reverse
Border:               1px solid rgba(255, 255, 255, 0.05)
```

### Spheres
```
Size:                 24px diameter
Border:               1px solid rgba(255, 255, 255, 0.2)
Backdrop:             blur(sm)
Glow:                 box-shadow: 0 0 20px currentColor
```

---

## Grid System

### Responsive Breakpoints
```
Mobile:               < 768px (single column)
Tablet:               768px - 1024px (2 columns)
Desktop:              > 1024px (3 columns)
```

### Feature Grid
```
Mobile:               grid-cols-1
Tablet:               md:grid-cols-2
Desktop:              lg:grid-cols-3
Gap:                  gap-6 (24px)
```

---

## Background Effects

### Starfield
```
Type:                 Radial gradient particles
Opacity:              0.1 - 0.15
Animation:            60s linear infinite drift
Count:                7 particles
```

### Grid Plane
```
Line Color:           rgba(59, 130, 246, 0.03)
Grid Size:            100px × 100px
Transform:            perspective(1000px) rotateX(60deg)
Opacity:              0.3
Mask:                 Linear gradient fade
```

### Depth Gradient
```
Background:           linear-gradient(to-b, #0B0F14, #0d1219, #0B0F14)
```

---

## State Interactions

### Hover States
```
Cards:                translateY(-4px) + border color change
Buttons:              shadow glow + scale(1.05)
Icons:                scale(1.1)
Feature Cards:        Radial glow at cursor position
```

### Focus States
```
Inputs:               Blue ring (2px)
Buttons:              Blue glow shadow
```

### Active States
```
Links:                Text color to blue-400
Buttons:              Scale(0.98)
```

---

## Accessibility

### Contrast Ratios
```
Body Text:            WCAG AAA (7:1+)
UI Text:              WCAG AA (4.5:1+)
```

### Motion
```
Slow animations only
No flashing
respects prefers-reduced-motion
```

---

## Don'ts ❌

- ❌ No neon colors (too crypto-esque)
- ❌ No fast animations (< 1s for decorative elements)
- ❌ No exclamation marks in copy
- ❌ No hype language ("10x", "revolutionary", etc.)
- ❌ No excessive bolding
- ❌ No heavy fonts (max 600 weight)
- ❌ No busy patterns
- ❌ No bright white (#FFF) - use off-white
- ❌ No harsh shadows
- ❌ No conflicting metaphors

---

## Do's ✅

- ✅ Slow, purposeful motion
- ✅ Generous negative space
- ✅ Subtle depth cues
- ✅ Mathematical precision
- ✅ Executive-level tone
- ✅ Glass morphism (subtle)
- ✅ Gradient accents
- ✅ Consistent metaphors
- ✅ Light font weights (300-400)
- ✅ Calm color transitions

---

## Brand Voice

### Tone Attributes
- Calm (not excited)
- Analytical (not salesy)
- Precise (not vague)
- Confident (not boastful)
- Technical (not jargon-heavy)

### Example Headlines
✅ "See What Actually Moves Your Revenue"
✅ "Orbital Models the System"
✅ "Real Modeling. Transparent Confidence."

### Example Body Copy
✅ "Quantifying incremental impact across revenue, traffic, and conversion using real statistical modeling."
✅ "When performance shifts, you don't know why."
✅ "Orbital monitors your performance against statistically expected behavior."

---

## Implementation Files

```
/app/page.tsx         → Main landing page structure
/app/globals.css      → Custom animations & styles
/app/layout.tsx       → Font setup, metadata, theme config
/.env.local           → Supabase credentials
```

---

**Last Updated**: Feb 18, 2026
**Design System Version**: 1.0
**Status**: Production Ready
