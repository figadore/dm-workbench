"""Typed Library classification and reconciliation contract tests."""

import uuid

import pytest
from pydantic import ValidationError

from dm_assistant.modules.library import (
    AuthorityClass,
    CorpusKind,
    DocumentType,
    IngestSource,
    ReconcileMissingSources,
    RevisionClassification,
    Ruleset,
    SourceLocator,
    SourceScope,
    SourceVisibility,
    VisibilityLabel,
)


def test_revision_classification_accepts_safe_campaign_and_rules_sources() -> None:
    plan = RevisionClassification(
        corpus=CorpusKind.CAMPAIGN,
        document_type=DocumentType.PLAN_OR_ADVENTURE,
        authority_class=AuthorityClass.PREPARATION,
        ruleset=None,
        visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
    )
    rules = RevisionClassification(
        corpus=CorpusKind.RULES,
        document_type=DocumentType.RULES_REFERENCE,
        authority_class=AuthorityClass.OFFICIAL_RULES,
        ruleset=Ruleset.DND_5E_2024,
        visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
    )

    campaign_creature = RevisionClassification(
        corpus=CorpusKind.CAMPAIGN,
        document_type=DocumentType.CREATURE_OR_BESTIARY_RECORD,
        authority_class=AuthorityClass.REFERENCE,
        ruleset=Ruleset.DND_5E_2024,
        visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
    )

    assert plan.authority_class is AuthorityClass.PREPARATION
    assert rules.ruleset is Ruleset.DND_5E_2024
    assert campaign_creature.corpus is CorpusKind.CAMPAIGN


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (
            {
                "corpus": CorpusKind.RULES,
                "document_type": DocumentType.RULES_REFERENCE,
                "authority_class": AuthorityClass.REFERENCE,
                "ruleset": None,
                "visibility": VisibilityLabel(policy=SourceVisibility.DM_ONLY),
            },
            "rules corpus revisions require a ruleset",
        ),
        (
            {
                "corpus": CorpusKind.RULES,
                "document_type": DocumentType.RULES_REFERENCE,
                "authority_class": AuthorityClass.OFFICIAL_RULES,
                "ruleset": Ruleset.DND_5E_2014,
                "visibility": VisibilityLabel(policy=SourceVisibility.PUBLIC),
            },
            "official rules default to dm_only visibility",
        ),
        (
            {
                "corpus": CorpusKind.CAMPAIGN,
                "document_type": DocumentType.PLAN_OR_ADVENTURE,
                "authority_class": AuthorityClass.REFERENCE,
                "ruleset": None,
                "visibility": VisibilityLabel(policy=SourceVisibility.DM_ONLY),
            },
            "preparation documents require preparation authority",
        ),
    ],
)
def test_revision_classification_rejects_unsafe_combinations(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        RevisionClassification.model_validate(payload)


def test_visibility_label_requires_unique_explicit_audience_ids() -> None:
    label = VisibilityLabel(
        policy=SourceVisibility.EXPLICIT_AUDIENCE,
        audience_ids=("player-a", "player-b"),
    )
    assert label.audience_ids == ("player-a", "player-b")

    with pytest.raises(ValidationError, match="requires audience IDs"):
        VisibilityLabel(policy=SourceVisibility.EXPLICIT_AUDIENCE)
    with pytest.raises(ValidationError, match="must be unique"):
        VisibilityLabel(
            policy=SourceVisibility.EXPLICIT_AUDIENCE,
            audience_ids=("player-a", "player-a"),
        )


def test_ingestion_command_requires_consistent_scope_and_explicit_retirement() -> None:
    campaign_id = uuid.uuid4()
    campaign_scope = SourceScope(
        campaign_id=campaign_id,
        corpus=CorpusKind.CAMPAIGN,
    )
    classification = RevisionClassification(
        corpus=CorpusKind.CAMPAIGN,
        document_type=DocumentType.REFERENCE_LORE,
        authority_class=AuthorityClass.REFERENCE,
        ruleset=None,
        visibility=VisibilityLabel(policy=SourceVisibility.DM_ONLY),
    )
    command = IngestSource(
        scope=campaign_scope,
        locator=SourceLocator(root_label="campaign", relative_path="lore.md"),
        classification=classification,
        title="Synthetic Lore",
    )
    assert command.scope.campaign_id == campaign_id

    with pytest.raises(ValidationError, match="corpus must match"):
        IngestSource(
            scope=SourceScope(campaign_id=None, corpus=CorpusKind.RULES),
            locator=command.locator,
            classification=classification,
            title="Synthetic Lore",
        )
    with pytest.raises(ValidationError):
        ReconcileMissingSources.model_validate(
            {
                "scope": campaign_scope,
                "root_label": "campaign",
                "confirm_retirement": False,
            }
        )
