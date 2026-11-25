# User Stories

## Story 1: Add a job listing
As a user, I can add a job listing so I can track it in one place.

Acceptance criteria:
- I can create a job with title, company, and URL.
- The job is stored with a default status of "new".
- I can edit or archive the job later.

## Story 2: Analyze a job description
As a user, I can analyze a job description so I can tailor my materials.

Acceptance criteria:
- I can run analysis for a selected job.
- The system extracts keywords and required skills.
- The results are stored with the job record.

## Story 3: Generate ATS-friendly materials
As a user, I can generate a resume and cover letter targeted to a job.

Acceptance criteria:
- Materials are tied to a specific resume version and job.
- Output is stored for later review.
- I can rate the output quality.

## Story 4: Review before submit
As a user, I can review all generated materials before any submission.

Acceptance criteria:
- Fill & Review prefills only recognized contact fields.
- I attach my own documents, answer screening and consent questions, and click Submit myself.
- A matching employer receipt confirms submission.

## Story 5: Start an application run
As a user, I can start an application run to fill a form with my data.

Acceptance criteria:
- The system opens the browser in headed mode.
- The run advances through the state machine.
- Each state transition is recorded.

## Story 6: Pause and resume a run
As a user, I can pause or resume a run when I need to intervene.

Acceptance criteria:
- I can pause the run from the UI.
- The system resumes from the last checkpoint.
- The audit trail shows pause and resume events.

## Story 7: Track outcomes
As a user, I can mark outcomes so I can measure results.

Acceptance criteria:
- I can set an outcome (submitted, rejected, interview, offer).
- The timestamp is stored with the outcome.
- I can view all outcomes in a list.

## Story 8: Enforce safety limits
As a user, I can rely on the system to enforce safe limits.

Acceptance criteria:
- The system caps daily applications to a configurable limit.
- Jittered delays are applied between actions.
- A per-site circuit breaker pauses runs after repeated failures.
