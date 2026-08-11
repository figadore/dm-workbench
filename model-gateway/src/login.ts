import { randomUUID } from "node:crypto";

import type { AuthEvent, AuthPrompt, AuthType } from "@earendil-works/pi-ai";

import type { GatewayRuntime } from "./runtime.js";

export type LoginEvent =
  | { readonly type: "info"; readonly message: string }
  | { readonly type: "auth_url"; readonly url: string; readonly instructions?: string }
  | {
      readonly type: "device_code";
      readonly userCode: string;
      readonly verificationUri: string;
      readonly intervalSeconds?: number;
      readonly expiresInSeconds?: number;
    }
  | { readonly type: "progress"; readonly message: string }
  | {
      readonly type: "prompt";
      readonly promptId: string;
      readonly promptType: "text" | "select" | "manual_code";
      readonly message: string;
      readonly placeholder?: string;
      readonly options?: readonly { readonly id: string; readonly label: string }[];
    };

export interface LoginStatus {
  readonly loginId: string;
  readonly providerId: string;
  readonly status: "pending" | "completed" | "failed";
  readonly events: readonly LoginEvent[];
}

interface PendingPrompt {
  resolve(value: string): void;
  reject(error: Error): void;
}

export class LoginCoordinator {
  private readonly sessions = new Map<string, LoginSession>();

  constructor(private readonly runtime: GatewayRuntime) {}

  start(providerId: string, type: AuthType): LoginStatus {
    const session = new LoginSession(randomUUID(), providerId, type, this.runtime);
    this.sessions.set(session.loginId, session);
    session.start();
    return session.status();
  }

  get(loginId: string): LoginStatus | undefined {
    return this.sessions.get(loginId)?.status();
  }

  respond(loginId: string, promptId: string, value: string): boolean {
    return this.sessions.get(loginId)?.respond(promptId, value) ?? false;
  }
}

class LoginSession {
  readonly events: LoginEvent[] = [];
  private readonly prompts = new Map<string, PendingPrompt>();
  private state: "pending" | "completed" | "failed" = "pending";

  constructor(
    readonly loginId: string,
    readonly providerId: string,
    private readonly type: AuthType,
    private readonly runtime: GatewayRuntime,
  ) {}

  start(): void {
    void this.runtime
      .login(this.providerId, this.type, {
        prompt: (prompt) => this.prompt(prompt),
        notify: (event) => this.notify(event),
      })
      .then(
        () => {
          this.state = "completed";
        },
        () => {
          this.state = "failed";
        },
      );
  }

  status(): LoginStatus {
    return {
      loginId: this.loginId,
      providerId: this.providerId,
      status: this.state,
      events: this.events,
    };
  }

  respond(promptId: string, value: string): boolean {
    const prompt = this.prompts.get(promptId);
    if (prompt === undefined) {
      return false;
    }
    this.prompts.delete(promptId);
    prompt.resolve(value);
    return true;
  }

  private prompt(prompt: AuthPrompt): Promise<string> {
    if (prompt.type === "secret") {
      return Promise.reject(
        new Error("secret credential prompts are not accepted through this API"),
      );
    }
    const promptId = randomUUID();
    this.events.push({
      type: "prompt",
      promptId,
      promptType: prompt.type,
      message: prompt.message,
      ...(prompt.type === "text" && prompt.placeholder !== undefined
        ? { placeholder: prompt.placeholder }
        : {}),
      ...(prompt.type === "select"
        ? {
            options: prompt.options.map((option) => ({
              id: option.id,
              label: option.label,
            })),
          }
        : {}),
    });
    return new Promise<string>((resolve, reject) => {
      this.prompts.set(promptId, { resolve, reject });
    });
  }

  private notify(event: AuthEvent): void {
    this.events.push(toLoginEvent(event));
  }
}

function toLoginEvent(event: AuthEvent): LoginEvent {
  switch (event.type) {
    case "info":
      return { type: "info", message: event.message };
    case "auth_url":
      return {
        type: "auth_url",
        url: event.url,
        ...(event.instructions === undefined ? {} : { instructions: event.instructions }),
      };
    case "device_code":
      return {
        type: "device_code",
        userCode: event.userCode,
        verificationUri: event.verificationUri,
        ...(event.intervalSeconds === undefined
          ? {}
          : { intervalSeconds: event.intervalSeconds }),
        ...(event.expiresInSeconds === undefined
          ? {}
          : { expiresInSeconds: event.expiresInSeconds }),
      };
    case "progress":
      return { type: "progress", message: event.message };
  }
}