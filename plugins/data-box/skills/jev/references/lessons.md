# Jev: lessons

- **2026-09 (the archived Super Browser dispatcher, cited in the 2026-09-23 plan): Jev routed 2 of 12 requests by itself, median 314 ms.**
  - It is fast, but it cannot plan: the rest needed an LLM.
  - **Rule:** in data-box, Jev decides typed sub-questions inside stages that code runs. It is never the router.
- **2026-09-23 (browser-box B2/B3): Jev is a good grounder.**
  - Jev picks the page element for each step in `act`, and `/api/command` passed 8/8 against the live TypeSafe key.
  - The later B5 benchmark found act (Jev per step, with the caller planning) beat the whole-goal browser agent.
  - **Rule:** use Jev where the options are concrete and code built them.
- **2026-09-28 (data-box D1): the survey needed a relevance judgment, and code did it with topic words.**
  - Borderline tools, where the description is near the topic but not on it, are where a yes/no from Jev helps.
  - **Rule:** `plan.relevance` is a D8 decision point, in shadow first.
- **2026-09-30 (TypeSafe docs): counting, numbers, dates and generation are Jev 1.13's weak spots.**
  - **Rule:** none of data-box's decision points asks for them. Counts, prices and dates stay in code.
