import assert from "node:assert/strict";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { zstdDecompressSync } from "node:zlib";

import {
  fauxAssistantMessage,
  fauxText,
  fauxThinking,
  fauxToolCall,
  type AssistantMessageEvent,
} from "@earendil-works/pi-ai";

import { FileCredentialStore } from "../src/credentials.js";
import { parseStreamRequest, type GatewayStreamRequest } from "../src/contracts.js";
import {
  classifyProviderError,
  fingerprintProviderContractError,
} from "../src/provider-errors.js";
import {
  createPiAiRuntime,
  GatewayRuntimeError,
  type GatewayRuntime,
} from "../src/runtime.js";
import { createGatewayServer } from "../src/server.js";

const INTERNAL_TOKEN = "a".repeat(32);

test("health, catalog, and streams require the internal caller token", async (t) => {
  const directory = await mkdtemp(join(tmpdir(), "dm-gateway-"));
  const runtime = createPiAiRuntime({
    credentials: new FileCredentialStore(join(directory, "credentials.json")),
    fauxResponses: [
      fauxAssistantMessage([
        fauxThinking("Synthetic reasoning"),
        fauxText("Synthetic answer"),
        fauxToolCall("set_brief", { rooms: 3 }, { id: "call_synthetic" }),
      ]),
    ],
  });
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const health = await fetch(`${baseUrl}/health`);
  assert.equal(health.status, 401);

  const authorizedHealth = await fetch(`${baseUrl}/health`, { headers: authorization() });
  assert.equal(authorizedHealth.status, 200);
  assert.deepEqual(await authorizedHealth.json(), {
    status: "ok",
    gateway_version: "0.1.0",
    credential_store: "ready",
  });

  assert.equal((await fetch(`${baseUrl}/v1/providers`)).status, 401);
  const catalog = await fetch(`${baseUrl}/v1/providers`, { headers: authorization() });
  assert.equal(catalog.status, 200);
  const catalogText = await catalog.text();
  assert.match(catalogText, /faux-deterministic-v1/);
  assert.match(catalogText, /github-copilot/);
  assert.match(catalogText, /openai-codex/);
  assert.doesNotMatch(catalogText, /access|refresh|credential/i);
  const catalogDocument = JSON.parse(catalogText) as {
    providers: { id: string; models: { capabilities: string[] }[] }[];
  };
  const apiKeyOpenAi = catalogDocument.providers.find((provider) => provider.id === "openai");
  const subscriptionCodex = catalogDocument.providers.find((provider) => provider.id === "openai-codex");
  assert.ok(apiKeyOpenAi?.models.every((model) => model.capabilities.includes("hard_output_token_limit")));
  assert.ok(subscriptionCodex?.models.every((model) => !model.capabilities.includes("hard_output_token_limit")));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest()),
  });
  assert.equal(stream.status, 200);
  const events = await stream.text();
  assert.match(events, /event: thinking_delta/);
  assert.match(events, /event: text_delta/);
  assert.match(events, /event: tool_call/);
  assert.match(events, /"id":"call_synthetic"/);
  assert.match(events, /event: usage/);
  assert.match(events, /"input_tokens":\d+,"output_tokens":\d+/);
  assert.match(events, /event: done/);
});

test("the pinned Codex transport omits unsupported output-limit fields", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dm-gateway-"));
  const credentials = new FileCredentialStore(join(directory, "credentials.json"));
  await credentials.modify("openai-codex", async () => ({
    type: "oauth",
    access: syntheticCodexAccessToken(),
    refresh: "synthetic-refresh-token",
    expires: Number.MAX_SAFE_INTEGER,
  }));

  let capturedPayload: Record<string, unknown> | undefined;
  const providerFetch: typeof fetch = async (_input, init) => {
    const headers = new Headers(init?.headers);
    const body = init?.body;
    assert.ok(typeof body === "string" || body instanceof Uint8Array);
    const encoded = Buffer.from(body);
    const decoded = headers.get("content-encoding") === "zstd"
      ? zstdDecompressSync(encoded)
      : encoded;
    capturedPayload = JSON.parse(decoded.toString("utf8")) as Record<string, unknown>;
    return new Response(JSON.stringify({ error: { message: "private rejection detail" } }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  };
  const runtime = createPiAiRuntime({
    credentials,
    providerFetch,
    providerTransport: "sse",
  });
  const request = parseStreamRequest(fauxStreamRequest({
    provider: "openai-codex",
    model: "gpt-5.4",
    output_token_limit: 321,
    provider_contract_diagnostics: true,
  }));

  await assert.rejects(
    async () => {
      for await (const _event of runtime.stream(request, new AbortController().signal)) {
        // The synthetic response is consumed only to exercise the transport boundary.
      }
    },
    (error: unknown) => {
      assert.ok(error instanceof GatewayRuntimeError);
      assert.equal(error.code, "provider_request_rejected");
      assert.deepEqual(error.contractDiagnostic, {
        http_status: 400,
        mentions_max_output_tokens: false,
        parameter_rejection: false,
        max_output_tokens_rejection: false,
      });
      assert.doesNotMatch(error.message, /private rejection detail/);
      return true;
    },
  );

  assert.equal(capturedPayload?.model, "gpt-5.4");
  assert.equal(capturedPayload?.max_output_tokens, undefined);
  assert.equal(capturedPayload?.max_tokens, undefined);
  assert.equal(capturedPayload?.max_completion_tokens, undefined);
});

test("the standard OpenAI API transport serializes its documented hard output limit", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dm-gateway-"));
  const credentials = new FileCredentialStore(join(directory, "credentials.json"));
  await credentials.modify("openai", async () => ({
    type: "api_key",
    key: "synthetic-openai-api-key",
  }));

  let capturedPayload: Record<string, unknown> | undefined;
  const providerFetch: typeof fetch = async (_input, init) => {
    const body = init?.body;
    assert.ok(typeof body === "string" || body instanceof Uint8Array);
    capturedPayload = JSON.parse(Buffer.from(body).toString("utf8")) as Record<string, unknown>;
    return new Response(JSON.stringify({ error: { message: "Unsupported parameter: synthetic_field; private detail" } }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  };
  const runtime = createPiAiRuntime({ credentials, providerFetch });
  const request = parseStreamRequest(fauxStreamRequest({
    provider: "openai",
    model: "gpt-5.4",
    output_token_limit: 654,
  }));

  await assert.rejects(
    async () => {
      for await (const _event of runtime.stream(request, new AbortController().signal)) {
        // The synthetic response is consumed only to exercise the transport boundary.
      }
    },
    (error: unknown) => {
      assert.ok(error instanceof GatewayRuntimeError);
      assert.equal(error.code, "provider_request_rejected");
      assert.doesNotMatch(error.message, /synthetic_field|private detail/);
      return true;
    },
  );

  assert.equal(capturedPayload?.model, "gpt-5.4");
  assert.equal(capturedPayload?.max_output_tokens, 654);
});

test("normalized transcript roles preserve tool continuity without user-message flattening", () => {
  const request = parseStreamRequest(fauxStreamRequest({
    messages: [
      { role: "user", content: "Create a synthetic dungeon brief." },
      {
        role: "assistant",
        content: "",
        tool_calls: [{ tool_name: "set_brief", call_id: "call_synthetic", arguments: { rooms: 3 } }],
        opaque_continuity_signatures: ["opaque-provider-signature"],
      },
      {
        role: "tool_result",
        content: "{\"status\":\"ok\"}",
        tool_call_id: "call_synthetic",
        tool_name: "set_brief",
        is_error: false,
      },
    ],
  }));

  assert.deepEqual(request.messages.map((message) => message.role), ["user", "assistant", "tool_result"]);
  assert.equal(request.providerContractDiagnostics, false);
  assert.equal(request.messages[1]?.role === "assistant" && request.messages[1].toolCalls[0]?.id, "call_synthetic");
  assert.equal(request.messages[2]?.role === "tool_result" && request.messages[2].toolCallId, "call_synthetic");
  assert.throws(() => parseStreamRequest(fauxStreamRequest({ messages: [{ role: "tool_result", content: "x" }] })));
  assert.throws(() => parseStreamRequest(fauxStreamRequest({ provider_contract_diagnostics: "yes" })));
});

test("constrained JSON-schema sampling is forwarded as prefer and remains safe for faux fallback", async () => {
  const parsed = parseStreamRequest(fauxStreamRequest({
    tools: [{
      name: "set_brief",
      description: "Set a deterministic dungeon brief.",
      parameters: { type: "object", properties: { rooms: { type: "integer" } } },
      constrained_sampling: "prefer",
    }],
  }));
  assert.equal(parsed.tools[0]?.constrainedSampling, "prefer");

  const directory = await mkdtemp(join(tmpdir(), "dm-gateway-"));
  const runtime = createPiAiRuntime({
    credentials: new FileCredentialStore(join(directory, "credentials.json")),
    fauxResponses: [fauxAssistantMessage([fauxToolCall("set_brief", { rooms: 3 })])],
  });
  const events: AssistantMessageEvent[] = [];
  for await (const event of runtime.stream(parsed, new AbortController().signal)) events.push(event);
  assert.ok(events.some((event) => event.type === "toolcall_end"));
});

test("credential persistence serializes writes, uses restrictive permissions, and never exposes tokens", async () => {
  const directory = await mkdtemp(join(tmpdir(), "dm-gateway-"));
  const path = join(directory, "credentials.json");
  const store = new FileCredentialStore(path);
  await Promise.all([
    store.modify("openai-codex", async () => ({
      type: "oauth",
      access: "access-token-must-not-leak",
      refresh: "refresh-token-must-not-leak",
      expires: 1,
    })),
    store.modify("openai-codex", async (current) => ({
      ...(current ?? {
        type: "oauth" as const,
        access: "access-token-must-not-leak",
        refresh: "refresh-token-must-not-leak",
        expires: 1,
      }),
      expires: 2,
    })),
  ]);

  assert.deepEqual(await store.list(), [{ providerId: "openai-codex", type: "oauth" }]);
  const fileMode = (await stat(path)).mode & 0o777;
  assert.equal(fileMode & 0o077, 0);
  const serialized = await readFile(path, "utf8");
  assert.match(serialized, /access-token-must-not-leak/);
});

test("login coordination exposes device and manual-code events without credentials", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login(_providerId, _type, interaction) {
      interaction.notify({
        type: "device_code",
        userCode: "ABCD-1234",
        verificationUri: "https://example.test/device",
        expiresInSeconds: 900,
      });
      await interaction.prompt({ type: "manual_code", message: "Enter the displayed code." });
    },
    async logout() {},
    async *stream(): AsyncIterable<AssistantMessageEvent> {},
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const started = await fetch(`${baseUrl}/v1/auth/login`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify({ provider: "openai-codex", type: "oauth" }),
  });
  assert.equal(started.status, 202);
  const status = (await started.json()) as {
    login_id: string;
    status: string;
    events: Array<{ type: string; prompt_id?: string; user_code?: string }>;
  };
  assert.equal(status.status, "pending");
  assert.equal(status.events[0]?.user_code, "ABCD-1234");
  const prompt = status.events.find((event) => event.type === "prompt");
  assert.notEqual(prompt?.prompt_id, undefined);
  assert.doesNotMatch(JSON.stringify(status), /access|refresh|credential|secret/i);

  const response = await fetch(`${baseUrl}/v1/auth/login/${status.login_id}/prompts/${prompt?.prompt_id}`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify({ value: "user-entered-code" }),
  });
  assert.equal(response.status, 204);

  const completed = await fetch(`${baseUrl}/v1/auth/login/${status.login_id}`, {
    headers: authorization(),
  });
  assert.equal((await completed.json() as { status: string }).status, "completed");
});

test("safe provider classification distinguishes operational failure categories", () => {
  const cases: readonly [unknown, number | undefined, string][] = [
    [{ errorMessage: "private usage limit reached" }, undefined, "usage_limit"],
    [{ errorMessage: "private token expired" }, undefined, "authentication_required"],
    [{ errorMessage: "private access denied" }, undefined, "provider_access_denied"],
    [{ errorMessage: "private unknown model" }, undefined, "model_unavailable"],
    [{ errorMessage: "private unknown parameter" }, undefined, "provider_request_rejected"],
    [{ errorMessage: "private opaque failure" }, 429, "rate_limited"],
    [{ errorMessage: "private opaque failure" }, 503, "provider_unavailable"],
    [{ errorMessage: "private opaque failure" }, undefined, "provider_error"],
  ];

  for (const [value, status, expectedCode] of cases) {
    const classified = classifyProviderError(value, status);
    assert.equal(classified.code, expectedCode);
    assert.doesNotMatch(classified.message, /private/);
  }
});

test("contract diagnostics reduce provider text to one bounded fingerprint", () => {
  assert.deepEqual(
    fingerprintProviderContractError(
      { errorMessage: "Unsupported parameter max_output_tokens; private detail" },
      400,
    ),
    {
      http_status: 400,
      mentions_max_output_tokens: true,
      parameter_rejection: true,
      max_output_tokens_rejection: true,
    },
  );
  assert.deepEqual(
    fingerprintProviderContractError({ errorMessage: "private opaque failure" }, 422),
    {
      http_status: 422,
      mentions_max_output_tokens: false,
      parameter_rejection: false,
      max_output_tokens_rejection: false,
    },
  );
});

test("provider usage errors are classified without exposing provider text", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login() {},
    async logout() {},
    async *stream(): AsyncIterable<AssistantMessageEvent> {
      yield {
        type: "error",
        reason: "error",
        error: fauxAssistantMessage("", {
          stopReason: "error",
          errorMessage: "Codex error: The usage limit has been reached; secret detail",
        }),
      };
    },
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest()),
  });
  const events = await stream.text();
  assert.match(events, /"code":"usage_limit"/);
  assert.doesNotMatch(events, /secret detail|Codex error/);
});

test("provider request errors are classified without exposing provider text", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login() {},
    async logout() {},
    async *stream(): AsyncIterable<AssistantMessageEvent> {
      yield {
        type: "error",
        reason: "error",
        error: fauxAssistantMessage("", {
          stopReason: "error",
          errorMessage: "Codex error: Unsupported parameter max_output_tokens; private detail",
        }),
      };
    },
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest()),
  });
  const events = await stream.text();
  assert.match(events, /"code":"provider_request_rejected"/);
  assert.doesNotMatch(events, /max_output_tokens|private detail|Codex error/);
});

test("opt-in contract diagnostics travel only on the no-store SSE stream", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login() {},
    async logout() {},
    async *stream(request: GatewayStreamRequest): AsyncIterable<AssistantMessageEvent> {
      assert.equal(request.providerContractDiagnostics, true);
      throw new GatewayRuntimeError(
        "provider_request_rejected",
        "model provider rejected the request contract",
        {
          http_status: 400,
          mentions_max_output_tokens: true,
          parameter_rejection: true,
          max_output_tokens_rejection: true,
        },
      );
    },
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest({ provider_contract_diagnostics: true })),
  });
  const events = await stream.text();
  assert.match(events, /event: provider_contract_diagnostic/);
  assert.match(events, /"http_status":400/);
  assert.match(events, /"max_output_tokens_rejection":true/);
  assert.match(events, /"code":"provider_request_rejected"/);
  assert.doesNotMatch(events, /provider body|private detail/);
});

test("the gateway aborts a stalled stream at the caller's bounded time limit", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login() {},
    async logout() {},
    async *stream(_request: GatewayStreamRequest, signal: AbortSignal): AsyncIterable<AssistantMessageEvent> {
      await new Promise<void>((resolve) => signal.addEventListener("abort", () => resolve(), { once: true }));
    },
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest({ time_limit_seconds: 1 })),
  });
  const events = await stream.text();

  assert.match(events, /"code":"timeout"/);
  assert.match(events, /event: done/);
});

test("an internal caller can cancel an active normalized stream", async (t) => {
  const runtime: GatewayRuntime = {
    async listProviders() {
      return [];
    },
    async login() {},
    async logout() {},
    async *stream(_request: GatewayStreamRequest, signal: AbortSignal): AsyncIterable<AssistantMessageEvent> {
      await new Promise<void>((resolve) => signal.addEventListener("abort", () => resolve(), { once: true }));
    },
  };
  const server = createGatewayServer({ runtime, internalToken: INTERNAL_TOKEN });
  const baseUrl = await listen(server);
  t.after(() => close(server));

  const stream = await fetch(`${baseUrl}/v1/streams`, {
    method: "POST",
    headers: { ...authorization(), "content-type": "application/json" },
    body: JSON.stringify(fauxStreamRequest()),
  });
  const streamId = stream.headers.get("x-gateway-stream-id");
  assert.notEqual(streamId, null);
  const cancellation = await fetch(`${baseUrl}/v1/streams/${streamId}`, {
    method: "DELETE",
    headers: authorization(),
  });
  assert.equal(cancellation.status, 202);
  assert.match(await stream.text(), /"code":"cancelled"/);
});

function syntheticCodexAccessToken(): string {
  const encode = (value: object): string => Buffer.from(JSON.stringify(value)).toString("base64url");
  return [
    encode({ alg: "none", typ: "JWT" }),
    encode({
      "https://api.openai.com/auth": {
        chatgpt_account_id: "synthetic-account",
      },
    }),
    "synthetic-signature",
  ].join(".");
}

function authorization(): Record<string, string> {
  return { authorization: `Bearer ${INTERNAL_TOKEN}` };
}

function fauxStreamRequest(overrides: Record<string, unknown> = {}): object {
  return {
    provider: "faux",
    model: "faux-deterministic-v1",
    effort: "standard",
    messages: [{ role: "user", content: "Create a synthetic dungeon brief." }],
    tools: [
      {
        name: "set_brief",
        description: "Set a deterministic dungeon brief.",
        parameters: { type: "object", properties: { rooms: { type: "integer" } } },
      },
    ],
    output_token_limit: 512,
    time_limit_seconds: 30,
    run_id: "run_synthetic",
    ...overrides,
  };
}

async function listen(server: ReturnType<typeof createServer>): Promise<string> {
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      server.off("error", reject);
      resolve();
    });
  });
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("expected TCP server address");
  }
  return `http://127.0.0.1:${address.port}`;
}

async function close(server: ReturnType<typeof createServer>): Promise<void> {
  await new Promise<void>((resolve, reject) => server.close((error) => (error === undefined ? resolve() : reject(error))));
}