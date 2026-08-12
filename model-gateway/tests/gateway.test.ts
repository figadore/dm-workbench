import assert from "node:assert/strict";
import { mkdtemp, readFile, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  fauxAssistantMessage,
  fauxText,
  fauxThinking,
  fauxToolCall,
  type AssistantMessageEvent,
} from "@earendil-works/pi-ai";

import { FileCredentialStore } from "../src/credentials.js";
import type { GatewayStreamRequest } from "../src/contracts.js";
import { createPiAiRuntime, type GatewayRuntime } from "../src/runtime.js";
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
  assert.doesNotMatch(catalogText, /access|refresh|credential/i);

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
  assert.match(events, /"input_tokens":\d+/);
  assert.match(events, /"output_tokens":\d+/);
  assert.match(events, /event: done/);
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

function authorization(): Record<string, string> {
  return { authorization: `Bearer ${INTERNAL_TOKEN}` };
}

function fauxStreamRequest(): object {
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
    run_id: "run_synthetic",
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