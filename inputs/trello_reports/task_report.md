# Trello Board Analysis - Exploratory Task

## Objective

Analyze a Trello board JSON export to explore and answer key questions about team workflow, workload distribution, and process health. Generate metrics and visualizations that provide insight into how work flows through the board and where improvements could be made.

## Input

Trello board exported as two files: a JSON export (full board — cards, lists, members, labels, checklists, custom field definitions, and activity history) and a CSV export (a flat card table, non-archived cards only, with the custom-field values as columns). Of particular interest are the custom fields `Lab`, `Lead` and `Source` plus the free-text `Lab Name` — note the list-type values (`Lab`, `Lead`, `Source`) are populated in the CSV export but come through as null in the JSON export, so analyses of them must read the CSV and join to the JSON on Card ID.

## Guiding Questions for Analysis

Your analysis should help answer these exploratory questions:

1. **Workflow Bottlenecks**: Where do cards get stuck? Which lists do cards spend the most time in? Are there significant delays between creation and completion? Do cards from certain labs go stale more often than others? On Hold and Ongoing are now known to be ~95% dormant (no activity in 30+ days) — what distinguishes a dormant card that's genuinely blocked on someone else from one that's simply been neglected?

2. **Team Workload Distribution**: How is work distributed across team members? Are some members overloaded while others have capacity? Which members handle which types of work?

3. **Velocity & Timing Patterns**: How long does it typically take for cards to move through the workflow? Is the process getting faster or slower? Are there patterns in how often cards are updated? A first-cut keyword pass over card text suggests requests naming established tools (QuPath, OMERO) resolve roughly 10x faster than ones naming more specialised tools (Ilastik, deep-learning segmentation, Imaris) or spatial/multiplex imaging work, which rarely reach a terminal state at all — a materially better (not keyword-based) categorisation of card text by technology and scientific domain, checked against completion speed and stuck-rate, would confirm or refute this properly.

4. **Process Health**: How many cards are in progress vs. completed? Are there inactive cards that should be archived? How is the board being used—is activity even or bursty?

5. **Client Relationship Management**: Do specific labs or users have a preference for specific team members? Do people in the same lab open projects with multiple team members?

6. **Lab workload distribution**: Which labs do the team spend most time working with? How has this evolved over time? Are projects with certain labs more productive than others? Only 7.3% of completed (Done) cards ever reach Billed — does that gap concentrate in specific labs, sources, or time periods, or does it mostly reflect a large share of legitimately non-billable work (Training/Wishlist/internal)?

7. **Think outside the box**: What would surprise the team leadership? What would a funder not already know?

## Analysis Requirements

### 1. Suggest Key metrics
Analyse the Trello board JSON export and suggest **5-7 key metrics** that help answer the guiding questions above. Choose metrics that are:
- Computable from the available data
- Relevant to at least one of the guiding questions
- More insightful than just raw counts
- Pay particular attention here to the custom fields and labels used in the Trello board – any insights derived from these are of particular interest.
- Consider other metrics that might typically be included in an analysis of Trello board activity, or project management in general.

### Already Explored — Do Not Repeat

The analyses below have already been done on this data (Run 37, `outputs/gallery_20260819_173843.md`, plus a direct
follow-up computed against the real export in `explorations/trello/group_management_review.py`). Proposed metrics
must be materially different in kind - not a refinement, re-implementation, or alternative-library version of
anything here.

**Workload**
- Per-member assignment counts vs. actual board-activity (action) counts, summarised as Gini/HHI concentration plus
  a per-member divergence (action share − assignment share) — established that workload is heavily concentrated on
  2-3 members, and that the concentration is materially different (and higher) when measured by realised activity
  than by nominal assignment.

**Workflow health**
- Backward/rework transitions through the list sequence (e.g. Done → To Do) as a bottleneck signal — tested
  directly and disconfirmed: only 1 of 42 tracked cards ever moved backward, and it was not stale. Do not
  re-propose "rework loops" as a bottleneck angle without a specific reason the capped 1000-action window would
  newly reveal it.
- Per-list staleness (share of cards with no activity in 30+ days) — established directly: On Hold (95.6% stale,
  68 cards - the single largest list on the board) and Ongoing (95.2% stale) are overwhelmingly dormant; Done is
  also mostly stale (92.1%) but that's expected for a terminal state, not a finding on its own.
- Terminal-state conversion (Done → Billed) — established directly: only 3 of 41 terminal cards (7.3%) ever reach
  Billed.

In short: raw workload-concentration metrics, backward-transition/rework counts, per-list staleness counts, and
the overall Done-vs-Billed conversion rate are exhausted. What's NOT yet known, and is the more valuable next
step: WHY the billing gap exists (concentrated in specific labs/sources/time periods, or mostly a reflection of
genuinely non-billable work?), and WHY On Hold/Ongoing cards go dormant (blocked on an external party vs. simply
neglected) — a card-level or time-series angle that gets at causes, not a re-measurement of the three numbers
above, is what's actually needed now.

**Technology & scientific domain (heuristic pass only — confirm/refute properly, don't just repeat the same
shallow approach)**

Neither "technology used" nor "scientific domain/model system" is a Trello field — the ~10 labels describe
engagement type (Training, Development, User Support...), not the science or tool involved. A hand-written
keyword pass over `Card Name`/`Card Description` (`explorations/trello/domain_technology_review.py`) found a
striking split worth taking seriously but NOT worth treating as settled:

- **Technology**: QuPath (24 cards, median 10 days to Done/Billed) and OMERO (15 cards, 12 days) resolve far
  faster than Ilastik (11 cards, 126 days), DL segmentation tools like Cellpose/StarDist (10 cards, 126.5 days),
  or Imaris (5 cards, 136 days). Napari (4 cards) and Visiopharm (2 cards) have never reached a terminal state.
- **Domain**: Spatial/multiplex imaging work (17 cards) stands out - only 1 has ever reached Done/Billed, taking
  187 days, versus e.g. tissue histology (20 cards, 12 days median).
- **Why this is only a lead, not a finding**: the keyword lists only matched 43.5% of cards for technology and
  30.6% for domain - most of the board is uncategorised by this pass - and several of the categories above have
  single-digit n (Napari, Visiopharm, Organoid, Vasculature), so their 0%/100% figures are anecdotes. A proper
  angle should categorise card text by technology and domain in a materially better way (not this same keyword
  list) and check whether the fast-vs-stuck split survives - if it does, the natural follow-up is WHY (genuine
  task difficulty vs. a capacity/expertise bottleneck on the newer/less common tools, which would also connect
  to the workload-concentration finding above).

### 2. Create Visualizations (PNG files)
Create **at least five visualizations** that illustrate the metrics chosen in section 1. Pick visualizations that help answer the guiding questions:

### 3. Identify Data Gaps

After analysis, print **2-3 specific suggestions** for additional data/fields that would improve future analysis:
- Focus on what data would help answer the guiding questions more clearly
- Examples: due date compliance, priority levels, effort estimates, blockers/dependencies, sprint assignments, etc.
- Format: Bulleted list with a brief explanation of why each would be useful

## Output Requirements

The script must:
- Load and parse the Trello JSON export (auto-detect filename in the data directory)
- Compute metrics suggested in section 1
- Print metrics to console in a readable tabular format
- Generate the visualizations suggested in section 2
- Print data gap analysis suggestions to console
- Save visualizations to the current working directory with specified filenames
- Handle missing or empty data gracefully (e.g., members with no cards, lists with no due dates)

## Success Criteria

✅ Script runs without errors on the provided Trello JSON export  
✅ At least five metrics are computed and printed  
✅ At least five PNG visualization files are created and saved  
✅ Visualisations are properly labeled (titles, axis labels, legends)   
✅ Code is clean and minimal (no unnecessary utilities or visualizations)  
✅ One-line docstrings for all functions  
