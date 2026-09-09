import type { DecisionContext } from "../contracts/index.js";
import type { LlmDecisionGenerator } from "../planner/llmPlanner.js";

const DECISION_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    action: { type: "string", enum: ["purchase", "skip", "clarify"] },
    candidate_id: { type: ["string", "null"] },
    requested_tier: { type: "string", enum: ["preview", "full", "auto"] },
    budget_usdc: { type: "number", minimum: 0 },
    max_price_usdc: { type: "number", minimum: 0 },
    reason: { type: "string" },
    rejected_candidate_ids: {
      type: "array",
      maxItems: 25,
      items: { type: "string" },
    },
  },
  required: [
    "action",
    "candidate_id",
    "requested_tier",
    "budget_usdc",
    "max_price_usdc",
    "reason",
    "rejected_candidate_ids",
  ],
} as const;

interface OpenAiResponse {
  choices?: Array<{
    message?: { content?: string | null; refusal?: string | null };
  }>;
  error?: { message?: string };
}

export type LlmProvider = "openai" | "gemini" | "groq" | "openrouter" | "ollama";

export interface OpenAiDecisionGeneratorOptions {
  provider?: LlmProvider;
  apiKey?: string;
  model?: string;
  baseUrl?: string;
}

export class OpenAiDecisionGenerator implements LlmDecisionGenerator {
  private readonly provider: LlmProvider;
  private readonly apiKey: string;
  private readonly model: string;
  private readonly baseUrl: string;

  constructor(options: OpenAiDecisionGeneratorOptions = {}) {
    const provider = (options.provider || process.env.QMA_LLM_PROVIDER || "openai").toLowerCase().trim();
    if (!["openai", "gemini", "groq", "openrouter", "ollama"].includes(provider)) {
      throw new Error(`Unsupported LLM provider '${provider}'.`);
    }
    this.provider = provider as LlmProvider;

    // Resolve apiKey
    let resolvedKey = options.apiKey || process.env.QMA_LLM_API_KEY || "";
    if (!resolvedKey) {
      if (this.provider === "openai") {
        resolvedKey = process.env.OPENAI_API_KEY || "";
      } else if (this.provider === "gemini") {
        resolvedKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || "";
      } else if (this.provider === "groq") {
        resolvedKey = process.env.GROQ_API_KEY || "";
      } else if (this.provider === "openrouter") {
        resolvedKey = process.env.OPENROUTER_API_KEY || process.env.OPENROUTER_API || "";
      }
    }
    this.apiKey = resolvedKey;

    if (this.provider !== "ollama" && !this.apiKey) {
      throw new Error(`API key is required for LLM provider: ${this.provider}`);
    }

    // Resolve model
    let defaultModel = "gpt-4o-mini";
    if (this.provider === "gemini") defaultModel = "gemini-2.5-flash";
    else if (this.provider === "groq") defaultModel = "llama-3.3-70b-versatile";
    else if (this.provider === "openrouter") defaultModel = "google/gemini-2.5-flash";
    else if (this.provider === "ollama") defaultModel = "qwen2.5:7b";
    this.model = options.model || process.env.QMA_LLM_MODEL || defaultModel;

    // Resolve baseUrl
    let defaultBaseUrl = "https://api.openai.com/v1";
    if (this.provider === "gemini") defaultBaseUrl = "https://generativelanguage.googleapis.com/v1beta/openai";
    else if (this.provider === "groq") defaultBaseUrl = "https://api.groq.com/openai/v1";
    else if (this.provider === "openrouter") defaultBaseUrl = "https://openrouter.ai/api/v1";
    else if (this.provider === "ollama") defaultBaseUrl = "http://localhost:11434/v1";
    this.baseUrl = options.baseUrl || process.env.QMA_LLM_BASE_URL || defaultBaseUrl;
  }

  async generateDecision(input: {
    systemPrompt: string;
    userPrompt: string;
    context: DecisionContext;
  }): Promise<unknown> {
    const url = `${this.baseUrl.replace(/\/$/, "")}/chat/completions`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.apiKey) {
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    if (this.provider === "openrouter") {
      headers["HTTP-Referer"] = "https://github.com/hoanlv214/qma";
      headers["X-Title"] = "QMA Agent";
    }

    // Determine response format
    let responseFormat: any;
    if (["openai", "gemini", "groq"].includes(this.provider)) {
      responseFormat = {
        type: "json_schema",
        json_schema: {
          name: "qma_agent_decision",
          strict: true,
          schema: DECISION_SCHEMA,
        },
      };
    } else {
      responseFormat = {
        type: "json_object",
      };
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({
        model: this.model,
        messages: [
          { role: "system", content: input.systemPrompt },
          { role: "user", content: input.userPrompt },
        ],
        response_format: responseFormat,
      }),
      signal: AbortSignal.timeout(30_000),
    });

    const data = (await response.json()) as OpenAiResponse;
    if (!response.ok) {
      throw new Error(`LLM provider ${this.provider} returned HTTP ${response.status}: ${data.error?.message || "unknown error"}`);
    }

    const message = data.choices?.[0]?.message;
    if (message?.refusal) throw new Error(`LLM provider refused the decision: ${message.refusal}`);
    if (!message?.content) throw new Error("LLM provider returned an empty decision.");
    return message.content;
  }
}

export { OpenAiDecisionGenerator as OpenAiCompatibleDecisionGenerator };
