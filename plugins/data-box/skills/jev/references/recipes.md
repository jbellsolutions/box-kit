# Jev: recipes

Each recipe is a decision point in data-box (D8). Code builds the candidates, Jev answers, and code acts only on a certified point at confidence ≥0.95.

## `preflight.sample_fit`: are these samples the right thing?

```json
{
  "model": "jev-latest",
  "state": {
    "request": "roofing contractors in Austin TX",
    "samples": ["Summit Roofing - roof repair and replacement", "Lions Municipal Golf Course - tee times"]
  },
  "questions": {
    "fit": {"type": "noul", "instructions": "Are most samples businesses that do roofing work? A golf course, ticket seller or retailer is not."}
  }
}
```

- **Low probability:** the lane is dropped before the bulk pull, and the plan says why.
- **Confidence under 0.95:** code's topic-word check stands.

## `plan.lane_order`: tie-break among ranked lanes

- Code ranks the lanes by records per dollar × coverage × field fit.
- When the top lanes are within 5%, Jev gets a Choice over at most 5 lane names, with the request and each lane's contract summary as state.

## `execute.same_entity`: borderline dedupe

- Two records share a name but not a phone.
- The state has name, city, category and website domain, never the phone or email.
- A Noul asks: "the same business?" Code merges only above the certified threshold, and only up to a bounded count per run.
