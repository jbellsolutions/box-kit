# Jev: charter

**The engine, not a data source.** Jev makes typed decisions inside data-box's three stages. It fetches no data and holds no records.

## Rules

1. **Code first.** A decision goes to Jev only when code's own answer is weak: an ambiguous parse, a borderline match, or a tie.
2. **Typed decisions only.** Choice, yes/no or score, over candidates code built. Never free text, counts, dates or arithmetic.
3. **Shadow before active.** Every decision point starts in shadow. It acts only once **certified**:
   - at least 100 held-out cases;
   - precision ≥99% where spend is affected, and ≥98% where it is not;
   - zero unauthorized actions.

   Active decisions need confidence ≥0.95. Anything lower falls back to code.
4. **No authority over money.** Jev never approves, never raises a cap and never triggers a paid call on its own.
5. **No contact data.** Phones, emails and LinkedIn URLs are stripped from `state`.
6. **Its own budget.** `DATABOX_JEV_MONTHLY_USD` (planned, D8), default $5, is metered in the ledger like any provider. When it is spent, code decides.
7. **The key is `TYPESAFE_API_KEY` on the box.** It never goes in a URL, log, commit, skill or chat.
