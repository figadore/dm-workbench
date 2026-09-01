export type GatewayEffort = "fast" | "standard" | "deep";

export interface GatewayToolSchema {
  readonly name: string;
  readonly description: string;
  readonly parameters: Record<string, unknown>;
  readonly constrainedSampling?: "prefer" | "require";
}

export type GatewayMessage =
  | { readonly role: "user"; readonly content: string }
  | {
      readonly role: "assistant";
      readonly content: string;
      readonly toolCalls: readonly { readonly id: string; readonly name: string; readonly arguments: Record<string, unknown> }[];
      readonly opaqueContinuitySignatures: readonly string[];
    }
  | {
      readonly role: "tool_result";
      readonly content: string;
      readonly toolCallId: string;
      readonly toolName: string;
      readonly isError: boolean;
    };

export interface GatewayStreamRequest {
  readonly provider: string;
  readonly model: string;
  readonly effort: GatewayEffort;
  readonly systemPrompt?: string;
  readonly messages: readonly GatewayMessage[];
  readonly tools: readonly GatewayToolSchema[];
  readonly outputTokenLimit: number;
  readonly timeLimitSeconds: number;
  readonly runId: string;
  readonly sessionId?: string;
  readonly providerContractDiagnostics: boolean;
}

export class GatewayRequestError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const MAX_MESSAGES = 32;
const MAX_MESSAGE_CHARACTERS = 32_000;
const MAX_PROMPT_CHARACTERS = 128_000;
const MAX_TOOLS = 16;
const MAX_OUTPUT_TOKENS = 16_384;

export function parseStreamRequest(value: unknown): GatewayStreamRequest {
  const object = expectObject(value, "request must be a JSON object");
  expectOnlyKeys(
    object,
    new Set([
      "provider",
      "model",
      "effort",
      "system_prompt",
      "messages",
      "tools",
      "output_token_limit",
      "time_limit_seconds",
      "run_id",
      "session_id",
      "provider_contract_diagnostics",
      "attachment_references",
    ]),
  );

  if ("attachment_references" in object) {
    const attachments = expectArray(
      object.attachment_references,
      "attachment_references must be an array",
    );
    if (attachments.length > 4) {
      throw new GatewayRequestError("attachment_limit", "too many attachments");
    }
    throw new GatewayRequestError(
      "attachments_unavailable",
      "attachment loading is not configured for this gateway",
    );
  }

  const messages = expectArray(object.messages, "messages must be an array");
  if (messages.length === 0 || messages.length > MAX_MESSAGES) {
    throw new GatewayRequestError("message_limit", "invalid number of messages");
  }

  let promptCharacters = 0;
  const normalizedMessages = messages.map((message) => {
    const item = expectObject(message, "message must be an object");
    const role = expectString(item.role, "message role must be a string");
    const content = expectString(item.content, "message content must be a string");
    if (content.length > MAX_MESSAGE_CHARACTERS) {
      throw new GatewayRequestError("message_limit", "invalid message length");
    }
    promptCharacters += content.length;
    if (role === "user") {
      expectOnlyKeys(item, new Set(["role", "content"]));
      if (content.length === 0) throw new GatewayRequestError("message_limit", "invalid message length");
      return { role: "user" as const, content };
    }
    if (role === "assistant") {
      expectOnlyKeys(item, new Set(["role", "content", "tool_calls", "opaque_continuity_signatures"]));
      const calls = item.tool_calls === undefined ? [] : expectArray(item.tool_calls, "tool_calls must be an array").map((call) => {
        const value = expectObject(call, "tool call must be an object");
        expectOnlyKeys(value, new Set(["tool_name", "call_id", "arguments"]));
        return { id: expectIdentifier(value.call_id, "tool call ID"), name: expectIdentifier(value.tool_name, "tool name"), arguments: expectObject(value.arguments, "tool arguments must be an object") };
      });
      const signatures = item.opaque_continuity_signatures === undefined ? [] : expectArray(item.opaque_continuity_signatures, "opaque continuity signatures must be an array").map((value) => expectString(value, "opaque continuity signature must be a string"));
      return { role: "assistant" as const, content, toolCalls: calls, opaqueContinuitySignatures: signatures };
    }
    if (role === "tool_result") {
      expectOnlyKeys(item, new Set(["role", "content", "tool_call_id", "tool_name", "is_error"]));
      if (content.length === 0 || typeof item.is_error !== "boolean") throw new GatewayRequestError("invalid_message_role", "invalid tool result message");
      return { role: "tool_result" as const, content, toolCallId: expectIdentifier(item.tool_call_id, "tool call ID"), toolName: expectIdentifier(item.tool_name, "tool name"), isError: item.is_error };
    }
    throw new GatewayRequestError("invalid_message_role", "unsupported message role");
  });

  const systemPrompt = optionalString(object.system_prompt, "system_prompt");
  promptCharacters += systemPrompt?.length ?? 0;
  if (promptCharacters > MAX_PROMPT_CHARACTERS) {
    throw new GatewayRequestError("prompt_limit", "prompt exceeds the gateway limit");
  }

  const tools = parseTools(object.tools);
  const outputTokenLimit = expectInteger(
    object.output_token_limit,
    "output_token_limit must be an integer",
  );
  if (outputTokenLimit < 1 || outputTokenLimit > MAX_OUTPUT_TOKENS) {
    throw new GatewayRequestError(
      "output_token_limit",
      "output_token_limit is outside the allowed range",
    );
  }

  const timeLimitSeconds = expectInteger(
    object.time_limit_seconds,
    "time_limit_seconds must be an integer",
  );
  if (timeLimitSeconds < 1 || timeLimitSeconds > 300) {
    throw new GatewayRequestError(
      "time_limit_seconds",
      "time_limit_seconds is outside the allowed range",
    );
  }

  const effort = expectString(object.effort, "effort must be a string");
  if (effort !== "fast" && effort !== "standard" && effort !== "deep") {
    throw new GatewayRequestError("effort", "unsupported effort level");
  }
  const providerContractDiagnostics =
    object.provider_contract_diagnostics === undefined
      ? false
      : expectBoolean(
          object.provider_contract_diagnostics,
          "provider_contract_diagnostics must be a boolean",
        );

  return {
    provider: expectIdentifier(object.provider, "provider"),
    model: expectIdentifier(object.model, "model"),
    effort,
    ...(systemPrompt === undefined ? {} : { systemPrompt }),
    messages: normalizedMessages,
    tools,
    outputTokenLimit,
    timeLimitSeconds,
    runId: expectIdentifier(object.run_id, "run_id"),
    ...(object.session_id === undefined
      ? {}
      : { sessionId: expectIdentifier(object.session_id, "session_id") }),
    providerContractDiagnostics,
  };
}

function parseTools(value: unknown): readonly GatewayToolSchema[] {
  const tools = expectArray(value, "tools must be an array");
  if (tools.length > MAX_TOOLS) {
    throw new GatewayRequestError("tool_limit", "too many tool schemas");
  }
  return tools.map((tool) => {
    const item = expectObject(tool, "tool schema must be an object");
    expectOnlyKeys(item, new Set(["name", "description", "parameters", "constrained_sampling"]));
    const constrainedSampling = item.constrained_sampling;
    if (constrainedSampling !== undefined && constrainedSampling !== "prefer" && constrainedSampling !== "require") {
      throw new GatewayRequestError("invalid_request", "constrained_sampling is invalid");
    }
    return {
      name: expectIdentifier(item.name, "tool name"),
      description: expectString(item.description, "tool description"),
      parameters: expectObject(item.parameters, "tool parameters must be an object"),
      ...(constrainedSampling === undefined ? {} : { constrainedSampling }),
    };
  });
}

function expectObject(value: unknown, message: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new GatewayRequestError("invalid_request", message);
  }
  return value as Record<string, unknown>;
}

function expectArray(value: unknown, message: string): readonly unknown[] {
  if (!Array.isArray(value)) {
    throw new GatewayRequestError("invalid_request", message);
  }
  return value;
}

function expectString(value: unknown, message: string): string {
  if (typeof value !== "string") {
    throw new GatewayRequestError("invalid_request", message);
  }
  return value;
}

function optionalString(value: unknown, field: string): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  return expectString(value, `${field} must be a string`);
}

function expectInteger(value: unknown, message: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new GatewayRequestError("invalid_request", message);
  }
  return value;
}

function expectBoolean(value: unknown, message: string): boolean {
  if (typeof value !== "boolean") {
    throw new GatewayRequestError("invalid_request", message);
  }
  return value;
}

function expectIdentifier(value: unknown, field: string): string {
  const identifier = expectString(value, `${field} must be a string`);
  if (!/^[A-Za-z0-9._:-]{1,160}$/.test(identifier)) {
    throw new GatewayRequestError("invalid_request", `${field} is invalid`);
  }
  return identifier;
}

function expectOnlyKeys(
  value: Record<string, unknown>,
  allowedKeys: ReadonlySet<string>,
): void {
  for (const key of Object.keys(value)) {
    if (!allowedKeys.has(key)) {
      throw new GatewayRequestError("unknown_field", `unknown field: ${key}`);
    }
  }
}