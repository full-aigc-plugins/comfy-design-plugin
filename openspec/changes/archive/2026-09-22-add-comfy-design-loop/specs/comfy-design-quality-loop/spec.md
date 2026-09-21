## ADDED Requirements

### Requirement: Loop rounds SHALL be new authorized intents

Each loop round SHALL be a new generation intent carrying the previous round's review feedback, and every billed action in a round SHALL be covered by per-round user confirmation or a recorded loop budget. A failed, timed-out, or unknown job SHALL never be resubmitted as a loop round.

#### Scenario: A job fails during a round

- **WHEN** a submitted job ends in failure, timeout, or unknown state
- **THEN** the loop SHALL NOT resubmit it, SHALL exit the round, and SHALL report per the one-submit rule instead of starting a retry round

#### Scenario: A round is attempted without authorization

- **WHEN** no per-round confirmation exists and no budget is recorded in the ledger
- **THEN** the loop SHALL NOT issue any `run_template`, `submit_workflow`, or `partner_generate` call

### Requirement: A target image SHALL exist before the loop starts

The loop SHALL NOT begin without a target image, which is either supplied by the user or generated once under authorization as a realistic reachable result rather than concept art. When a previous artifact exists, the target SHALL be derived from it as a refinement.

#### Scenario: No target and no authorized way to generate one

- **WHEN** the user supplies no target image and has not authorized a generation for it
- **THEN** the loop SHALL stop and ask the user to provide the target or authorize its generation

#### Scenario: A previous artifact exists

- **WHEN** the user asks to improve an existing generation result
- **THEN** the target SHALL be generated from that result as baseline input, and SHALL NOT diverge from it

### Requirement: Judgement SHALL be independent and rubric-based

Review of each round SHALL be performed by a fresh-context judge that receives only the target image, the round's locally verified artifact, and prior verdicts — never the round's prompt draft or conversation context. Scores SHALL follow the image rubric (composition 0-3, lighting 0-3, materials 0-3, details 0-1) or the video rubric (image axes plus motion quality 0-3 and temporal consistency 0-3), allow fractional scores, and every named gap SHALL state the concrete difference and how to fix it. A regression SHALL receive a lower score than the prior round.

#### Scenario: The author judges their own round

- **WHEN** the agent that authored the round's workflow would score its own output without a fresh judge
- **THEN** the round SHALL NOT proceed to the next iteration on that self-assessment

#### Scenario: The result regressed against the previous round

- **WHEN** the current artifact is worse than the previous round's artifact on a named gap
- **THEN** the judge SHALL assign a lower total score than the previous round's verdict

### Requirement: The loop SHALL stop on defined exit conditions

The loop SHALL stop when the rubric threshold is met, when progress stalls, or when the recorded budget is exhausted. After two rounds without improvement or two consecutive rounds naming the same gap, the loop SHALL make an architectural-level change (different template, model tier, or workflow topology) rather than incremental tweaks, and if that fails to improve the score it SHALL stop and ask the user.

#### Scenario: The threshold is reached

- **WHEN** the judge's total score reaches the rubric threshold
- **THEN** the loop SHALL deliver the latest verified artifact and stop without further billed rounds

#### Scenario: The budget is exhausted below the threshold

- **WHEN** the recorded budget can no longer cover another round
- **THEN** the loop SHALL stop, deliver the best verified artifact so far, and attach the outstanding gap list

### Requirement: Loop state SHALL be recorded in a ledger

The loop SHALL persist its target image, per-round workflow, artifacts, verdicts, scores, gap history, round count, and budget authorization under `.comfy-loop/`, which SHALL be excluded from version control. Stall detection SHALL be derived from the ledger, not from conversation memory.

#### Scenario: Stall is detected across context loss

- **WHEN** a new session resumes a loop with an existing ledger
- **THEN** the stall and exit conditions SHALL be evaluated from the recorded round history alone

### Requirement: Artifacts SHALL be locally verified before judging

Each round's artifact SHALL be retrieved via the job output, downloaded by executing the returned signed download command verbatim, and verified locally before being submitted to the judge. The target image SHALL enter the generation workflow through the file upload flow rather than absolute local paths.

#### Scenario: A signed download URL is returned

- **WHEN** the job output provides a signed download command
- **THEN** the loop SHALL execute it unmodified, verify the saved file locally, and pass that file to the judge
