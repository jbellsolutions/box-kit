# Lead Radar: lessons

- **2026-09-23 (Super Browser's lead intent, archived): 0 qualified buyers from 149 candidates, and 0 from 62.**
  - Two problems:
    - **sourcing:** LinkedIn post search surfaces sellers; 265 collected, 1 buyer;
    - **gating:** all-must-pass 0.85 gates held real requests at 0.75-0.79.
  - **Rule:** go where buyers post (comments, groups, job and gig boards), and measure precision and recall on labeled sets before trusting a gate.
- **2026-09-30 (lead-radar PROGRESS.md): V2's classifier is not there yet.**
  - Held-out High precision was 0.686 and seller leakage 29.2%, mostly job ads.
  - **Rule:** data-box's plan marks the intent lane "unverified" until Lead Radar reports a passing golden set.
- **2026-09-30 (decision): called, never contained.**
  - Lead intent was once to move into data-box; Justin put it in its own project with its own API.
  - **Rule:** data-box depends only on the HTTP contract. A test (D9) fails if `data_box` imports `lead_radar`.
