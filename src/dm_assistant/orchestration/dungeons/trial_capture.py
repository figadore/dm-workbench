"""Opt-in private P7-15b creative records, never a gateway debug/transport dump."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import JsonValue

from dm_assistant.modules.modeling import PromptMessage, ResolvedModelRunProfile
from dm_assistant.orchestration.modeling.service import (
    GatewayCompletion,
    GatewayToolSchema,
)


class TrialCaptureError(RuntimeError):
    """Body-free, terminal capture failure; never authorize a retry or dispatch."""

    def __init__(self) -> None:
        super().__init__(
            "Private creative capture failed; preserve the incomplete directory. No automatic retry."
        )


class PrivateTrialCapture:
    """One explicitly opted-in synthetic trial; exclusive requests/candidates, mutable journal.

    Callers must review synthetic inputs as secret-free before opting in. Exact creative
    prose cannot also be automatically redacted. Credentials/transport/reasoning never
    enter this interface; unexpected transcript roles/signatures fail before dispatch.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._started = False
        try:
            directory.mkdir(
                mode=0o700
            )  # Exclusive, including refusal of existing symlinks.
            directory.chmod(0o700)
            self._write(".gitignore", b"*\n")
            self._write_json(
                "consent.json",
                {
                    "task": "P7-15b",
                    "creative_capture_enabled": True,
                    "scope": "one synthetic trial; exact requests and submission arguments only",
                    "inputs_reviewed_secret_free": True,
                    "retention": "preserve until user requests local deletion after review",
                },
            )
        except OSError:
            raise TrialCaptureError() from None

    def begin(self) -> None:
        if self._started:
            raise TrialCaptureError()
        self._started = True

    def request(
        self,
        number: int,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> None:
        if allowed_tools != ("submit_whole_adventure",) or any(
            message.role != "user" or message.opaque_continuity_signatures
            for message in messages
        ):
            raise TrialCaptureError()
        self._write_json(
            f"{number:02d}-request.json",
            {
                "profile": profile.model_dump(mode="json"),
                "messages": [message.model_dump(mode="json") for message in messages],
                "allowed_tools": list(allowed_tools),
                "tool_schemas": [
                    schema.model_dump(mode="json") for schema in tool_schemas
                ],
            },
        )

    def candidates(self, number: int, completion: GatewayCompletion) -> None:
        # Preserve allowed creative arguments even on invalid count/schema/reference/usage.
        # Never dump completion.content, call IDs, unknown tools, or a raw envelope.
        self._write_json(
            f"{number:02d}-candidates.json",
            [
                call.arguments
                for call in completion.tool_calls
                if call.tool_name == "submit_whole_adventure"
            ],
        )

    def journal(self, report: dict[str, JsonValue]) -> None:
        self._write_json("journal.json", report, replace=True)

    def _write_json(self, name: str, value: object, *, replace: bool = False) -> None:
        self._write(
            name,
            (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            replace=replace,
        )

    def _write(self, name: str, data: bytes, *, replace: bool = False) -> None:
        """Flush complete private bytes before atomic publication; never clobber evidence.

        Pending files survive write failure. A missing final manifest or pending journal
        state means incomplete evidence, not permission to retry. Only journal may replace.
        """
        try:
            descriptor, pending_name = tempfile.mkstemp(
                prefix=".pending-", dir=self.directory
            )
            pending = Path(pending_name)
            with os.fdopen(descriptor, "wb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            destination = self.directory / name
            if replace:
                os.replace(pending, destination)
            else:
                os.link(
                    pending, destination
                )  # Atomic exclusive publication, no overwrite.
                pending.unlink()
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            raise TrialCaptureError() from None
