# Pokémon TCG AI Battle Challenge — Playground Plan

Reviewed: October 28, 2026 (Asia/Seoul).

## Goal and scope

Build a reliable Pokémon TCG playing agent, measure its strength locally, and prepare a reproducible submission for the linked Playground competition. Keep an experiment record that can also support a strategy report later.

The repository name contains `strategy`, but the requested competition is **Playground**. The plan follows that URL; a Strategy-track entry would need its own requirements review.

## Verified context and open requirements

The [Playground competition](https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground) asks participants to build a Pokémon Trading Card Game AI Training Agent. The public page identifies it as a Playground Simulation Competition, lists swag, and says it does not award points or medals. The displayed close is **January 9, 2027 at 08:59:59 KST** (January 8 at 23:59:59 UTC). Recheck the live timeline before submission.

The public Overview had no detailed task description beyond that summary. The [Data](https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/data) and [Rules](https://www.kaggle.com/competitions/the-pokemon-company-ptcg-ai-battle-challenge-playground/rules) tabs exposed no detailed content in the unauthenticated browser session. These requirements remain unverified:

- Submission entry point, archive layout, required files, and deck format.
- Exact engine version, supported Python/platform, dependencies, and available card pool.
- Action time, initialization time, memory, CPU, and archive-size limits.
- Evaluation metric, matchmaking, draw handling, active-agent policy, and submission quota.
- Entry/team deadlines, permitted data and pretrained models, and redistribution conditions.

Do not copy deadlines, resource limits, or packaging rules from the earlier Simulation or Strategy competitions into this project as Playground facts.

The official [cabt engine documentation](https://matsuoinstitute.github.io/cabt/) provides a provisional technical starting point: observations contain logs, current state, and selection options; initial state/selection can be absent; actions select option indices. Opponent hands are hidden. Its example uses `agent(obs_dict) -> list[int]`, a 60-card deck of card IDs, and `make("cabt")`. Confirm these interfaces against the Playground starter before implementation. The [Kaggle environments repository](https://github.com/Kaggle/kaggle-environments) is the upstream reference for environment setup and execution.

## Approach

Start with one validated deck and a dependable heuristic policy. Establish evaluation before introducing expensive search or training. Treat deck quality and playing policy as separate experimental variables. Add complexity only when it improves held-out match results within the confirmed runtime budget.

## Milestones and acceptance criteria

### 1. Establish the competition contract

- Review the full Playground materials using an authorized Kaggle session; the account owner handles any required rule acceptance.
- Record exact requirements and source links in `docs/competition.md`, with retrieval date.
- Obtain the official starter, engine, and card data; keep downloads outside version control.
- Pin the working Python and engine versions and record platform compatibility. If the engine does not run on macOS, use its supported Linux environment.
- Reproduce the official starter battle and inspect a replay.

**Done when:** the requirements checklist is resolved and one complete official example runs locally with a reproducible setup command.

### 2. Build a reliable baseline

- Define a thin adapter between engine observations and policy code.
- Implement a seeded legal-choice baseline, then a deck-specific heuristic policy.
- Respect selection cardinality, option bounds, mandatory choices, optional choices, and setup phases. Add a valid fallback and diagnostic error reporting.
- Prioritize immediate wins and knockouts, setup consistency, energy allocation, evolution, draw/search sequencing, retreat decisions, and preservation of resources needed on later turns.
- Validate deck legality through the actual competition tooling.
- Test representative observation fixtures, multi-choice decisions, setup, and complete games.

**Done when:** 100 local baseline games complete without invalid responses, agent exceptions, or timeouts. This is a reliability gate, not evidence of competitive strength.

### 3. Create the evaluation harness

- Run candidate-versus-baseline matches across multiple seeds and both player positions. Use matched seeds where the engine supports reproducible randomness; verify that support first.
- Maintain a development opponent pool and a separate held-out pool covering several deck styles.
- Record wins/draws/losses, games per matchup, confidence intervals, decision latency, peak memory, failures, and replay paths.
- Save the code revision, deck/configuration hashes, dependency versions, seeds, and opponent versions for every run.
- Inspect losses for setup failures, sequencing errors, missed knockouts, prize planning, and resource exhaustion.

**Done when:** one command produces a reproducible matchup report and links failures to replays. Start comparisons at 200 paired matches and expand when uncertainty makes the decision unclear; do not promote based only on a noisy aggregate win rate.

### 4. Improve policy and deck choices

- Fix the most frequent costly errors identified in replays before broad parameter tuning.
- Compare heuristic weights and deck variants independently, then test their interaction.
- Explore bounded search only after confirming simulator access, hidden-information behavior, and runtime costs. Never supply private engine state unavailable to the submitted agent.
- Consider imitation learning or self-play only if evaluation shows a clear gap that heuristics cannot resolve and compute/data budgets justify training.
- Require ablations for each substantial addition and report matchup regressions alongside overall gains.

**Done when:** a candidate improves against the frozen evaluation suite with uncertainty reported, passes reliability checks, and fits the verified deployment limits with headroom.

### 5. Package and validate

- Implement packaging only after verifying the current Playground contract.
- Build from an explicit file allowlist; exclude credentials, downloaded data, caches, and evaluation logs.
- Extract the archive in a clean environment and run through the actual submission entry point with networking disabled if that matches Kaggle execution.
- Record artifact checksum, source revision, deck, environment, and local evaluation report.
- Validate a first Kaggle submission once submission is authorized; compare its behavior with local results before further tuning.

**Done when:** the extracted artifact passes local contract checks and an authorized Kaggle submission completes successfully.

## Proposed repository layout

```text
PLAN.md
README.md                # Setup and run commands, once verified
pyproject.toml           # Dependencies and tooling, once selected
src/ptcg_agent/          # Adapter, baseline, heuristics, optional search
configs/                 # Tracked experiment configurations
decks/                   # Small, permitted deck lists
scripts/                 # Evaluation and packaging commands
tests/                   # Contract fixtures and regression cases
docs/                    # Requirements, findings, experiment summaries
notebooks/               # Small analysis notebooks; clear large outputs
data/                    # Local downloads and derived datasets (ignored)
runs/                    # Local metrics and replays (ignored)
models/                  # Local weights (ignored)
submissions/             # Generated bundles (ignored)
```

Track source, configuration, dependency lockfiles, permitted deck lists, and concise result summaries. Keep raw competition assets and generated artifacts local. Directory layout is proposed; no implementation or dependencies have been created yet.

## Suggested schedule

- Week 1: resolve requirements, reproduce the starter, complete the reliable baseline.
- Week 2: build evaluation, diagnose losses, and establish the first benchmark report.
- Weeks 3–4: improve heuristics and compare deck variants.
- Later iterations: evaluate search or learning only if supported by results.
- Before the verified deadline: freeze a stable candidate early, validate packaging, and reserve time for submission failures.

## Immediate next actions

1. Resolve the Playground requirements and obtain its official starter materials.
2. Pin the supported environment and reproduce a complete battle.
3. Implement the legal baseline and evaluation harness before optimization.
