---
name: jev
description: Use when data-box (or an agent building on it) needs a fast, typed decision rather than generated text - pick one of up to 255 options, answer yes/no with a probability, or score against levels - through TypeSafe's Jev (POST api.typesafe.ai/v1/systemone). Covers where Jev sits in data-box's intake, planning and execution, its shadow-then-certified modes, its monthly cap, and what it must never see or decide. Milestone D8; the key is not on the box yet.
---

# Jev (TypeSafe System One)

Jev is TypeSafe's decision model. It takes a `state` (text or JSON) and typed questions, and returns typed answers with calibrated probabilities and a confidence.

| Question type | Answer |
|---|---|
| **Choice** | one of up to 255 options |
| **Noul** | yes/no, as a probability |
| **Score** | a level on a rubric you define |

It **never writes text**. Counting, arithmetic, dates and generation stay in code.

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
{"model": "jev-latest", "state": {...}, "questions": {...}}
```

## Where data-box uses it (D8)

Code decides first. Jev is asked only where code's answer is weak.

| Decision point | Type | Jev chooses |
|---|---|---|
| `intake.kind`, `intake.entity` | choice | what kind of request, what entity |
| `intake.intent` | yes/no | is this "people asking to buy X" (a Lead Radar request) |
| `intake.named_source` | choice | which provider was meant, after the alias match fails |
| `plan.relevance` | yes/no | borderline cases of the Alexandria relevance gate |
| `plan.lane_order` | choice | tie-break among at most 5 lanes code already ranked |
| `preflight.sample_fit` | yes/no | do the samples match the entity and topic (golf courses in a roofers pull) |
| `execute.same_entity` | yes/no | borderline dedupe pairs, a bounded number per run |
| `scrape.real_page` | yes/no | a real page or a block page, when code cannot tell |

**Modes** (planned for D8: `DATABOX_JEV_MODE`):
- **off**;
- **shadow:** decisions are logged next to what code did, and change nothing;
- **active:** only certified decision points act, and only at confidence ≥0.95.

## Never

- Let Jev approve a plan, raise a cap, or spend provider money.
- Send it a phone number, email address or LinkedIn URL. Decisions work on names, categories and page text.
- Ask it to count, compare dates, do arithmetic or write a value. Do those in code, and ask Jev a Choice over candidates instead ([jaggedness](references/vendor-docs/pages/model-jaggedness/jev-1.13.md)).
- Exceed its monthly cap (planned for D8: `DATABOX_JEV_MONTHLY_USD`, default $5). Over the cap, code's answer stands.

## References

- [references/charter.md](references/charter.md), [references/handoff.md](references/handoff.md), [references/best-practices.md](references/best-practices.md), [references/lessons.md](references/lessons.md), [references/cost-map.md](references/cost-map.md), [references/recipes.md](references/recipes.md)
- [references/vendor-docs/](references/vendor-docs/PROVENANCE.md): TypeSafe's `llms-full.txt` and the API, models, confidence, routing, jaggedness and error pages, mirrored 2026-09-30.
- The repo's `skills/typesafe-ai/` holds the fuller page-by-page mirror, with raw copies, from 2026-09-17.
