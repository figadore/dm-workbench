import { createServer, type IncomingMessage, type Server, type ServerResponse } from "node:http";
import { randomUUID, timingSafeEqual } from "node:crypto";

import { GatewayRequestError, parseStreamRequest } from "./contracts.js";
import { LoginCoordinator } from "./login.js";
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
        for await (const event of options.runtime.stream(streamRequest, controller.signal)) {
          if (controller.signal.aborted) {
            break;
          }
          writePiEvent(response, event);
        }
        if (timedOut) {
          writeEvent(response, "error", { code: "timeout", message: "stream time limit reached" });
        } else if (controller.signal.aborted) {
          writeEvent(response, "error", { code: "cancelled", message: "stream cancelled" });
        }
      } catch (error: unknown) {
        if (timedOut) {
          writeEvent(response, "error", { code: "timeout", message: "stream time limit reached" });
        } else {
          writeSafeError(response, error);
        }
      } finally {
        clearTimeout(timeout);
        activeStreams.delete(streamId);
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
      writeEvent(response, "usage", normalizeUsage(message.usage));
      writeEvent(response, "completion", { reason: message.stopReason });
      return;
    }
    case "error":
      writeEvent(response, "error", safeProviderError(event.error));
  }
}

function safeProviderError(value: unknown): { code: string; message: string } {
  const errorMessage =
    value !== null && typeof value === "object" && "errorMessage" in value
      ? (value as { errorMessage?: unknown }).errorMessage
      : undefined;
  if (typeof errorMessage === "string") {
    if (/usage limit|insufficient_quota|quota[^.]*reached|quota[^.]*exceeded/i.test(errorMessage)) {
      return { code: "usage_limit", message: "model provider usage limit reached" };
    }
    if (/rate limit|too many requests/i.test(errorMessage)) {
      return { code: "rate_limited", message: "model provider rate limit reached" };
    }
    if (/unauthorized|authentication|credential/i.test(errorMessage)) {
      return { code: "authentication_required", message: "provider authentication is required" };
    }
  }
  return { code: "provider_error", message: "model stream failed" };
}

function normalizeUsage(value: unknown): { input_tokens: number; output_tokens: number } {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    return { input_tokens: 0, output_tokens: 0 };
  }
  const usage = value as Record<string, unknown>;
  return {
    input_tokens: nonNegativeInteger(usage.inputTokens ?? usage.input_tokens),
    output_tokens: nonNegativeInteger(usage.outputTokens ?? usage.output_tokens),
  };
}

function nonNegativeInteger(value: unknown): number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 ? value : 0;
}

function writeSafeError(response: ServerResponse, error: unknown): void {
  if (error instanceof GatewayRuntimeError) {
    writeEvent(response, "error", { code: error.code, message: error.message });
    return;
  }
  writeEvent(response, "error", { code: "provider_error", message: "model stream failed" });
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