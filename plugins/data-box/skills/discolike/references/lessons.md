# DiscoLike: lessons

- **2026-09 (the M2 key check; still true on 2026-09-30): the key is inactive.**
  - A live check from the server got 403 "inactive".
  - **Rule:** `status` shows DiscoLike as configured but refused, with the reason. D5 maps that answer to `AuthRejected`, which stops a run at no charge.
- **2026-09-30: the local notes disagree with the vendor's docs.**
  - The disco-plugin and the Hermes skills disagree on whether Validate is on MCP, on DiscoGen's price ($0.01 an item, "$0.10 a record", or $0.30-2 per 100 domains), and on output folders.
  - The vendor mirror is dated and hashed.
  - **Rule:** the vendor docs are the reference, and local notes are leads to check.
- **2026-09-30: "+stem" is not documented.**
  - The plan assumed a `+stem` query syntax. Neither the vendor docs nor the local plugin define it.
  - **Rule:** no query syntax goes into code until a free count shows what it does.
- **2026-06 (disco-plugin): an LLM-mediated gate is not a gate.**
  - The Hermes copy asks through `clarify()`. The Claude plugin's hook returns `permissionDecision: "ask"`, which a person must answer.
  - **Rule:** data-box's plugin gates `execute` the same hard way, and Hermes gets a protocol with hard stops (D7).
