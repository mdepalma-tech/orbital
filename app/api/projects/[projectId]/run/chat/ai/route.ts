import { NextRequest } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSupabaseServiceClient } from "@/lib/supabase/service";
import Anthropic from "@anthropic-ai/sdk";

// ── Rate limiter ────────────────────────────────────────────────────────
const RATE_LIMIT = {
  windowMs: 60_000,      // 1 minute window
  maxRequests: 10,        // max requests per user per window
  maxDaily: 100,          // max requests per user per day
};

interface RateBucket {
  count: number;
  resetAt: number;
}

const rateBuckets = new Map<string, RateBucket>();
const dailyBuckets = new Map<string, RateBucket>();

function checkRateLimit(userId: string): { allowed: boolean; retryAfter?: number } {
  const now = Date.now();

  // Per-minute check
  const minuteKey = userId;
  const minute = rateBuckets.get(minuteKey);
  if (!minute || now >= minute.resetAt) {
    rateBuckets.set(minuteKey, { count: 1, resetAt: now + RATE_LIMIT.windowMs });
  } else {
    if (minute.count >= RATE_LIMIT.maxRequests) {
      return { allowed: false, retryAfter: Math.ceil((minute.resetAt - now) / 1000) };
    }
    minute.count++;
  }

  // Daily check
  const dayStart = new Date();
  dayStart.setHours(0, 0, 0, 0);
  const dayEnd = dayStart.getTime() + 86_400_000;
  const dailyKey = userId;
  const daily = dailyBuckets.get(dailyKey);
  if (!daily || now >= daily.resetAt) {
    dailyBuckets.set(dailyKey, { count: 1, resetAt: dayEnd });
  } else {
    if (daily.count >= RATE_LIMIT.maxDaily) {
      return { allowed: false, retryAfter: Math.ceil((daily.resetAt - now) / 1000) };
    }
    daily.count++;
  }

  return { allowed: true };
}

// Cleanup stale buckets every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [key, bucket] of rateBuckets) {
    if (now >= bucket.resetAt) rateBuckets.delete(key);
  }
  for (const [key, bucket] of dailyBuckets) {
    if (now >= bucket.resetAt) dailyBuckets.delete(key);
  }
}, 300_000);

// ── Global token budget (kill switch) ───────────────────────────────────
// Claude Haiku pricing: $0.25/1M input, $1.25/1M output
// 500k tokens/day ≈ worst case ~$0.75/day
const TOKEN_BUDGET = {
  maxDailyTokens: 500_000,
  maxOutputTokens: 512,         // per request — keeps responses short & cheap
  maxInputChars: 12_000,        // truncate pipeline context to ~3k tokens
  maxHistoryTurns: 6,           // keep last 6 messages
};

let dailyTokens = { count: 0, resetAt: 0 };

function trackTokens(used: number): boolean {
  const now = Date.now();
  const dayStart = new Date();
  dayStart.setHours(0, 0, 0, 0);
  const dayEnd = dayStart.getTime() + 86_400_000;

  if (now >= dailyTokens.resetAt) {
    dailyTokens = { count: used, resetAt: dayEnd };
    return true;
  }
  if (dailyTokens.count + used > TOKEN_BUDGET.maxDailyTokens) {
    return false;
  }
  dailyTokens.count += used;
  return true;
}

function checkTokenBudget(): boolean {
  const now = Date.now();
  if (now >= dailyTokens.resetAt) return true;
  return dailyTokens.count < TOKEN_BUDGET.maxDailyTokens;
}

// ── System prompt ───────────────────────────────────────────────────────
const SYSTEM_PROMPT = `You are Orbital's modeling assistant — an expert in Media Mix Modeling (MMM), econometrics, and marketing analytics. You help marketers understand their model results in plain, actionable language.

You have access to the full pipeline output: diagnostics, model coefficients, confidence scores, out-of-sample metrics, counterfactual analysis (incremental revenue & marginal ROI per channel), and anomaly detection.

Guidelines:
- Be concise and direct. Lead with the insight, not the methodology.
- Use **bold** for key numbers and channel names.
- When discussing coefficients or ROI, frame them in business terms (e.g. "For every $1 spent on Meta, you generated ~$X in incremental revenue").
- If confidence is low or medium, explain specifically what drove the downgrade and what the user can do about it.
- If asked about a specific channel, focus on that channel's coefficient, ROI, adstock decay, and statistical significance.
- If the model has negative spend coefficients, flag this clearly as a data quality concern.
- Never invent data — only reference what's in the pipeline context provided.
- Keep responses under 200 words unless the user asks for a deep dive.`;

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ projectId: string }> }
) {
  const { projectId } = await context.params;
  if (!projectId) {
    return new Response(JSON.stringify({ error: "Missing projectId" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const apiKey = process.env.AI_API_KEY?.trim();
  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: "AI_API_KEY not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }

  // Auth check
  const auth = await createClient();
  const {
    data: { user },
  } = await auth.auth.getUser();
  if (!user) {
    return new Response(JSON.stringify({ error: "Not authenticated" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Daily token budget check (kill switch)
  if (!checkTokenBudget()) {
    return new Response(
      JSON.stringify({ error: "Daily AI token budget exhausted. Resets at midnight." }),
      { status: 429, headers: { "Content-Type": "application/json" } }
    );
  }

  // Rate limit check
  const rateCheck = checkRateLimit(user.id);
  if (!rateCheck.allowed) {
    return new Response(
      JSON.stringify({
        error: `Rate limit exceeded. Try again in ${rateCheck.retryAfter}s.`,
      }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(rateCheck.retryAfter),
        },
      }
    );
  }

  // Project access check
  const supabase = getSupabaseServiceClient();
  const { data: project } = await supabase
    .from("projects")
    .select("id")
    .eq("id", projectId)
    .eq("user_id", user.id)
    .single();
  if (!project) {
    return new Response(JSON.stringify({ error: "Project not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  let body: {
    message: string;
    pipelineResults?: Record<string, unknown>[];
    summary?: Record<string, unknown>;
    chatHistory?: { role: string; content: string }[];
  };
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const userMessage = body.message?.trim();
  if (!userMessage) {
    return new Response(JSON.stringify({ error: "message is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  // Build context from pipeline results (truncated to budget)
  let pipelineContext = "";
  if (body.summary) {
    pipelineContext += `\n## Model Summary\n${JSON.stringify(body.summary, null, 2)}\n`;
  }
  if (body.pipelineResults && body.pipelineResults.length > 0) {
    pipelineContext += `\n## Pipeline Step Results\n`;
    for (const r of body.pipelineResults) {
      pipelineContext += `### ${r.title} (${r.status})\n${JSON.stringify(r.metrics, null, 2)}\n\n`;
    }
  }
  // Truncate context to keep input tokens in check
  if (pipelineContext.length > TOKEN_BUDGET.maxInputChars) {
    pipelineContext = pipelineContext.slice(0, TOKEN_BUDGET.maxInputChars) + "\n...[truncated]";
  }

  // Build conversation history for Claude
  const messages: { role: "user" | "assistant"; content: string }[] = [];
  if (body.chatHistory) {
    const recent = body.chatHistory.slice(-TOKEN_BUDGET.maxHistoryTurns);
    for (const msg of recent) {
      if (msg.role === "user" || msg.role === "assistant") {
        messages.push({ role: msg.role, content: msg.content });
      }
    }
  }
  messages.push({ role: "user", content: userMessage });

  // Call Claude Haiku with streaming
  const anthropic = new Anthropic({ apiKey });

  try {
    const stream = await anthropic.messages.stream({
      model: "claude-haiku-4-5-20251001",
      max_tokens: TOKEN_BUDGET.maxOutputTokens,
      system: SYSTEM_PROMPT + (pipelineContext ? `\n\n---\nPIPELINE CONTEXT:\n${pipelineContext}` : ""),
      messages,
    });

    const encoder = new TextEncoder();
    const readableStream = new ReadableStream({
      async start(controller) {
        try {
          for await (const event of stream) {
            if (
              event.type === "content_block_delta" &&
              event.delta.type === "text_delta"
            ) {
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({ text: event.delta.text })}\n\n`)
              );
            }
          }

          // Track token usage
          const finalMessage = await stream.finalMessage();
          const totalTokens =
            (finalMessage.usage?.input_tokens ?? 0) +
            (finalMessage.usage?.output_tokens ?? 0);
          if (!trackTokens(totalTokens)) {
            console.warn(`[AI Chat] Daily token budget exhausted: ${dailyTokens.count} tokens used`);
          }

          controller.enqueue(encoder.encode(`data: [DONE]\n\n`));
          controller.close();
        } catch (err) {
          controller.enqueue(
            encoder.encode(
              `data: ${JSON.stringify({ error: err instanceof Error ? err.message : "Stream error" })}\n\n`
            )
          );
          controller.close();
        }
      },
    });

    return new Response(readableStream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({
        error: err instanceof Error ? err.message : "Claude API error",
      }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
