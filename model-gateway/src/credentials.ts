import { chmod, mkdir, open, readFile, rename, stat, unlink } from "node:fs/promises";
import { basename, dirname, join } from "node:path";
import { randomUUID } from "node:crypto";

import type {
  AuthOperationOptions,
  Credential,
  CredentialInfo,
  CredentialStore,
} from "@earendil-works/pi-ai";

type CredentialFile = Record<string, Credential>;

/** Persistent, app-owned credentials with provider-scoped serialized updates. */
export class FileCredentialStore implements CredentialStore {
  private readonly chains = new Map<string, Promise<void>>();

  constructor(private readonly filePath: string) {}

  async read(
    providerId: string,
    options?: AuthOperationOptions,
  ): Promise<Credential | undefined> {
    throwIfAborted(options?.signal);
    assertProviderId(providerId);
    const credentials = await this.readFile();
    return cloneCredential(credentials[providerId]);
  }

  async list(options?: AuthOperationOptions): Promise<readonly CredentialInfo[]> {
    throwIfAborted(options?.signal);
    const credentials = await this.readFile();
    return Object.entries(credentials).map(([providerId, credential]) => ({
      providerId,
      type: credential.type,
    }));
  }

  modify(
    providerId: string,
    fn: (current: Credential | undefined) => Promise<Credential | undefined>,
    options?: AuthOperationOptions,
  ): Promise<Credential | undefined> {
    assertProviderId(providerId);
    return this.enqueue(providerId, async () => {
      throwIfAborted(options?.signal);
      const credentials = await this.readFile();
      const current = cloneCredential(credentials[providerId]);
      const next = await fn(current);
      throwIfAborted(options?.signal);
      if (next === undefined) {
        return current;
      }
      const stored = cloneCredential(next);
      if (stored === undefined) {
        return current;
      }
      credentials[providerId] = stored;
      await this.writeFile(credentials);
      return stored;
    });
  }

  delete(providerId: string, options?: AuthOperationOptions): Promise<void> {
    assertProviderId(providerId);
    return this.enqueue(providerId, async () => {
      throwIfAborted(options?.signal);
      const credentials = await this.readFile();
      if (credentials[providerId] !== undefined) {
        delete credentials[providerId];
        await this.writeFile(credentials);
      }
    });
  }

  private async enqueue<T>(providerId: string, task: () => Promise<T>): Promise<T> {
    const previous = this.chains.get(providerId) ?? Promise.resolve();
    const pending = previous.catch(() => undefined).then(task);
    this.chains.set(
      providerId,
      pending.then(
        () => undefined,
        () => undefined,
      ),
    );
    return pending;
  }

  private async readFile(): Promise<CredentialFile> {
    try {
      const contents = await readFile(this.filePath, "utf8");
      return parseCredentialFile(contents);
    } catch (error: unknown) {
      if (isNodeError(error, "ENOENT")) {
        return {};
      }
      throw error;
    }
  }

  private async writeFile(credentials: CredentialFile): Promise<void> {
    const directory = dirname(this.filePath);
    await mkdir(directory, { recursive: true, mode: 0o700 });
    await chmod(directory, 0o700);

    const temporaryPath = join(
      directory,
      `.${basename(this.filePath)}.${process.pid}.${randomUUID()}.tmp`,
    );
    const handle = await open(temporaryPath, "wx", 0o600);
    try {
      await handle.writeFile(`${JSON.stringify(credentials)}\n`, "utf8");
      await handle.sync();
    } finally {
      await handle.close();
    }

    try {
      await rename(temporaryPath, this.filePath);
      await chmod(this.filePath, 0o600);
    } catch (error: unknown) {
      await unlink(temporaryPath).catch(() => undefined);
      throw error;
    }
  }
}

function parseCredentialFile(contents: string): CredentialFile {
  const value: unknown = JSON.parse(contents);
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("gateway credential file must contain an object");
  }
  const credentials: CredentialFile = {};
  for (const [providerId, credential] of Object.entries(value)) {
    assertProviderId(providerId);
    if (
      credential === null ||
      typeof credential !== "object" ||
      Array.isArray(credential) ||
      ((credential as { type?: unknown }).type !== "api_key" &&
        (credential as { type?: unknown }).type !== "oauth")
    ) {
      throw new Error("gateway credential file contains an invalid credential");
    }
    credentials[providerId] = credential as Credential;
  }
  return credentials;
}

function cloneCredential(credential: Credential | undefined): Credential | undefined {
  if (credential === undefined) {
    return undefined;
  }
  return JSON.parse(JSON.stringify(credential)) as Credential;
}

function assertProviderId(providerId: string): void {
  if (!/^[A-Za-z0-9._:-]{1,160}$/.test(providerId)) {
    throw new Error("invalid credential provider id");
  }
}

function throwIfAborted(signal: AbortSignal | undefined): void {
  if (signal?.aborted) {
    throw signal.reason ?? new Error("credential operation aborted");
  }
}

function isNodeError(error: unknown, code: string): error is NodeJS.ErrnoException {
  return typeof error === "object" && error !== null && (error as NodeJS.ErrnoException).code === code;
}