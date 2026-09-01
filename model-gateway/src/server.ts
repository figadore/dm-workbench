import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";

import { type Usage } from "@earendil-works/pi-ai";

import { GatewayRequestError, parseStreamRequest } from "./contracts.js";
import { LoginCoordinator } from "./login.js";
import { classifyProviderError } from "./provider-errors.js";
import { GatewayRuntimeError, type GatewayRuntime } from "./runtime.js";

const MAX_REQUEST_BYTES = 256 * 1024;

export interface GatewayServerOptions {
  readonly runtime: GatewayRuntime;
  readonly internalToken: string;
  readonly gatewayVersion?: string;
}

export function createGatewayServer(options: GatewayServerOptions): Server {
  if (options.internalToken.length < 32) {
    throw new Error("DM_MODEL_GATEWAY_INTERNAL_TOKEN must be at least 32 characters");
  }
  const logins = new LoginCoordinator(options.runtime);
  const activeStreams = new Map<string, AbortController>();

  return createServer((request, response) => {
    void route(request, response, options, logins, activeStreams);
  });
}

async function route(
  request: IncomingMessage,
  response: ServerResponse,
  options: GatewayServerOptions,
  logins: LoginCoordinator,
  activeStreams: Map<string, AbortController>,
): Promise<void> {
  try {
    const url = new URL(request.url ?? "/", "http://gateway.internal");
    if (!isAuthorized(request, options.internalToken)) {
      sendJson(response, 401, { error: { code: "unauthorized", message: "unauthorized" } });
      return;
    }

    if (request.method === "GET" && url.pathname === "/health") {
      sendJson(response, 200, {
        status: "ok",
        gateway_version: options.gatewayVersion ?? "0.1.0",
        credential_store: "ready",
      });
      return;
    }

    if (request.method === "GET" && url.pathname === "/v1/providers") {
      sendJson(response, 200, { providers: await options.runtime.listProviders() });
      return;
    }
    if (request.method === "GET" && url.pathname === "/v1/auth/status") {
      const providers = await options.runtime.listProviders();
      sendJson(response, 200, {
        providers: providers.map(({ id, authenticated, authModes }) => ({
          id,
          authenticated,
          auth_modes: authModes,
        })),
      });
      return;
    }
    if (request.method === "POST" && url.pathname === "/v1/auth/login") {
      const body = expectObject(await readJson(request));
      const providerId = expectIdentifier(body.provider, "provider");
      const type = body.type;
      if (type !== "oauth" && type !== "api_key") {
        throw new GatewayRequestError("invalid_request", "invalid login type");
      }
      sendJson(response, 202, toJsonLoginStatus(logins.start(providerId, type)));
      return;
    }
    if (request.method === "POST" && url.pathname === "/v1/auth/logout") {
      const body = expectObject(await readJson(request));
      await options.runtime.logout(expectIdentifier(body.provider, "provider"));
      response.writeHead(204).end();
      return;
    }

    const loginStatus = /^\/v1\/auth\/login\/([0-9a-f-]+)$/.exec(url.pathname);
    if (request.method === "GET" && loginStatus !== null) {
      const status = logins.get(loginStatus[1]);
      if (status === undefined) {
        sendJson(response, 404, { error: { code: "not_found", message: "login not found" } });
      } else {
        sendJson(response, 200, toJsonLoginStatus(status));
      }
      return;
    }
    const loginPrompt = /^\/v1\/auth\/login\/([0-9a-f-]+)\/prompts\/([0-9a-f-]+)$/.exec(
      url.pathname,
    );
    if (request.method === "POST" && loginPrompt !== null) {
      const body = expectObject(await readJson(request));
      const value = body.value;
      if (typeof value !== "string" || value.length > 4_096) {
        throw new GatewayRequestError("invalid_request", "invalid prompt response");
      }
      if (!logins.respond(loginPrompt[1], loginPrompt[2], value)) {
        sendJson(response, 404, { error: { code: "not_found", message: "prompt not found" } });
      } else {
        response.writeHead(204).end();
      }
      return;
    }
    if (request.method === "POST" && url.pathname === "/v1/streams") {
      const streamRequest = parseStreamRequest(await readJson(request));
      const streamId = randomUUID();
      const controller = new AbortController();
      activeStreams.set(streamId, controller);
      activeStreams.set(streamRequest.runId, controller);
      logGatewayEvent("model stream started", {
        stream_id: streamId,
        provider_id: streamRequest.provider,
        model_id: streamRequest.model,
        time_limit_seconds: streamRequest.timeLimitSeconds,
      });
      response.writeHead(200, {
        "cache-control": "no-store",
        connection: "keep-alive",
        "content-type": "text/event-stream; charset=utf-8",
        "x-gateway-stream-id": streamId,
      });
      response.flushHeaders();
      response.on("close", () => controller.abort());
      let timedOut = false;
      const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, streamRequest.timeLimitSeconds * 1_000);
      try {
        let eventCount = 0;
        let textCharacters = 0;
        let thinkingCharacters = 0;
        let toolCallCount = 0;
        let terminalType: string | undefined;
        for await (const event of options.runtime.stream(streamRequest, controller.signal)) {
          if (controller.signal.aborted) {
            break;
          }
          eventCount += 1;
          if (event.type === "text_delta" && typeof event.delta === "string") {
            textCharacters += event.delta.length;
          } else if (event.type === "thinking_delta" && typeof event.delta === "string") {
            thinkingCharacters += event.delta.length;
          } else if (event.type === "toolcall_end") {
            toolCallCount += 1;
          }
          if (event.type === "done" || event.type === "error") {
            terminalType = event.type;
          }
          writePiEvent(response, event);
        }
        if (terminalType !== undefined) {
          logGatewayEvent("model stream terminal event", {
            stream_id: streamId,
            event_count: eventCount,
            text_characters: textCharacters,
            thinking_characters: thinkingCharacters,
            tool_call_count: toolCallCount,
            terminal_type: terminalType,
          });
        }
        if (timedOut) {
          logGatewayEvent("model stream timed out", {
            stream_id: streamId,
            event_count: eventCount,
            text_characters: textCharacters,
            thinking_characters: thinkingCharacters,
            tool_call_count: toolCallCount,
          });
          writeEvent(response, "error", { code: "timeout", message: "stream time limit reached" });
        } else if (controller.signal.aborted) {
          logGatewayEvent("model stream cancelled", {
            stream_id: streamId,
            event_count: eventCount,
            text_characters: textCharacters,
            thinking_characters: thinkingCharacters,
            tool_call_count: toolCallCount,
          });
          writeEvent(response, "error", { code: "cancelled", message: "stream cancelled" });
        } else if (terminalType === undefined) {
          logGatewayEvent("model stream ended without terminal provider event", {
            stream_id: streamId,
            event_count: eventCount,
            text_characters: textCharacters,
            thinking_characters: thinkingCharacters,
            tool_call_count: toolCallCount,
          });
          writeEvent(response, "error", {
            code: "provider_error",
            message: "model stream ended without a terminal response",
          });
        }
      } catch (error: unknown) {
        if (timedOut) {
          logGatewayEvent("model stream timed out", { stream_id: streamId });
          writeEvent(response, "error", { code: "timeout", message: "stream time limit reached" });
        } else {
          writeSafeError(response, error, streamId);
        }
      } finally {
        clearTimeout(timeout);
        activeStreams.delete(streamId);
        activeStreams.delete(streamRequest.runId);
        writeEvent(response, "done", {});
        response.end();
      }
      return;
    }
    const streamCancellation = /^\/v1\/streams\/([0-9a-f-]+)$/.exec(url.pathname);
    if (request.method === "DELETE" && streamCancellation !== null) {
      const controller = activeStreams.get(streamCancellation[1]);
      if (controller === undefined) {
        sendJson(response, 404, { error: { code: "not_found", message: "stream not found" } });
      } else {
        controller.abort();
        response.writeHead(202).end();
      }
      return;
    }
    sendJson(response, 404, { error: { code: "not_found", message: "not found" } });
  } catch (error: unknown) {
    writeHttpError(response, error);
  }
}

function writePiEvent(response: ServerResponse, event: { readonly type: string; readonly [key: string]: unknown }): void {
  switch (event.type) {
    case "text_delta":
      writeEvent(response, "text_delta", { content_index: event.contentIndex, delta: event.delta });
      return;
    case "thinking_delta":
      writeEvent(response, "thinking_delta", { content_index: event.contentIndex, delta: event.delta });
      return;
    case "toolcall_end": {
      const toolCall = event.toolCall as { id: string; name: string; arguments: Record<string, unknown> };
      writeEvent(response, "tool_call", toolCall);
      return;
    }
    case "done": {
      const message = event.message as { usage: unknown; stopReason: unknown };
      const usage = normalizeUsage(message.usage);
      if (usage !== undefined) writeEvent(response, "usage", usage);
      writeEvent(response, "completion", { reason: message.stopReason });
      return;
    }
    case "error": {
      const error = classifyProviderError(event.error);
      logGatewayEvent("model provider stream error", { code: error.code });
      writeEvent(response, "error", error);
    }
  }
}

function normalizeUsage(value: unknown): { input_tokens: number; output_tokens: number } | undefined {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  // `pi-ai` normalizes every provider's final message to this pinned contract.
  // Do not inspect provider-native usage field names at the gateway boundary.
  const usage = value as Partial<Usage>;
  if (!isNonNegativeInteger(usage.input) || !isNonNegativeInteger(usage.output)) {
    return undefined;
  }
  return { input_tokens: usage.input, output_tokens: usage.output };
}

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function writeSafeError(response: ServerResponse, error: unknown, streamId: string): void {
  if (error instanceof GatewayRuntimeError) {
    logGatewayEvent("model gateway runtime error", { stream_id: streamId, code: error.code });
    if (error.contractDiagnostic !== undefined) {
      // Explicit transient diagnostics travel only on the caller's no-store SSE stream.
      // They are never written to ordinary gateway logs or durable attempt reports.
      writeEvent(response, "provider_contract_diagnostic", error.contractDiagnostic);
    }
    writeEvent(response, "error", { code: error.code, message: error.message });
    return;
  }
  logGatewayEvent("model gateway stream exception", {
    stream_id: streamId,
    exception_type: error instanceof Error ? error.constructor.name : typeof error,
  });
  writeEvent(response, "error", { code: "provider_error", message: "model stream failed" });
}

function logGatewayEvent(message: string, data: Record<string, string | number>): void {
  // Never log prompts, provider response content, or credentials from the gateway.
  process.stderr.write(`${JSON.stringify({ timestamp: new Date().toISOString(), level: "INFO", message, data })}\n`);
}

function writeHttpError(response: ServerResponse, error: unknown): void {
  if (response.headersSent) {
    response.end();
    return;
  }
  if (error instanceof GatewayRequestError) {
    sendJson(response, 400, { error: { code: error.code, message: error.message } });
    return;
  }
  sendJson(response, 500, { error: { code: "internal_error", message: "internal server error" } });
}

function sendJson(response: ServerResponse, status: number, body: unknown): void {
  response.writeHead(status, {
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
  });
  response.end(JSON.stringify(body));
}

function writeEvent(response: ServerResponse, event: string, data: unknown): void {
  response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}

function isAuthorized(request: IncomingMessage, token: string): boolean {
  const authorization = request.headers.authorization;
  if (authorization === undefined || !authorization.startsWith("Bearer ")) {
    return false;
  }
  const supplied = Buffer.from(authorization.slice("Bearer ".length));
  const expected = Buffer.from(token);
  return supplied.length === expected.length && timingSafeEqual(supplied, expected);
}

async function readJson(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  let total = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    total += buffer.length;
    if (total > MAX_REQUEST_BYTES) {
      throw new GatewayRequestError("request_limit", "request exceeds the gateway limit");
    }
    chunks.push(buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8")) as unknown;
  } catch {
    throw new GatewayRequestError("invalid_json", "request body must be valid JSON");
  }
}

function expectObject(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new GatewayRequestError("invalid_request", "request must be a JSON object");
  }
  return value as Record<string, unknown>;
}

function expectIdentifier(value: unknown, field: string): string {
  if (typeof value !== "string" || !/^[A-Za-z0-9._:-]{1,160}$/.test(value)) {
    throw new GatewayRequestError("invalid_request", `${field} is invalid`);
  }
  return value;
}

function toJsonLoginStatus(status: ReturnType<LoginCoordinator["start"]>): object {
  return {
    login_id: status.loginId,
    provider: status.providerId,
    status: status.status,
    events: status.events.map(toJsonLoginEvent),
  };
}

function toJsonLoginEvent(event: ReturnType<LoginCoordinator["start"]>["events"][number]): object {
  switch (event.type) {
    case "info":
    case "progress":
      return { type: event.type, message: event.message };
    case "auth_url":
      return {
        type: event.type,
        url: event.url,
        ...(event.instructions === undefined ? {} : { instructions: event.instructions }),
      };
    case "device_code":
      return {
        type: event.type,
        user_code: event.userCode,
        verification_uri: event.verificationUri,
        ...(event.intervalSeconds === undefined
          ? {}
          : { interval_seconds: event.intervalSeconds }),
        ...(event.expiresInSeconds === undefined ? {} : { expires_in_seconds: event.expiresInSeconds }),
      };
    case "prompt":
      return {
        type: event.type,
        prompt_id: event.promptId,
        prompt_type: event.promptType,
        message: event.message,
        ...(event.placeholder === undefined ? {} : { placeholder: event.placeholder }),
        ...(event.options === undefined ? {} : { options: event.options }),
      };
  }
}