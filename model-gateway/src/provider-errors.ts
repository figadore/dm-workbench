export type SafeProviderErrorCode =
  | "usage_limit"
  | "rate_limited"
  | "authentication_required"
  | "provider_access_denied"
  | "model_unavailable"
  | "provider_request_rejected"
  | "provider_unavailable"
  | "provider_error";

export interface SafeProviderError {
  readonly code: SafeProviderErrorCode;
  readonly message: string;
}

export interface ProviderContractDiagnostic {
  readonly http_status: number | null;
  readonly mentions_max_output_tokens: boolean;
  readonly parameter_rejection: boolean;
  readonly max_output_tokens_rejection: boolean;
}

/**
 * Produce an opt-in, body-free fingerprint for one transient contract diagnosis.
 *
 * The provider text is reduced in memory to booleans over one server-owned field name.
 * No provider text, arbitrary code, response body, prompt, or credential is returned.
 */
export function fingerprintProviderContractError(
  value: unknown,
  httpStatus?: number,
): ProviderContractDiagnostic {
  const errorMessage =
    value !== null && typeof value === "object" && "errorMessage" in value
      ? (value as { errorMessage?: unknown }).errorMessage
      : undefined;
  const text = typeof errorMessage === "string" ? errorMessage : "";
  const mentionsMaxOutputTokens = /\bmax_output_tokens\b/i.test(text);
  const parameterRejection =
    /(?:unknown|unrecognized|unsupported|invalid)\s+(?:parameter|field)|(?:parameter|field)[^.]{0,80}(?:not supported|unsupported|invalid)/i.test(text);

  return {
    http_status:
      httpStatus !== undefined
      && Number.isSafeInteger(httpStatus)
      && httpStatus >= 100
      && httpStatus <= 599
        ? httpStatus
        : null,
    mentions_max_output_tokens: mentionsMaxOutputTokens,
    parameter_rejection: parameterRejection,
    max_output_tokens_rejection: mentionsMaxOutputTokens && parameterRejection,
  };
}

/**
 * Reduce transient provider failure detail to a stable body-free category.
 *
 * Provider text is inspected only in memory and is never returned or logged. An HTTP
 * status supplied by pi-ai's response callback is useful when an adapter discards that
 * status while building its final AssistantMessage error.
 */
export function classifyProviderError(
  value: unknown,
  httpStatus?: number,
): SafeProviderError {
  const errorMessage =
    value !== null && typeof value === "object" && "errorMessage" in value
      ? (value as { errorMessage?: unknown }).errorMessage
      : undefined;

  if (typeof errorMessage === "string") {
    if (/usage limit|insufficient_quota|quota[^.]*reached|quota[^.]*exceeded|out of budget/i.test(errorMessage)) {
      return { code: "usage_limit", message: "model provider usage limit reached" };
    }
    if (/rate limit|too many requests|rate_limit_exceeded/i.test(errorMessage)) {
      return { code: "rate_limited", message: "model provider rate limit reached" };
    }
    if (/unauthorized|authentication|credential|invalid token|token expired/i.test(errorMessage)) {
      return { code: "authentication_required", message: "provider authentication is required" };
    }
    if (/forbidden|permission denied|access denied|not entitled|account[^.]*not allowed/i.test(errorMessage)) {
      return { code: "provider_access_denied", message: "provider access was denied" };
    }
    if (/model[^.]*not (?:found|available|supported)|unknown model|unsupported model/i.test(errorMessage)) {
      return { code: "model_unavailable", message: "requested model is unavailable" };
    }
    if (/invalid[_ -]?request|bad request|unknown (?:parameter|field)|unrecognized (?:parameter|field)|unsupported (?:parameter|field)|(?:parameter|field)[^.]*not supported|schema[^.]*invalid/i.test(errorMessage)) {
      return { code: "provider_request_rejected", message: "model provider rejected the request contract" };
    }
    if (/service unavailable|temporarily unavailable|upstream[^.]*unavailable|connection refused/i.test(errorMessage)) {
      return { code: "provider_unavailable", message: "model provider is unavailable" };
    }
  }

  if (httpStatus !== undefined) {
    if (httpStatus === 400 || httpStatus === 409 || httpStatus === 422) {
      return { code: "provider_request_rejected", message: "model provider rejected the request contract" };
    }
    if (httpStatus === 401) {
      return { code: "authentication_required", message: "provider authentication is required" };
    }
    if (httpStatus === 402 || httpStatus === 403) {
      return { code: "provider_access_denied", message: "provider access was denied" };
    }
    if (httpStatus === 404) {
      return { code: "model_unavailable", message: "requested model is unavailable" };
    }
    if (httpStatus === 429) {
      return { code: "rate_limited", message: "model provider rate limit reached" };
    }
    if (httpStatus === 408 || httpStatus >= 500) {
      return { code: "provider_unavailable", message: "model provider is unavailable" };
    }
  }

  return { code: "provider_error", message: "model stream failed" };
}
