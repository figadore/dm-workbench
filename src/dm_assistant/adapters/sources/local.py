"""Symlink-safe bounded local source reader for allowlisted roots."""

import errno
import os
import stat
from collections.abc import Mapping
from pathlib import Path

from dm_assistant.adapters.sources.port import SourceBytes
from dm_assistant.errors import InvalidInputError
from dm_assistant.modules.library.contracts import SourceLocator, SourcePresence

_DEFAULT_MAXIMUM_BYTES = 8 * 1024 * 1024
_READ_SIZE = 1024 * 1024


class _SourceMissingError(Exception):
    """Internal distinction used only to avoid retiring unsafe paths."""


class LocalSourceReader:
    """Open relative paths beneath explicitly named roots without symlink traversal."""

    def __init__(
        self,
        roots: Mapping[str, Path],
        *,
        maximum_bytes: int = _DEFAULT_MAXIMUM_BYTES,
    ) -> None:
        if not roots:
            raise ValueError("at least one source root is required")
        if maximum_bytes < 0:
            raise ValueError("maximum_bytes cannot be negative")
        normalized: dict[str, Path] = {}
        for label, configured_path in roots.items():
            try:
                SourceLocator(root_label=label, relative_path="_")
            except ValueError:
                raise ValueError("source root label is invalid") from None
            expanded = configured_path.expanduser()
            if not expanded.is_absolute():
                raise ValueError("source roots must be absolute")
            try:
                metadata = expanded.lstat()
            except OSError:
                raise ValueError("source root is unavailable") from None
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("source roots must be real directories")
            resolved = expanded.resolve(strict=True)
            if resolved in normalized.values():
                raise ValueError("source roots must be distinct")
            normalized[label] = resolved
        self._roots = normalized
        self._maximum_bytes = maximum_bytes

    def ensure_root(self, root_label: str) -> None:
        if root_label not in self._roots:
            raise InvalidInputError("The source root is not configured.")

    def read(self, locator: SourceLocator) -> SourceBytes:
        self.ensure_root(locator.root_label)
        try:
            descriptor = self._open_descriptor(locator)
        except _SourceMissingError:
            raise InvalidInputError("The source file does not exist.") from None
        try:
            chunks: list[bytes] = []
            byte_size = 0
            while True:
                try:
                    chunk = os.read(descriptor, _READ_SIZE)
                except OSError:
                    raise InvalidInputError("The source file cannot be read.") from None
                if not chunk:
                    break
                byte_size += len(chunk)
                if byte_size > self._maximum_bytes:
                    raise InvalidInputError("The source file is too large.")
                chunks.append(chunk)
        finally:
            os.close(descriptor)
        return SourceBytes(
            source_path=locator.registry_path,
            data=b"".join(chunks),
        )

    def probe_registry_path(self, source_path: str) -> SourcePresence:
        try:
            locator = SourceLocator.from_registry_path(source_path)
        except ValueError:
            raise InvalidInputError("The registered source path is invalid.") from None
        self.ensure_root(locator.root_label)
        try:
            descriptor = self._open_descriptor(locator)
        except _SourceMissingError:
            return SourcePresence.MISSING
        os.close(descriptor)
        return SourcePresence.PRESENT

    def _open_descriptor(self, locator: SourceLocator) -> int:
        root = self._roots[locator.root_label]
        directory_flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        file_flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        descriptors: list[int] = []
        try:
            try:
                current = os.open(root, directory_flags)
            except OSError:
                raise InvalidInputError("The source root is unavailable.") from None
            descriptors.append(current)
            parts = locator.relative_path.split("/")
            for part in parts[:-1]:
                try:
                    current = os.open(
                        part,
                        directory_flags,
                        dir_fd=current,
                    )
                except OSError as error:
                    self._raise_open_error(error)
                descriptors.append(current)
            try:
                source_descriptor = os.open(
                    parts[-1],
                    file_flags,
                    dir_fd=current,
                )
            except OSError as error:
                self._raise_open_error(error)
            try:
                metadata = os.fstat(source_descriptor)
                if not stat.S_ISREG(metadata.st_mode):
                    raise InvalidInputError("The source path must be a regular file.")
                if metadata.st_size > self._maximum_bytes:
                    raise InvalidInputError("The source file is too large.")
            except BaseException:
                os.close(source_descriptor)
                raise
            return source_descriptor
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    @staticmethod
    def _raise_open_error(error: OSError) -> None:
        if error.errno == errno.ENOENT:
            raise _SourceMissingError from None
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise InvalidInputError(
                "The source path cannot contain symbolic links."
            ) from None
        raise InvalidInputError("The source path cannot be accessed safely.") from None
