import {
  createModels,
  fauxAssistantMessage,
  fauxProvider,
  Type,
  type AssistantMessageEvent,
  type AuthInteraction,
  type AuthType,
  type CredentialStore,
  type FauxResponseStep,
  type FetchFunction,
  type MutableModels,
  type Tool,
  type Transport,
} from "@earendil-works/pi-ai";
import { githubCopilotProvider } from "@earendil-works/pi-ai/providers/github-copilot";
import { openaiCodexProvider } from "@earendil-works/pi-ai/providers/openai-codex";
import { openaiProvider } from "@earendil-works/pi-ai/providers/openai";

import type { GatewayStreamRequest } from "./contracts.js";

const FAUX_PROVIDER_ID = "faux";

export class GatewayRuntimeError extends Error {
  constructor(
    readonly code: "model_unavailable" | "authentication_required",
    message: string,
  ) {
    super(message);
  }
}

export interface GatewayModel {
  readonly id: string;
  readonly name: string;
  readonly input: readonly string[];
  readonly capabilities: readonly string[];
  readonly contextWindow: number;
  readonly maxOutputTokens: number;
}

export interface GatewayProviderStatus {
  readonly id: string;
  readonly name: string;
  readonly authenticated: boolean;
  readonly authModes: readonly string[];
  readonly models: readonly GatewayModel[];
}

export interface GatewayRuntime {
  listProviders(): Promise<readonly GatewayProviderStatus[]>;
  login(providerId: string, type: AuthType, interaction: AuthInteraction): Promise<void>;
  logout(providerId: string): Promise<void>;
  stream(
    request: GatewayStreamRequest,
    signal: AbortSignal,
  ): AsyncIterable<AssistantMessageEvent>;
}

export interface PiAiRuntimeOptions {
  readonly credentials: CredentialStore;
  readonly fauxResponses?: readonly FauxResponseStep[];
  readonly providerFetch?: FetchFunction;
  readonly providerTransport?: Transport;
}

export function createPiAiRuntime(options: PiAiRuntimeOptions): GatewayRuntime {
  const models = createAllowlistedModels(options.credentials, options.fauxResponses);
  return new PiAiGatewayRuntime(
    models,
    options.providerFetch,
    options.providerTransport,
  );
}

function createAllowlistedModels(
  credentials: CredentialStore,
  fauxResponses: readonly FauxResponseStep[] | undefined,
): MutableModels {
  const models = createModels({ credentials });
  models.setProvider(githubCopilotProvider());
  models.setProvider(openaiCodexProvider());
  models.setProvider(openaiProvider());

  const faux = fauxProvider({
    provider: FAUX_PROVIDER_ID,
    models: [
      {
        id: "faux-deterministic-v1",
        name: "Faux deterministic contract provider",
        input: ["text"],
        reasoning: true,
        contextWindow: 16_384,
        maxTokens: 4_096,
      },
    ],
    tokensPerSecond: 100_000,
  });
  faux.setResponses([...(fauxResponses ?? [fauxAssistantMessage("Faux provider ready.")])]);
  models.setProvider(faux.provider);
  return models;
}

class PiAiGatewayRuntime implements GatewayRuntime {
  constructor(
    private readonly models: MutableModels,
    private readonly providerFetch?: FetchFunction,
    private readonly providerTransport?: Transport,
  ) {}

  async listProviders(): Promise<readonly GatewayProviderStatus[]> {
    return Promise.all(
      this.models.getProviders().map(async (provider) => {
        let authenticated = provider.id === FAUX_PROVIDER_ID;
        try {
          authenticated ||= (await this.models.checkAuth(provider.id)) !== undefined;
        } catch {
          authenticated = false;
        }
        return {
          id: provider.id,
          name: provider.name,
          authenticated,
          authModes: [
            ...(provider.auth.oauth === undefined ? [] : ["oauth"]),
            ...(provider.auth.apiKey === undefined ? [] : ["api_key"]),
          ],
          models: provider.getModels().map((model) => ({
            id: model.id,
            name: model.name,
            input: model.input,
            capabilities: [
              "text",
              ...(model.input.includes("image") ? ["image"] : []),
              ...(model.reasoning ? ["thinking"] : []),
              ...(
                model.compat !== undefined
                && "supportsStrictMode" in model.compat
                && model.compat.supportsStrictMode
                  ? ["json_schema_constrained_sampling"]
                  : []
              ),
              "tool_calls",
            ],
            contextWindow: model.contextWindow,
            maxOutputTokens: model.maxTokens,
          })),
        };
      }),
    );
  }

  async login(
    providerId: string,
    type: AuthType,
    interaction: AuthInteraction,
  ): Promise<void> {
    await this.models.login(providerId, type, interaction);
  }

  async logout(providerId: string): Promise<void> {
    await this.models.logout(providerId);
  }

  async *stream(
    request: GatewayStreamRequest,
    signal: AbortSignal,
  ): AsyncIterable<AssistantMessageEvent> {
    const model = this.models.getModel(request.provider, request.model);
    if (model === undefined) {
      throw new GatewayRuntimeError("model_unavailable", "requested model is unavailable");
    }
    if (request.provider !== FAUX_PROVIDER_ID) {
      const auth = await this.models.getAuth(model);
      if (auth === undefined) {
        throw new GatewayRuntimeError(
          "authentication_required",
          "provider authentication is required",
        );
      }
    }

    const stream = this.models.streamSimple(
      model,
      {
        ...(request.systemPrompt === undefined
          ? {}
          : { systemPrompt: request.systemPrompt }),
        messages: request.messages.map((message) => {
          const timestamp = Date.now();
          if (message.role === "user") {
            return { role: "user" as const, content: message.content, timestamp };
          }
          if (message.role === "assistant") {
            return {
              role: "assistant" as const,
              content: [
                ...(message.content === "" ? [] : [{ type: "text" as const, text: message.content }]),
                ...message.opaqueContinuitySignatures.map((thinkingSignature) => ({ type: "thinking" as const, thinking: "", thinkingSignature })),
                ...message.toolCalls.map((call) => ({ type: "toolCall" as const, id: call.id, name: call.name, arguments: call.arguments })),
              ],
              api: model.api,
              provider: model.provider,
              model: model.id,
              usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } },
              stopReason: message.toolCalls.length > 0 ? "toolUse" as const : "stop" as const,
              timestamp,
            };
          }
          return {
            role: "toolResult" as const,
            toolCallId: message.toolCallId,
            toolName: message.toolName,
            content: [{ type: "text" as const, text: message.content }],
            isError: message.isError,
            timestamp,
          };
        }),
        tools: request.tools.map(toPiTool),
      },
      {
        maxTokens: request.outputTokenLimit,
        sessionId: request.sessionId,
        reasoning: toPiEffort(request.effort),
        signal,
        fetch: this.providerFetch,
        transport: this.providerTransport,
        ...(request.provider === "openai-codex"
          ? {
              onPayload: (payload: unknown) =>
                withCodexOutputTokenLimit(payload, request.outputTokenLimit),
            }
          : {}),
      },
    );
    yield* stream;
  }
}

function withCodexOutputTokenLimit(
  payload: unknown,
  outputTokenLimit: number,
): Record<string, unknown> {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Codex provider payload must be an object");
  }
  return {
    ...(payload as Record<string, unknown>),
    max_output_tokens: outputTokenLimit,
  };
}

function toPiTool(tool: GatewayStreamRequest["tools"][number]): Tool {
  return {
    name: tool.name,
    description: tool.description,
    parameters: Type.Unsafe(tool.parameters),
    ...(tool.constrainedSampling === undefined
      ? {}
      : { constrainedSampling: { type: "json_schema" as const, strict: tool.constrainedSampling } }),
  };
}

function toPiEffort(effort: GatewayStreamRequest["effort"]): "low" | "medium" | "high" {
  switch (effort) {
    case "fast":
      return "low";
    case "standard":
      return "medium";
    case "deep":
      return "high";
  }
}