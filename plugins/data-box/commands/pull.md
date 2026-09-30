---
description: Build a list of businesses or people (leads) through data-box, plan first — survey every source, show the priced plan, execute only on your yes.
argument-hint: <what, how many, where> e.g. "50 roofing contractors in Austin TX with phone and website"
allowed-tools: [Read]
---

Use the `data-box` skill and its four steps for: $ARGUMENTS

1. Read the request into `plan` arguments: `request`, `kind: "pull"`, `entity`, `count`, `fields`,
   `queries`, `geo` (one entry per place), and `sources` only if a source was named. If the count
   or the place is missing, ask before planning.
2. Call the data-box `plan` tool and wait for it (it runs a small preflight).
3. Present the plan the way the skill describes: what was understood, sources considered by tier
   (and why the notable ones cannot run), the lanes with credits and dollars, the preflight
   samples, every warning, and "Run it for up to $X?".
4. Stop there. Call `execute` with the `plan_id` and `approve: true` only after an explicit yes in
   this conversation. Then report unique records against the target, what each lane did, the cost,
   and offer a CSV export with `job` (`action: "export"`).

If `$ARGUMENTS` is empty, ask what to pull.
