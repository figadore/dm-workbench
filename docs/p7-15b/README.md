# P7-15b Provider-Free Whole-Adventure Prototype

This disposable file adapter exercises one complete structured content submission over an existing
supported map grammar. It is not the production two-pass pipeline, a review workspace, a live
comparison, or evidence that a one-shot is ready to run. `PROJECT_STATUS.md` owns task state.

## Run it

From the repository root, without PostgreSQL, gateway login, or network access:

```bash
uv run --frozen python scripts/dungeon-whole-adventure-prototype.py \
  --output generated/p7-15b-prototype
```

The output directory must not exist. It contains:

- one shared validated map, plan, layout request and submission schema;
- `dm-map.svg` and independently audience-filtered `player-map.svg`;
- three cases, each with `on/` and `off/` consistency conditions;
- each condition's exact input, brief, accepted synthetic submission, `dm-guide.md`, body-free
  `measurement.json`, and blank `human-review.md` worksheet;
- a hash manifest covering the files, including the exact guide bytes.

**Treat the whole directory as DM-private.** Only `player-map.svg` is a player export. There is no
player guide, approval, canonical write, database publication, or retained artifact version.

To exercise a reference rejection followed by its one allowed technical repair, use
`--scenario reference-repair` with a different output directory. `--scenario rejected` preserves both
failed attempts, emits no accepted guide, and exits 1. `--consistency on` or `off` selects one arm;
the default emits both. No option enables live transport or an editorial pass.

## Chosen inputs and comparison boundary

`tests/evals/golden/whole_adventure/plan.json` uses the existing five-room critical path plus Annex
branch, one secret bypass/loop and one key gate, adapted from the supported review-fixture topology.
It removes the reference archive's setting, trap and linked-machine story rather than forcing those
onto different adventures. The ordinary compiler, layout constructor and independent topology/geometry
validators build the fixed map once; model submissions cannot change it.

The three synthetic briefs adapt the Tier A signal-house, embassy and gallery settings to **that same
five-room map**. They vary navigation, social inference and investigation guidance. Each brief records
its historical source and mismatch: original room counts/terrain requests and prior packets are not
matched comparisons. The two embassy facts are explicit synthetic preparation inputs, not a campaign
context or retrieval shortcut. No real campaign or published rules content is used.

The gallery is reserved from live prompt tuning, not hidden from provider-free tests or this code's
author. Fresh held-out live briefs must be chosen after a prompt freeze; this fixture does not establish
held-out authoring performance.

Within each case, both conditions use identical plan, map, brief, assumptions, tool schema, profile,
rendering, output ceiling and cumulative technical-repair policy. Their initial inputs differ **only**
by appending the general causal/counterfactual authoring objective. Repair retains that exact initial
input and may replace the complete submission only to correct structural/reference diagnostics.
Neither condition calls an editor, performs an outline pass or changes a production task prompt.

## Reused boundaries and limitations

The experiment wraps the existing `DungeonGuideContentPlan` with five bounded overview prose fields;
it does not introduce persistent story-state records or a parallel production engine. It reuses
`StructuredSubmissionRunner`, `reserve_structured_submission_repair`, existing guide reference checks,
map construction/validation, guide projection and rendering. The adapter additionally requires a
play-content entry for the fixed gate dependency, which the legacy optional-content validator does
not itself require. A single cumulative deadline/budget covers initial submission and at most one
technical repair. Unknown usage blocks repair; measured overages block acceptance.

Schema/reference acceptance is **technical only**. Typed topology/mechanics remain code-owned and
unchanged. Nonempty prose and these validators cannot prove causal consistency, actual clue usability,
absence of unsupported mechanical claims in prose, map/prose agreement or session length. Missing
play material and questionable prose must remain review blockers, not an implied approval.

The scripted responses intentionally ignore the consistency switch and are short plumbing samples,
not full-length adventure-quality exemplars. Identical output between conditions proves no prompt
effect. The worksheet is blank, condition labels are visible, and no AI score or invented human time
is included. The intended authoring guide budget is roughly 2,000 words; the samples do not demonstrate
that budget or the three-hour session target.

Reports retain every dispatched attempt, schema/reference failures, repair denial arithmetic,
cumulative token counters and local gateway-call elapsed time. The fixture counters (10,000 input /
2,000 output per call) and generous test ceilings are **synthetic accounting inputs, not measured
provider usage or recommended live budgets**. Cost and human effort remain null. Guide length uses
`len(complete_rendered_markdown.split())`, including headings and deterministic mechanics. Rejected
candidates are not accepted guide exports. The CLI continues across all cases so one rejection does
not hide the others; unexpected programming errors fail the staged packet write rather than publish
partial output.

Any live adapter/trial requires separately agreed model/effort, cumulative attempts/tokens/cost/time,
guide-length and human-feedback budgets plus explicit provider authorization. Readiness still needs
fresh-case human missing-authoring/causal-repair observations, actual effort and a tabletop walkthrough.
The ten-minute/no-core-authoring target is unchanged; this prototype does not cross that gate or justify
an added editorial call or broader pipeline/workspace investment.

## Focused checks

```bash
uv run --frozen pytest -q tests/unit/test_whole_adventure_prototype.py \
  tests/evals/test_dungeon_evals.py tests/unit/test_dungeon_guide_content_contract.py \
  tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py
```
