export type OrbitalGroup = "funnel" | "paidMedia" | "demand" | "events";

export interface OrbitalVariable {
  id: string;
  label: string;
  description: string;
  group: OrbitalGroup;
  color: string;
  orbitIndex: number;
  panelCopy: string[];
}

export interface OrbitalGroupConfig {
  radius: number;
  eccentricity: number;
  tiltXDeg: number;
  tiltZDeg: number;
  speed: number;
}

export const GROUP_CONFIG: Record<OrbitalGroup, OrbitalGroupConfig> = {
  funnel: { radius: 2.2, eccentricity: 0.85, tiltXDeg: 12, tiltZDeg: 5, speed: 0.12 },
  paidMedia: { radius: 3.2, eccentricity: 0.8, tiltXDeg: 25, tiltZDeg: -15, speed: 0.09 },
  demand: { radius: 4.2, eccentricity: 0.82, tiltXDeg: -18, tiltZDeg: 20, speed: 0.07 },
  events: { radius: 5.2, eccentricity: 0.75, tiltXDeg: 30, tiltZDeg: 10, speed: 0.05 },
};

export const VARIABLES: OrbitalVariable[] = [
  // Funnel
  {
    id: "sessions",
    label: "Sessions",
    description: "Total store visits that drive your top-of-funnel volume. Orbital isolates how traffic shifts affect revenue independently of conversion or spend changes.",
    group: "funnel",
    color: "#34d399",
    orbitIndex: 0,
    panelCopy: [
      "Tracks traffic contribution to revenue",
      "Separates demand shifts from paid lift",
      "Detects funnel instability over time",
      "Measures organic vs paid session mix",
    ],
  },
  {
    id: "conversion_rate",
    label: "Conversion Rate",
    description: "The percentage of sessions that become orders. Orbital measures how conversion efficiency changes over time and separates it from traffic quality shifts.",
    group: "funnel",
    color: "#2dd4bf",
    orbitIndex: 1,
    panelCopy: [
      "Measures checkout efficiency over time",
      "Detects conversion drops from site changes",
      "Separates funnel effects from traffic quality",
      "Quantifies impact on revenue per session",
    ],
  },
  {
    id: "aov",
    label: "AOV",
    description: "Average order value reflects how much customers spend per transaction. Orbital detects when pricing, product mix, or promotions shift basket size independently of volume.",
    group: "funnel",
    color: "#22d3ee",
    orbitIndex: 2,
    panelCopy: [
      "Tracks average order value trends",
      "Separates pricing effects from volume changes",
      "Detects mix shifts across product categories",
      "Models impact of promotions on basket size",
    ],
  },

  // Paid Media
  {
    id: "meta_spend",
    label: "Meta Spend",
    description: "Daily advertising spend on Meta platforms (Facebook, Instagram). Orbital estimates the true incremental revenue driven by each dollar, accounting for overlap with other channels.",
    group: "paidMedia",
    color: "#60a5fa",
    orbitIndex: 0,
    panelCopy: [
      "Estimates incremental lift from Meta ads",
      "Adjusts for seasonality and baseline demand",
      "Accounts for channel overlap with Google",
      "Models diminishing returns at scale",
      "Simulates marginal ROI per dollar",
    ],
  },
  {
    id: "google_spend",
    label: "Google Spend",
    description: "Daily advertising spend across Google (Search, Shopping, Display). Orbital separates branded demand from true paid lift and models how additional spend translates to revenue.",
    group: "paidMedia",
    color: "#818cf8",
    orbitIndex: 1,
    panelCopy: [
      "Estimates incremental lift from Google ads",
      "Separates branded from non-branded impact",
      "Accounts for channel overlap with Meta",
      "Models diminishing returns at scale",
      "Simulates marginal ROI per dollar",
    ],
  },
  {
    id: "tiktok_spend",
    label: "TikTok Spend",
    description: "Daily advertising spend on TikTok. Orbital accounts for delayed attribution and awareness effects to measure the real revenue contribution beyond what the platform reports.",
    group: "paidMedia",
    color: "#a78bfa",
    orbitIndex: 2,
    panelCopy: [
      "Estimates incremental lift from TikTok ads",
      "Adjusts for awareness vs conversion effects",
      "Accounts for delayed attribution windows",
      "Models diminishing returns at scale",
      "Simulates marginal ROI per dollar",
    ],
  },

  // Demand
  {
    id: "seasonality",
    label: "Seasonality",
    description: "Recurring patterns like day-of-week cycles, holidays, and peak shopping periods. Orbital separates these natural demand rhythms so your paid media isn't credited for seasonal lifts.",
    group: "demand",
    color: "#fbbf24",
    orbitIndex: 0,
    panelCopy: [
      "Captures weekly and holiday demand patterns",
      "Separates baseline from paid lift",
      "Prevents over-attribution during peak periods",
      "Models day-of-week revenue variation",
    ],
  },
  {
    id: "trend",
    label: "Trend",
    description: "The long-term growth or decline trajectory of your store. Orbital establishes this baseline so it can accurately measure what spend and events add on top of organic momentum.",
    group: "demand",
    color: "#f59e0b",
    orbitIndex: 1,
    panelCopy: [
      "Measures long-term growth or decline",
      "Separates organic trajectory from paid effects",
      "Establishes the revenue baseline over time",
      "Detects structural shifts in demand",
    ],
  },
  {
    id: "brand_demand",
    label: "Brand Demand",
    description: "Organic revenue driven by brand recognition, word-of-mouth, and repeat customers. Orbital prevents crediting paid channels for sales that would have happened regardless.",
    group: "demand",
    color: "#fb923c",
    orbitIndex: 2,
    panelCopy: [
      "Captures organic brand awareness effects",
      "Separates word-of-mouth from paid traffic",
      "Tracks brand equity contribution to revenue",
      "Prevents crediting paid channels for organic lift",
    ],
  },

  // Events & Shocks
  {
    id: "promotions",
    label: "Promotions",
    description: "Sales events, discount campaigns, and flash sales that create temporary revenue spikes. Orbital quantifies the true incremental lift and detects whether promotions cannibalize future demand.",
    group: "events",
    color: "#f87171",
    orbitIndex: 0,
    panelCopy: [
      "Measures event-driven lift precisely",
      "Separates temporary spikes from baseline growth",
      "Quantifies true incremental impact of sales",
      "Detects cannibalization of future revenue",
    ],
  },
  {
    id: "product_launch",
    label: "Product Launch",
    description: "New product releases that shift revenue mix and create launch halo effects. Orbital separates the launch bump from sustained demand to measure real product-market impact.",
    group: "events",
    color: "#fb7185",
    orbitIndex: 1,
    panelCopy: [
      "Quantifies revenue impact of new products",
      "Separates launch halo from sustained demand",
      "Measures cross-product cannibalization",
      "Tracks adoption curve over time",
    ],
  },
  {
    id: "inventory",
    label: "Inventory",
    description: "Stockouts and low inventory suppress revenue even when demand is strong. Orbital flags supply-side constraints so you don't mistake lost sales for declining demand.",
    group: "events",
    color: "#e879f9",
    orbitIndex: 2,
    panelCopy: [
      "Detects revenue loss from stockouts",
      "Measures suppressed demand during low inventory",
      "Flags supply-side constraints on growth",
      "Separates supply effects from demand shifts",
    ],
  },
  {
    id: "algorithm_changes",
    label: "Algorithm Changes",
    description: "Platform algorithm updates on Meta, Google, or TikTok can suddenly shift ad efficiency. Orbital detects these external shocks so you don't misattribute the impact to your own strategy.",
    group: "events",
    color: "#c084fc",
    orbitIndex: 3,
    panelCopy: [
      "Detects platform algorithm shifts",
      "Flags sudden efficiency changes in paid media",
      "Separates external shocks from internal changes",
      "Prevents misattribution of platform-driven variance",
    ],
  },
];
