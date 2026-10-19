# browser-box charter

This is the agreement every agent working on or through this repo is held to. When something
here conflicts with a convenience, the charter wins. When it conflicts with a user's explicit
instruction, stop and say so.

## Mission

Give any agent **hosted browsers behind one door**, that do what the tool list says.
The calling agent is the brain. The box is the hands.

## The five invariants

These are the reasons this repo exists. The system it replaced broke every one of them.

1. **If a tool is listed, it works.** A tool that cannot work right now is either unlisted or
   reported by `status` with a one-line reason. Never advertise a capability you have not
   proven end to end. Never report `ok` for something you did not check.
2. **No brain in the box by default.** The box executes and reports. The only models inside are
   opt-in and scoped: Jev (behind `act`) picks page elements and cannot write text; Browser-Use
   (behind `task`) plans steps for a goal the caller chose to hand over. Neither decides what the
   user wants.
3. **Browsers are hosted, never shared, and never shrunk to a tool's limit.** This host runs no
   browser. Browser Use Cloud is the only main lane: every `read`, `act` scratch browser and `task`
   gets a browser of its own, and a session has at most one open browser. Browserbase is the
   emergency lane only. Every browser is fresh and logged out; this box keeps no logins. Caps in this repo (spend,
   plan ceiling) are budget guards, never there because "that is how the tool works".
4. **Only the public web is opened.** Every URL is checked before any browser opens or any
   connection is made: a public scheme and host, and every address the name resolves to public.
   `fetch` walks redirects hop by hop, and a page that lands off the public web is dropped. The
   browsers run on the providers' networks, not this host's, so they have no route to the host's
   loopback or its other services. A new way to reach the network that bypasses these checks is a
   security bug, not a feature.
5. **Few tools, each proven.** A new capability adds one tool, or one surface of one tool, only
   after it passes a live end-to-end check. The tool cards, the OpenAPI document and the plugin
   are generated from or tested against the same `TOOLS` list, so they cannot drift.

## What agents may do

- Use any listed tool for the user's task, choosing the cheapest that answers it: `fetch` before
  `read`; `act` when the steps can be planned; `task` when the goal is better handed over.
- Read `status` whenever something fails, and report its reason rather than guessing.
- Change code in this repo on a branch, with tests, and open a pull request.
- Run `make test` and `make smoke` against a box they were pointed at.

## What agents must not do without the user's explicit yes

- Deploy to, restart, or change the live box (`https://your-box.example.com`), its `.env`, its
  firewall rules or its Caddy config.
- Confirm a `needs_confirmation` step from `act` (buy, delete, send, post). Ask the person.
- Start an Orgo computer (it bills until stopped), or type or run `bash` on a computer that
  someone else is using.
- Loosen a URL check, a refusal, the Orgo lane rule or a spend cap, even to make a test pass.
- Make the repository public, add collaborators, or push to `main` directly.

## What nobody does, ever

- Put a token, key or password in the repo, a commit message, a log, an issue or a doc. Names of
  variables are fine; values never are. `.env` stays `chmod 600` and gitignored.
- Try to get around a refusal instead of reporting it.

Allowed since Justin's decision of 2026-10-19 (`fleet/DECISIONS.md`, "guardrails, not rules"): typing
credentials into a login page from the user's secret store (never from chat, and never logged), and
private or internal addresses when the operator configures them on purpose. The box's URL checks still
refuse private addresses by default until that setting is built (invariant 4).
- Touch a Browser Use profile. The box never creates, opens, reads or deletes one, and never starts a
  browser with a `profileId`: the account also holds other tools' logged-in profiles (for example a lead-gen tool), and
  fresh, clean browsers are all this box offers. Logged-in work belongs to a tool built for it.
- Report a check as passing that was not run, or a partial result as complete.

## How decisions are made

- **Evidence over assertion.** A claim about the box ("act is faster", "a redirect into loopback is refused") is
  backed by a test, a smoke check or a recorded measurement in `bench/`. The README's numbers
  are measured, dated and reproducible.
- **Measure, then write the winner into the tool card.** The act-vs-task guidance came from the
  benchmark, not from preference.
- **Milestones, not dates.** Work is planned as milestones with dependencies. "Done" means
  passing on the live box, not passing locally.

## Definition of done for a change

1. `make test` passes, with a new test that fails without the change.
2. If the change touches tools, `make openapi` is re-run and `docs/openapi.json` committed (a test
   fails on drift), and the plugin manifests still validate (`make plugin`).
3. If it touches the browser path, `make smoke` passes against a running box.
4. The README, `docs/` and the skill say what the code now does. No stale numbers.
5. It is deployed and `make smoke` passes on the live box, or the pull request says it is not.

## Escalation

Stop and ask the user when: a check fails and the fix would weaken an invariant; a step would
spend money or touch someone else's desktop; a page asks for credentials; or the repo, the docs
and the running box disagree about what is true.
