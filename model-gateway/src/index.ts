import { isIP } from "node:net";

import { FileCredentialStore } from "./credentials.js";
import { createPiAiRuntime } from "./runtime.js";
import { createGatewayServer } from "./server.js";

const host = process.env.MODEL_GATEWAY_HOST ?? "127.0.0.1";
const port = parsePort(process.env.MODEL_GATEWAY_PORT ?? "3000");
const credentialPath = process.env.MODEL_GATEWAY_CREDENTIAL_PATH ?? "/var/lib/dm-model-gateway/credentials.json";
const internalToken = requiredEnvironment("DM_MODEL_GATEWAY_INTERNAL_TOKEN");

if (!isPrivateBindHost(host)) {
  throw new Error("MODEL_GATEWAY_HOST must be a loopback or private address");
}

const server = createGatewayServer({
  runtime: createPiAiRuntime({ credentials: new FileCredentialStore(credentialPath) }),
  internalToken,
});

server.listen(port, host, () => {
  process.stdout.write(`DM model gateway listening on ${host}:${port}\n`);
});

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value.length === 0) {
    throw new Error(`${name} is required`);
  }
  return value;
}

function parsePort(value: string): number {
  const port = Number(value);
  if (!Number.isSafeInteger(port) || port < 1 || port > 65_535) {
    throw new Error("MODEL_GATEWAY_PORT must be a valid TCP port");
  }
  return port;
}

function isPrivateBindHost(value: string): boolean {
  const normalized = value.toLowerCase();
  if (normalized === "localhost" || normalized === "::1") {
    return true;
  }
  const family = isIP(normalized);
  if (family === 4) {
    const [first, second] = normalized.split(".").map(Number);
    return first === 127 || first === 10 || (first === 172 && second >= 16 && second <= 31) || (first === 192 && second === 168);
  }
  return family === 6 && (normalized.startsWith("fc") || normalized.startsWith("fd"));
}