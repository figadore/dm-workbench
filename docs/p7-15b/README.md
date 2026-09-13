# P7-15b Whole-Adventure Prototype

This disposable file adapter exercises one complete structured content submission over an existing
supported map grammar. Fixture mode is provider-free; explicitly authorized live mode samples one
brief and one condition. Neither is the production two-pass pipeline, a review workspace or proof
that a one-shot is ready to run. `PROJECT_STATUS.md` owns task state.

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
the default emits both. These fixture commands never enable live transport. No mode adds an editor.

## Explicit single-case live trial

After user authorization, run in an environment with the private gateway URL and internal caller
secret configured (for example the Workbench container). Never pass provider credentials to Python:

```bash
python scripts/dungeon-whole-adventure-prototype.py --live \
  --provider openai-codex --model gpt-6-astra --consistency on \
  --brief tests/evals/golden/whole_adventure/astra_feasibility_brief.json \
  --output generated/p7-15b-astra-high-trial
```

`--live` requires one explicit brief, provider, exact model and consistency condition. It cannot run
both arms or synthetic failure injection. Catalog/authentication checks happen before submission;
there is no model fallback. High reasoning is the Workbench's `deep` effort, verified against Astra's
wire request in a provider-free test. Normalized task profiles keep one initial call plus at most one
technical repair under a **600-second cumulative model-run deadline**. This clock excludes engineering
setup and human review. A successful first submission stops after one call.

For the authorized feasibility trial, Reese requested usage measurement rather than a financial cap.
The profile therefore uses advertised model capacity, bounded by the existing task-contract maximum
of 262,144 cumulative tokens and the transport's 131,072-token output ceiling. Astra advertises
128,000 output tokens; its profile uses that value. These are technical safety limits, not a spending
budget, and are still validated. Ordinary smaller task limits remain unchanged. SDK retries are off;
Codex uses SSE with no WebSocket fallback submission. The gateway counts cached input as input usage.
Subscription dollar cost stays unknown; do not equate catalog prices with actual charges.

Live mode claims a new private output directory and writes input pins and body-free attempt journals
before contacting the provider. It preserves interrupted/failed directories rather than cleaning
away evidence; a missing final manifest means an incomplete run, not permission to retry it. Never
rerun to replace an interrupted attempt without checking its journal and obtaining any needed new
call authorization. Only accepted creative content is saved as `submission.json` and guide prose;
raw provider envelopes and reasoning are not persisted. Production artifact/canon writes remain absent.

The first Astra feasibility packet lives under ignored `generated/p7-15b-astra-high-01/`. It used two
calls (initial reference rejection, then accepted technical repair), 321,752 ms of gateway time,
30,069 normalized input tokens including cached input, and 8,241 output tokens. The accepted guide
is 2,987 words—49.35% above the roughly 2,000-word target. This is an actual provider measurement,
not evidence of human readiness or a consistency-instruction effect. No editorial rewrite or third
call was made. The first rejection arose from optional prose entries targeting features absent from
the fixed plan; the repair moved that material into existing content slots. Reese subsequently spent
**28 minutes reviewing** and reported substantial confusion and an unusable result. This failed the
readiness target; it is not a minor-polish success. [The human-review record](reviews/astra-high-reese-review.md)
separates actual feedback from code-inspection findings. The authored guide remains unedited.

A local step-by-step audit is saved as
`generated/p7-15b-astra-high-audit/prompts-and-responses.md`. It includes the exact initial normalized
messages/schema, retained accepted submission and known repair instruction/diagnostics. The rejected
first submission and complete repair request were not retained; those gaps are explicitly labeled.
No new generation or runtime correction was made to produce the audit.

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

Live trials require explicit provider authorization and an agreed bounded attempt/time policy,
model/effort, guide-length objective and usage/spending policy; this feasibility trial explicitly
waives a monetary ceiling, not technical validation. The first sample has 28 reported human review
minutes and a negative result; editing time and tabletop duration remain unknown. Readiness still
needs usable fresh-case results, actual human effort and a tabletop walkthrough.
The ten-minute/no-core-authoring target is unchanged; this prototype does not cross that gate or justify
an added editorial call or broader pipeline/workspace investment.

## Planned correction: The Last Pay Chest as the structural reference

Reese explicitly selected [The Last Pay Chest](../p7-15a/last-pay-chest.md), with Nell and Iona,
not the earlier Bellglass/Neris adventure. The [P7-15b implementation-plan task](../../dm-assistant-implementation-plan.md#p7-15b--try-whole-adventure-authoring)
and [architecture §13](../../dm-assistant-technical-architecture.md#13-dungeon-generation) specify the
correction; this documentation does not implement it or authorize another generation.

The reference provides a short pitch/assumptions and map access, **The job** with hook and essential
DM context, map-numbered rooms with their own evidence/procedures/triggered dialogue and routes, then
**Settle up**. Use that actual information flow with flexible room sections—not a newly invented
preferred ordering, a mandatory template for every room, or the same payroll story. Its noncombat
premise, 60–90-minute target and licensed map are not constraints or validated inputs for other seeds.

The planned adapter change supplies ordinary room-local private prose independently of mechanical
feature reservations, one code-owned map/guide numbering scheme, code-derived exits and lossless
projection of required authored information. Small provider-free note/clue/delivery/rendering/secrecy
fixtures precede live trials. Later diagnostic capture needs a narrow explicit private policy for
requests and submitted creative candidates, including rejected ones, without raw transport/reasoning
or Git retention. The reviewed failed packet remains untouched; seed selection is a separate decision.

## Focused checks

```bash
uv run --frozen pytest -q tests/unit/test_whole_adventure_prototype.py \
  tests/evals/test_dungeon_evals.py tests/unit/test_dungeon_guide_content_contract.py \
  tests/unit/test_dungeon_review_packet.py tests/unit/test_prompted_dungeon_workflow.py
```
