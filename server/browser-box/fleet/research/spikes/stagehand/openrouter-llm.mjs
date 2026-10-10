// Stagehand v4 ClientLLM adapter for OpenRouter (OpenAI-compatible chat completions).
// Stagehand 4.2.0 has no model baseURL option and enumerates model ids per provider, so an
// OpenRouter model can only be reached through `model: { generate }`. In that mode the
// extension sends `llm.generate` JSON-RPC requests back to this process (see
// packages/sdk-ts/src/stagehand.ts:200-205), so LLM traffic leaves from here, not from the browser.
//
// Every call is counted and logged. The counter is the ground truth for "zero model calls".
// The API key is read from process.env only and never written anywhere.
import { appendFileSync } from "node:fs";

const OR_URL = "https://openrouter.ai/api/v1/chat/completions";

function toOpenAIContent(block) {
  if (block.type === "text") return { type: "text", text: block.text };
  if (block.type === "image")
    return { type: "image_url", image_url: { url: `data:${block.mimeType};base64,${block.data}` } };
  return { type: "text", text: JSON.stringify(block) };
}

function stripFences(text) {
  const m = text.match(/^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$/);
  return m ? { text: m[1], fenced: true } : { text, fenced: false };
}

export function makeOpenRouterLLM({
  model,
  logFile,
  promptDumpFile,
  reasoningEffort = "low",
  strictSchema = true,
  maxTokens = 2048,
}) {
  const stats = { calls: 0, costUsd: 0, inputTokens: 0, outputTokens: 0, reasoningTokens: 0, records: [] };

  async function generate(params) {
    stats.calls += 1;
    const callNo = stats.calls;
    const messages = [];
    if (params.systemPrompt) messages.push({ role: "system", content: params.systemPrompt });
    for (const m of params.messages) {
      const blocks = Array.isArray(m.content) ? m.content : [m.content];
      const parts = blocks.map(toOpenAIContent);
      messages.push({
        role: m.role,
        content: parts.length === 1 && parts[0].type === "text" ? parts[0].text : parts,
      });
    }
    const body = {
      model,
      messages,
      temperature: params.temperature ?? 0,
      reasoning: { effort: reasoningEffort },
      usage: { include: true },
      max_tokens: maxTokens,
      // Only route to providers that honour every parameter we send (json_schema, reasoning).
      provider: { require_parameters: true },
    };
    const structured = params.responseFormat?.type === "json_schema";
    if (structured) {
      body.response_format = {
        type: "json_schema",
        json_schema: {
          name: params.responseFormat.name,
          strict: strictSchema,
          schema: params.responseFormat.schema,
        },
      };
    }
    if (promptDumpFile) {
      appendFileSync(
        promptDumpFile,
        JSON.stringify({ callNo, name: params.responseFormat?.name ?? "text", body }) + "\n",
      );
    }
    const t0 = Date.now();
    const res = await fetch(OR_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${process.env.OPENROUTER_API_KEY}`,
        "x-title": "fleet-spike-stagehand",
      },
      body: JSON.stringify(body),
    });
    const ms = Date.now() - t0;
    const raw = await res.text();
    let json;
    try {
      json = JSON.parse(raw);
    } catch {
      json = undefined;
    }
    const rec = {
      callNo,
      name: params.responseFormat?.name ?? "text",
      model,
      httpStatus: res.status,
      ms,
      provider: json?.provider,
      finishReason: json?.choices?.[0]?.finish_reason,
      usage: json?.usage,
    };
    if (!res.ok || !json?.choices?.[0]) {
      rec.error = raw.slice(0, 600);
      stats.records.push(rec);
      if (logFile) appendFileSync(logFile, JSON.stringify(rec) + "\n");
      throw new Error(`OpenRouter HTTP ${res.status}: ${raw.slice(0, 300)}`);
    }
    const u = json.usage ?? {};
    stats.costUsd += Number(u.cost ?? 0);
    stats.inputTokens += u.prompt_tokens ?? 0;
    stats.outputTokens += u.completion_tokens ?? 0;
    stats.reasoningTokens += u.completion_tokens_details?.reasoning_tokens ?? 0;
    const text = json.choices[0].message?.content ?? "";
    const usage = {
      inputTokens: u.prompt_tokens ?? 0,
      outputTokens: u.completion_tokens ?? 0,
      totalTokens: u.total_tokens ?? (u.prompt_tokens ?? 0) + (u.completion_tokens ?? 0),
      ...(u.completion_tokens_details?.reasoning_tokens != null
        ? { reasoningTokens: u.completion_tokens_details.reasoning_tokens }
        : {}),
      ...(u.prompt_tokens_details?.cached_tokens != null
        ? { cachedInputTokens: u.prompt_tokens_details.cached_tokens }
        : {}),
    };
    if (!structured) {
      stats.records.push(rec);
      if (logFile) appendFileSync(logFile, JSON.stringify(rec) + "\n");
      return { role: "assistant", content: { type: "text", text }, outputFormat: "text", usage };
    }
    const { text: unfenced, fenced } = stripFences(text);
    rec.fenced = fenced;
    let structuredContent;
    try {
      structuredContent = JSON.parse(unfenced);
      rec.output = structuredContent;
    } catch (e) {
      rec.parseError = String(e).slice(0, 200);
      rec.rawText = text.slice(0, 400);
      stats.records.push(rec);
      if (logFile) appendFileSync(logFile, JSON.stringify(rec) + "\n");
      throw new Error(`model returned non-JSON for ${rec.name}: ${text.slice(0, 200)}`);
    }
    stats.records.push(rec);
    if (logFile) appendFileSync(logFile, JSON.stringify(rec) + "\n");
    return {
      role: "assistant",
      content: { type: "text", text: unfenced },
      outputFormat: "json_schema",
      structuredContent,
      usage,
    };
  }

  return { generate, stats };
}
