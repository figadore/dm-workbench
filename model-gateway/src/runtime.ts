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
  type MutableModels,
  type Tool,
} from "@earendil-works/pi-ai";
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
}

export function createPiAiRuntime(options: PiAiRuntimeOptions): GatewayRuntime {
  const models = createAllowlistedModels(options.credentials, options.fauxResponses);
  return new PiAiGatewayRuntime(models);
}

function createAllowlistedModels(
  credentials: CredentialStore,
  fauxResponses: readonly FauxResponseStep[] | undefined,
): MutableModels {
  const models = createModels({ credentials });
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
  constructor(private readonly models: MutableModels) {}

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
        messages: request.messages.map((message) => ({
          role: "user" as const,
          content: message.content,
          timestamp: Date.now(),
        })),
        tools: request.tools.map(toPiTool),
      },
      {
        maxTokens: request.outputTokenLimit,
        sessionId: request.sessionId,
        reasoning: toPiEffort(request.effort),
        signal,
      },
    );
    yield* stream;
  }
}

function toPiTool(tool: GatewayStreamRequest["tools"][number]): Tool {
  return {
    name: tool.name,
    description: tool.description,
    parameters: Type.Unsafe(tool.parameters),
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