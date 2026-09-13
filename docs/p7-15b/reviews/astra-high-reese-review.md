# P7-15b — Reese's Review of the Astra/High Feasibility Sample

This is a historical human-review record, not an approval, a model evaluation score or a current-task
handoff. `PROJECT_STATUS.md` owns task state. The reviewed adventure and its prompt audit remain
ignored private artifacts; this record does not copy provider response bodies into the repository.

## Artifact / Actual Human Evidence

- Reviewer: Reese, in the conversation following the first Astra/high feasibility trial.
- Artifact: `generated/p7-15b-astra-high-01/brass_orchard/on/dm-guide.md`.
- Guide SHA-256: `112e0cbc47dc65ee844806729ba63b748176c9129e6a913bfaf4e47c1f69f5ec`.
- Model: `openai-codex/gpt-6-astra`, high reasoning; two submissions, including one technical repair.
- **Actual reported review time: 28 minutes.** This is review time, not measured editing time,
  engineering setup, model latency, or tabletop play. No editing minutes or playtest supplied.
- Reese reports substantial confusion and does not know where to start fixing it. The result fails
  the roughly ten-minute/no-core-authoring readiness target; technical reference acceptance did not
  establish usability. Do not soften this into a request for minor polish or an unmeasured success.

## Reese's Feedback (Verbatim)

> this is probably the worst i've seen so far in this history of trying to make this dungeon generator. it too 28 minutes to review, i'm thoroughly confused and don't even know where to start

> The intro is a bit jarring, there’s no there’s no setting of the scene and just jumped straight into specific specifics of the adventure

> The horticultural theme is a bit unfamiliar. it’s kind of hard to follow just based on my lack of background knowledge

> The progression section mentions room names, but no numbers so I can’t really tell which rooms it’s referring to

> The ordering of the Guide is a hard to follow since it talks about progression and ending before it even introduces the rooms and everything that happens in them. A better order would be a brief introduction with background and read-aloud hook for players, and the things the dm needs to know ahead of time, followed by a room-by-room progression

> On the room by room guide it’s not really clear why it says there’s a note with a plant label on it, but it doesn’t say what the note contents are

> In map three I don’t know what a trial card is, nor does the party know after I read them that room’s read aloud text. Additionally, when referencing the other rooms, it should indicate a direction like east or north, but it just says the door towards the hall as a physical keyhole. which direction is that?

> It isn’t really clear what the travel cloaked Woman is doing in the side annex and I’m not really sure what is physically happening with the puzzle or how to solve it or find the secret door. The whole interaction is just confusing.

> The inner gate key section is also kind of unclear why it talks about entrance documents in this section. I don’t really know what I’m reading.

> The inner hall seems to have a puzzle and it mentions the trial cards that were found earlier, but those trial cards were never actually described and there’s no section read aloud in this room that tells the players what’s happening or what they’re supposed to do or anything

> The theme of this adventure is kind of tame and mundane, not very compelling

Reese also requested step-by-step prompts/responses (a Markdown document is acceptable), an explanation
of any unavailable material, and recommendations for proceeding. That request does not authorize a
new provider call, an editorial rewrite or silently replacing the reviewed artifact.

## Audit Findings (Code/Artifact Inspection, Not Additional Human Evidence)

1. **Brief selection:** the coding assistant chose the unfamiliar horticultural retrieval/custody
   premise and an already-accepted job. The authoring call did not independently choose the theme.
   System-neutral automatic procedures and restrictions on stat-block-dependent opposition narrowed
   the test. This was a high-effort model under a constrained adapter, not a clean model-capability
   ceiling test. Do not blame Reese's background knowledge for an insufficiently explained adventure.
2. **Content contract:** `DungeonGuideRoomNarrative` has arrival text/sensory details, not general
   room-local private content. Other prose is routed through reserved typed targets. The fixed plan
   contains no named features, while `validate_dungeon_guide_content` requires feature entries to
   match a pre-existing named feature. The first call's diagnostic journal rejects `entry_documents`,
   `gallery_trials` and `annex_bypass` as invalid feature targets. The first response body is missing;
   its literary quality or full before/after text cannot be established.
3. **Accepted repair:** retained structured fields place Entrance document interactions in the Annex
   key entry and Gallery evidence in the Hall puzzle entry. The repair instruction did not explicitly
   command those moves; it demanded reference fixes under the same restrictive contract. The evidence
   supports a contract/repair design failure, not a claim about the model's hidden reasoning.
4. **Presentation:** `render_trial_guide` hard-codes hook/background/opposition/progression/ending before
   the room guide. The room renderer prints puzzle solutions before situations. Its traversal order
   and map callout numbers disagree, producing two number systems. Exact opening directions exist in
   the package but are not projected as readable exits. Required sensory-detail fields are retained
   in the accepted submission but omitted from the Markdown renderer. These are code-owned defects,
   not matters for stronger reasoning or a new editorial model to repair in prose.
5. **Context:** the six initial user messages contain 33,449 content characters, including full map
   JSON and a content-empty projected guide. They do not include the reviewed Last Pay Chest, prior
   human feedback, or a usable example of the preferred reading order. Claims about context overload
   causing quality loss would still be hypotheses; the actual supplied inputs are inspectable.
6. **Audit gap:** exact initial normalized messages/schema and the accepted validated second submission
   were retained. The rejected first submission and full second prompt were not. The second prompt's
   fixed prefix/suffix and diagnostics can be reconstructed from code; its rejected-content portion
   cannot. Do not invent an exact transcript or rerun the model to pretend to recover it.

The local Markdown audit is `generated/p7-15b-astra-high-audit/prompts-and-responses.md`. It includes
an easy-to-read sequence, the exact initial instruction and brief, all six initial messages, full tool
schema, retained accepted response, diagnostics/measurements and clearly labeled missing evidence.
All twelve original manifest hashes were verified; current code reproduced the exact initial input
and final guide bytes. The reviewed packet was not modified. No additional model call was made.

## Recommendation Recorded for Discussion (Not Implemented Here)

- Treat this result as failed, not a draft Reese should keep reconstructing. Do not test cheaper
  models, add an editorial pass or broaden pipeline/workspace investment on this evidence.
- Simplify the file adapter around a readable whole guide with ordinary room-local DM content,
  retaining typed exact geometry/mechanics separately. A note does not need a structural feature
  reservation to have its text printed beside it. Reuse the existing validated map and security
  checks; no new story ontology, feature-specific pipeline or production framework is called for.
- Use Reese's requested reading order, one map-linked room-number scheme and code-derived exits.
  Keep observations, examinable text, NPC motives/reactions and play procedures together where they
  become relevant. Prove projection/placement with small provider-free examples before live trials.
- Any later authorized generation should use an agreed familiar, compelling premise and a small
  readable map brief. Judge the opening and first room before requesting another complete review;
  preserve the readiness target and permit stopping early. One success would still not prove reliability.
- For future diagnostic trials, explicitly define narrow private retention of submitted creative
  candidates (including rejected ones) and exact repair inputs. This is not permission to retain raw
  transport, reasoning, credentials or provider responses in Git. No retention/runtime change is made
  by this review record.
- If the simpler authoring path still requires repeated reconstruction, revisit the approach/product
  promise rather than assuming more infrastructure or explanation will make it work.
