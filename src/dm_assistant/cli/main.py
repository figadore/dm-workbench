"""DM Assistant command-line entry point."""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from pydantic import BaseModel

from dm_assistant import __version__
from dm_assistant.doctor import (
    collect_doctor_report,
    render_doctor_human,
    render_doctor_json,
)
from dm_assistant.errors import DomainError, InvalidInputError, format_cli_error
from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    LexicalSearchQuery,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)
from dm_assistant.orchestration.dungeons import (
    CreateDungeonWorkflow,
    ExportDungeonWorkflow,
    RegenerateDungeonWorkflow,
)
from dm_assistant.paths import resolve_allowlisted_file
from dm_assistant.runtime import workbench_runtime
from dm_dungeon import read_layout_request

app = typer.Typer(
    name="dm",
    help="DM Assistant Workbench.",
    no_args_is_help=True,
    add_completion=False,
)
campaign_app = typer.Typer(
    name="campaign",
    help="Minimal campaign-root administration.",
    no_args_is_help=True,
)
dungeon_app = typer.Typer(
    name="dungeon",
    help="Provider-independent Dungeon Studio workflows.",
    no_args_is_help=True,
)
library_app = typer.Typer(
    name="library",
    help="Immutable source documents and scoped lexical search.",
    no_args_is_help=True,
)
app.add_typer(campaign_app, name="campaign")
app.add_typer(dungeon_app, name="dungeon")
app.add_typer(library_app, name="library")


@app.callback()
def main() -> None:
    """Run DM Assistant commands."""


@app.command()
def version() -> None:
    """Show the installed DM Assistant version."""
    typer.echo(__version__)


@app.command()
def doctor(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit deterministic JSON instead of text."),
    ] = False,
) -> None:
    """Check safe configuration, database, extension, and schema readiness."""
    report = collect_doctor_report()
    output = render_doctor_json(report) if json_output else render_doctor_human(report)
    typer.echo(output)
    if not report.ready:
        raise typer.Exit(code=1)


@campaign_app.command("create")
def campaign_create(name: str) -> None:
    """Create the initial campaign root; this does not commit campaign facts."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            campaign = runtime.campaigns.create_campaign(name)
            typer.echo(
                json.dumps(
                    {"id": str(campaign.id), "name": campaign.name},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@campaign_app.command("list")
def campaign_list() -> None:
    """List safe campaign root IDs and names."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            typer.echo(
                json.dumps(
                    [
                        {"id": str(campaign.id), "name": campaign.name}
                        for campaign in runtime.campaigns.list_campaigns()
                    ],
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("ingest")
def library_ingest(
    relative_path: str,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    root: Annotated[str, typer.Option("--root")] = "root-0",
    title: Annotated[str, typer.Option("--title")] = "Source document",
    document_type: Annotated[DocumentType, typer.Option("--document-type")] = (
        DocumentType.REFERENCE_LORE
    ),
    authority: Annotated[AuthorityClass, typer.Option("--authority")] = (
        AuthorityClass.REFERENCE
    ),
    visibility: Annotated[SourceVisibility, typer.Option("--visibility")] = (
        SourceVisibility.DM_ONLY
    ),
    ruleset: Annotated[Ruleset | None, typer.Option("--ruleset")] = None,
) -> None:
    """Ingest one allowlisted Markdown/text source as an immutable revision."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.library_sources.ingest(
                    IngestSource(
                        scope=SourceScope(campaign_id=campaign_id, corpus=corpus),
                        locator=SourceLocator(
                            root_label=root,
                            relative_path=relative_path,
                        ),
                        classification=RevisionClassification(
                            corpus=corpus,
                            document_type=document_type,
                            authority_class=authority,
                            ruleset=ruleset,
                            visibility=VisibilityLabel(policy=visibility),
                        ),
                        title=title,
                    )
                )
            )


@library_app.command("documents")
def library_documents(
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
) -> None:
    """List immutable Library documents in one campaign/rules scope."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
            typer.echo(
                json.dumps(
                    [
                        {
                            "id": str(item.id),
                            "source_path": item.source_path,
                            "retired": item.retired,
                        }
                        for item in runtime.library_catalog.list_documents(scope)
                    ],
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("show-document")
def library_show_document(
    document_id: UUID,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    revision_id: Annotated[UUID | None, typer.Option("--revision")] = None,
) -> None:
    """Show one immutable document revision, latest by default."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            detail = runtime.library_catalog.show_document(
                SourceScope(campaign_id=campaign_id, corpus=corpus),
                document_id,
                revision_id,
            )
            typer.echo(
                json.dumps(
                    {
                        "id": str(detail.id),
                        "source_path": detail.source_path,
                        "revision_id": str(detail.revision_id),
                        "revision_number": detail.revision_number,
                        "content_hash": detail.content_hash,
                        "content": detail.content_snapshot,
                        "title": detail.title,
                        "document_type": detail.document_type,
                        "authority_class": detail.authority_class,
                        "ruleset": detail.ruleset,
                        "visibility_policy": detail.visibility_policy,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@library_app.command("search")
def library_search(
    query: str,
    campaign_id: Annotated[UUID | None, typer.Option("--campaign")] = None,
    corpus: Annotated[CorpusKind, typer.Option("--corpus")] = CorpusKind.CAMPAIGN,
    include_preparation: Annotated[bool, typer.Option("--include-preparation")] = False,
) -> None:
    """Search the active snapshot and return scoped immutable citations."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            scope = SourceScope(campaign_id=campaign_id, corpus=corpus)
            results = runtime.library_search.search(
                LexicalSearchQuery(
                    scope=scope,
                    query=query,
                    include_preparation=include_preparation,
                    visible_policies=(SourceVisibility.DM_ONLY,),
                )
            )
            typer.echo(
                json.dumps(
                    {
                        "scope": {
                            "campaign_id": str(campaign_id)
                            if campaign_id is not None
                            else None,
                            "corpus": corpus.value,
                        },
                        "results": [item.model_dump(mode="json") for item in results],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@dungeon_app.command("generate")
def dungeon_generate(
    input_path: Annotated[Path, typer.Argument(help="Allowlisted LayoutRequest JSON.")],
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
    title: Annotated[str, typer.Option("--title")],
    created_by: Annotated[str, typer.Option("--created-by")] = "dm",
) -> None:
    """Generate, validate, preview, and persist a hand-authored layout request."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            safe_path = resolve_allowlisted_file(
                input_path,
                runtime.settings.source_roots,
                maximum_bytes=2_000_000,
            )
            try:
                request = read_layout_request(safe_path)
            except (OSError, ValueError):
                raise InvalidInputError("The layout request is invalid.") from None
            result = runtime.dungeons.create(
                CreateDungeonWorkflow(
                    campaign_id=campaign_id,
                    title=title,
                    layout_request=request,
                    created_by=created_by,
                )
            )
            _emit_model(result)
            if not result.success:
                raise typer.Exit(code=1)


@dungeon_app.command("inspect")
def dungeon_inspect(
    artifact_id: UUID,
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
) -> None:
    """Inspect lifecycle and immutable version lineage."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.inspect(
                    campaign_id=campaign_id,
                    artifact_id=artifact_id,
                )
            )


@dungeon_app.command("compare")
def dungeon_compare(
    left_version_id: UUID,
    right_version_id: UUID,
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
) -> None:
    """Compare exact component IDs across two versions in one lineage."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.compare(
                    campaign_id=campaign_id,
                    left_version_id=left_version_id,
                    right_version_id=right_version_id,
                )
            )


@dungeon_app.command("regenerate")
def dungeon_regenerate(
    artifact_id: UUID,
    parent_version_id: UUID,
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
    seed: Annotated[int, typer.Option("--seed")],
    lock: Annotated[list[str] | None, typer.Option("--lock")] = None,
    summary: Annotated[str, typer.Option("--summary")] = "Regenerate dungeon.",
    created_by: Annotated[str, typer.Option("--created-by")] = "dm",
) -> None:
    """Regenerate from a parent while preserving selected exact components."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            result = runtime.dungeons.regenerate(
                RegenerateDungeonWorkflow(
                    campaign_id=campaign_id,
                    artifact_id=artifact_id,
                    parent_version_id=parent_version_id,
                    seed=seed,
                    locked_component_ids=tuple(lock or ()),
                    change_summary=summary,
                    created_by=created_by,
                )
            )
            _emit_model(result)
            if not result.success:
                raise typer.Exit(code=1)


@dungeon_app.command("export")
def dungeon_export(
    artifact_version_id: UUID,
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
) -> None:
    """Create exact-scale PDF and Roll20 assets for the current draft."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            asset_ids = runtime.dungeons.export(
                ExportDungeonWorkflow(
                    campaign_id=campaign_id,
                    artifact_version_id=artifact_version_id,
                )
            )
            typer.echo(
                json.dumps(
                    {"asset_ids": [str(item) for item in asset_ids]},
                    separators=(",", ":"),
                    sort_keys=True,
                )
            )


@dungeon_app.command("approve")
def dungeon_approve(
    artifact_id: UUID,
    artifact_version_id: UUID,
    campaign_id: Annotated[UUID, typer.Option("--campaign")],
    reason: Annotated[str, typer.Option("--reason")],
    actor: Annotated[str, typer.Option("--actor")] = "dm",
) -> None:
    """Explicitly approve preparation for play; this never commits campaign canon."""
    with _render_domain_errors():
        with workbench_runtime() as runtime:
            _emit_model(
                runtime.dungeons.approve(
                    campaign_id=campaign_id,
                    artifact_id=artifact_id,
                    artifact_version_id=artifact_version_id,
                    actor=actor,
                    reason=reason,
                )
            )


def _emit_model(model: BaseModel) -> None:
    typer.echo(
        json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


@contextmanager
def _render_domain_errors() -> Iterator[None]:
    try:
        yield
    except DomainError as error:
        typer.echo(format_cli_error(error), err=True)
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
