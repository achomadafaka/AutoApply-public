<script>
  import { onMount, onDestroy } from "svelte";
  import {
    cancelApplication,
    cvPreviewUrl,
    getCvWorkspace,
    completeApplication,
    deleteApplication,
    getApplication,
    getApplicationHistory,
    getArtifactFileUrl,
    getJob,
    getProfileAnswers,
    listApplicationArtifacts,
    updateProfileAnswers,
    pauseApplication,
    resumeApplication,
    startApplication
  } from "../../../lib/api";

  export let params;
  let application = null;
  let reviewBaseline = "";
  let approvedBaseline = "";
  let cvWorkspace = null;

  async function loadCvWorkspace() {
    try { cvWorkspace = await getCvWorkspace(); }
    catch { cvWorkspace = null; }
  }
  let job = null;
  let history = [];
  let artifacts = [];
  let error = "";
  let actionError = "";
  let actionSuccess = "";
  let pendingDelete = false;
  let pollHandle = null;
  let isLoading = false;
  let unansweredQuestions = [];
  let unansweredPlatform = "";
  let answerDrafts = {};
  let answerSuggestions = {};
  let savedAnswers = {};
  let saveAnswersError = "";
  let saveAnswersSuccess = "";
  let seenQuestionArtifact = "";
  $: latestEvent = history[history.length - 1]?.event;
  $: reviewOpen = ["fill_review_ready", "fill_review_needs_input", "fill_review_verification",
    "fill_review_submission_pending"].includes(latestEvent);

  function getGreenhouseApplyUrl(url) {
    if (!url) return null;
    const match = url.match(/https?:\/\/boards\.greenhouse\.io\/([^/]+)\/jobs\/(\d+)/i);
    if (!match) return null;
    return `https://boards.greenhouse.io/embed/job_app?for=${match[1]}&token=${match[2]}`;
  }

  async function loadAll() {
    if (isLoading) return;
    isLoading = true;
    try {
      application = await getApplication(params.id);
      if (application?.job_id) {
        job = await getJob(application.job_id);
      } else {
        job = null;
      }
      history = await getApplicationHistory(params.id);
      artifacts = await listApplicationArtifacts(params.id, { type: "screenshot" });
      const unansweredArtifacts = await listApplicationArtifacts(params.id, {
        type: "unanswered_questions",
        limit: 1
      });
      if (unansweredArtifacts.length > 0) {
        const artifact = unansweredArtifacts[0];
        const response = await fetch(getArtifactFileUrl(artifact.id));
        const payload = await response.json();
        unansweredQuestions = payload?.questions ?? [];
        unansweredPlatform = payload?.platform ?? application?.platform ?? "greenhouse";
        if (artifact.id !== seenQuestionArtifact) answerDrafts = {};
        seenQuestionArtifact = artifact.id;
        const [platformProfile, globalProfile] = await Promise.all([
          getProfileAnswers(unansweredPlatform),
          getProfileAnswers()
        ]);
        savedAnswers = platformProfile?.answers ?? {};
        const globalAnswers = flattenProfileAnswers(globalProfile?.answers ?? {});
        answerSuggestions = buildAnswerSuggestions(
          unansweredQuestions,
          { ...globalAnswers, ...savedAnswers }
        );
      } else {
        unansweredQuestions = [];
        unansweredPlatform = application?.platform ?? "greenhouse";
        answerDrafts = {};
        answerSuggestions = {};
        savedAnswers = {};
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load application";
    } finally {
      isLoading = false;
    }
  }

  async function handleAction(action) {
    actionError = "";
    actionSuccess = "";
    try {
      if (action === "start") {
        if (reviewBaseline && approvedBaseline !== reviewBaseline) {
          actionError = "Review and confirm the selected PDF first.";
          return;
        }
        await startApplication(params.id, reviewBaseline || undefined);
      }
      if (action === "complete") await completeApplication(params.id);
      if (action === "pause") await pauseApplication(params.id);
      if (action === "resume") await resumeApplication(params.id);
      if (action === "cancel") await cancelApplication(params.id);
      actionSuccess = `Action '${action}' applied.`;
      await loadAll();
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Action failed";
    }
  }

  function requestDelete() {
    pendingDelete = true;
    actionError = "";
    actionSuccess = "";
  }

  function cancelDelete() {
    pendingDelete = false;
  }

  async function handleDelete() {
    actionError = "";
    actionSuccess = "";
    try {
      await deleteApplication(params.id);
      actionSuccess = "Run deleted.";
      window.location.href = "/applications";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Delete failed";
    }
  }

  async function handleSaveAnswers() {
    saveAnswersError = "";
    saveAnswersSuccess = "";
    const answers = {};
    for (const [label, value] of Object.entries(answerDrafts)) {
      const cleanedLabel = cleanLabelForStorage(label);
      if (value && value.trim()) {
        answers[cleanedLabel] = value.trim();
      }
    }
    if (Object.keys(answers).length === 0) {
      saveAnswersError = "Add at least one answer.";
      return;
    }
    try {
      await updateProfileAnswers({
        platform: unansweredPlatform || "greenhouse",
        answers
      });
      saveAnswersSuccess = "Saved answers for future runs.";
      answerDrafts = {};
      const [platformProfile, globalProfile] = await Promise.all([
        getProfileAnswers(unansweredPlatform || "greenhouse"),
        getProfileAnswers()
      ]);
      savedAnswers = platformProfile?.answers ?? {};
      const globalAnswers = flattenProfileAnswers(globalProfile?.answers ?? {});
      answerSuggestions = buildAnswerSuggestions(
        unansweredQuestions,
        { ...globalAnswers, ...savedAnswers }
      );
    } catch (err) {
      saveAnswersError = err instanceof Error ? err.message : "Unable to save answers";
    }
  }

  function normalizeLabel(value) {
    return (value || "")
      .toLowerCase()
      .replace(/\*/g, "")
      .replace(/[^\w\s]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanLabelForStorage(label) {
    const cleaned = (label || "").split("\n")[0].replace(/\u00a0/g, " ").trim();
    return cleaned || label;
  }

  function similarityScore(a, b) {
    const na = normalizeLabel(a);
    const nb = normalizeLabel(b);
    if (!na || !nb) return 0;
    if (na === nb) return 1;
    const tokensA = new Set(na.split(" "));
    const tokensB = new Set(nb.split(" "));
    const intersection = [...tokensA].filter((t) => tokensB.has(t)).length;
    const union = new Set([...tokensA, ...tokensB]).size;
    let score = union ? intersection / union : 0;
    if (na.includes(nb) || nb.includes(na)) score += 0.2;
    return Math.min(score, 1);
  }

  function buildAnswerSuggestions(questions, answers) {
    const suggestions = {};
    const answerKeys = Object.keys(answers || {});
    for (const q of questions || []) {
      let best = null;
      let bestScore = 0;
      for (const key of answerKeys) {
        const score = similarityScore(q.label, key);
        if (score > bestScore) {
          bestScore = score;
          best = key;
        }
      }
      if (best && bestScore >= 0.45) {
        suggestions[q.label] = { key: best, value: answers[best], score: bestScore };
      }
    }
    return suggestions;
  }

  function flattenProfileAnswers(payload) {
    if (!payload || typeof payload !== "object") return {};
    const flattened = {};
    for (const [key, value] of Object.entries(payload)) {
      if (value && typeof value === "string") {
        flattened[key] = value;
        continue;
      }
      if (value && typeof value === "object" && !Array.isArray(value)) {
        for (const [innerKey, innerVal] of Object.entries(value)) {
          if (typeof innerVal === "string") {
            flattened[innerKey] = innerVal;
          }
        }
      }
    }
    return flattened;
  }

  function startPolling() {
    if (pollHandle) return;
    pollHandle = setInterval(async () => {
      if (application?.mode !== "fill_review" && artifacts.length > 0) {
        clearInterval(pollHandle);
        pollHandle = null;
        return;
      }
      await loadAll();
      if (application?.mode !== "fill_review" && artifacts.length > 0) {
        clearInterval(pollHandle);
        pollHandle = null;
      }
    }, 5000);
  }

  onMount(() => {
    loadCvWorkspace();
    loadAll();
    startPolling();
  });

  onDestroy(() => {
    if (pollHandle) clearInterval(pollHandle);
  });
</script>

<svelte:head>
  <title>Application {params?.id} · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>Application detail</h1>
    <p>State, platform, and history for this run.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/applications">Back to applications</a>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}
  {#if actionError}
    <p class="muted" style="margin-top: 12px;">{actionError}</p>
  {/if}
  {#if actionSuccess}
    <p class="muted" style="margin-top: 12px;">{actionSuccess}</p>
  {/if}

  {#if application}
    <section class="card fade-in delay-1" style="margin-top: 24px;">
      <h3>Summary</h3>
      <div class="list">
        <li>
          <span>ID</span>
          <strong>{application.id}</strong>
        </li>
        <li>
          <span>Job</span>
          <strong>{application.job_id}</strong>
        </li>
        <li>
          <span>Platform</span>
          <strong>{application.platform}</strong>
        </li>
        <li>
          <span>Mode</span>
          <strong>{application.mode}</strong>
        </li>
        <li>
          <span>State</span>
          <strong>{application.state}</strong>
        </li>
        <li>
          <span>Last error</span>
          <strong>{application.last_error ?? "—"}</strong>
        </li>
      </div>
      {#if application.mode === "fill_review"}
        {#if cvWorkspace?.baselines.length && !reviewOpen && ["pending", "awaiting_review"].includes(application.state)}
          <label>
            Résumé to review for manual upload
            <select bind:value={reviewBaseline} on:change={() => { approvedBaseline = ""; }}>
              <option value="">No workspace PDF selected</option>
              {#each cvWorkspace.baselines as cv (cv.id)}
                <option value={cv.id}>{cv.label}</option>
              {/each}
            </select>
          </label>
          {#if reviewBaseline}
            <a href={cvPreviewUrl(reviewBaseline)} target="_blank" rel="noreferrer">Review selected PDF</a>
            <label>
              <input type="checkbox" checked={approvedBaseline === reviewBaseline}
                on:change={(event) => { approvedBaseline = event.currentTarget.checked ? reviewBaseline : ""; }} />
              I reviewed this PDF and will attach it myself on the employer’s form.
            </label>
          {/if}
        {/if}
        <p class="muted">Fill &amp; Review enters recognized contact fields only. Attach your documents, answer employer questions, and submit in the employer’s browser yourself.</p>
        {#if latestEvent === "fill_review_confirmed"}
          <p>Submitted. The employer showed a receipt for this job.</p>
        {:else if latestEvent === "fill_review_pending_closed"}
          <p>Submission not confirmed. Check your email or the employer before applying again.</p>
        {:else if latestEvent === "fill_review_verification"}
          <p>The employer needs verification. Complete it in the open browser. Not submitted yet.</p>
        {:else if latestEvent === "fill_review_submission_pending"}
          <p>Submission attempted. Waiting for the employer’s receipt. Do not submit again.</p>
        {:else if reviewOpen}
          <p>The review browser is open. Check all fields and complete the remaining steps by hand.</p>
        {:else if application.state === "filling_form"}
          <p>Opening and filling the form…</p>
        {/if}
      {/if}
      <div class="hero-actions" style="margin-top: 12px;">
        {#if application.mode === "fill_review"}
          <button class="btn primary" on:click={() => handleAction("start")}
            disabled={reviewOpen || !["pending", "awaiting_review"].includes(application.state) || (reviewBaseline && approvedBaseline !== reviewBaseline)}>
            {application.state === "pending" ? "Fill & Review" : "Reopen and refill"}
          </button>
        {:else}
          <button class="btn" on:click={() => handleAction("start")}>Start</button>
          <button class="btn" on:click={() => handleAction("pause")}>Pause</button>
          <button class="btn" on:click={() => handleAction("resume")}>Resume</button>
        {/if}
        {#if application.mode !== "fill_review" || !["submitting", "completed", "failed"].includes(application.state)}
          <button class="btn" on:click={() => handleAction("cancel")}>Cancel</button>
        {/if}
        {#if application && application.mode !== "fill_review" && application.state !== "completed" && application.state !== "failed"}
          <button class="btn" on:click={() => handleAction("complete")}>Mark completed</button>
        {/if}
        {#if pendingDelete}
          <button class="btn ghost" on:click={handleDelete}>Confirm delete</button>
          <button class="btn" on:click={cancelDelete}>Cancel</button>
        {:else}
          <button class="btn ghost" on:click={requestDelete}>Delete</button>
        {/if}
        {#if job?.url}
          <a class="btn" href={job.url} target="_blank" rel="noreferrer">Open job listing</a>
          {#if getGreenhouseApplyUrl(job.url)}
            <a class="btn" href={getGreenhouseApplyUrl(job.url)} target="_blank" rel="noreferrer">
              Open application form
            </a>
          {/if}
        {/if}
      </div>
    </section>
  {/if}

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Latest screenshot</h3>
    <p class="muted">Captured during the last automation run (if available).</p>
    <div class="hero-actions" style="margin-top: 12px;">
      <button class="btn" on:click={loadAll}>Refresh</button>
      {#if artifacts.length === 0}
        <span class="muted">Waiting for screenshot…</span>
      {/if}
    </div>
    {#if artifacts.length === 0}
      <p class="muted">No screenshots yet.</p>
    {:else}
      <img
        class="artifact-image"
        src={getArtifactFileUrl(artifacts[0].id)}
        alt="Automation screenshot"
      />
      <div class="hero-actions" style="margin-top: 12px;">
        <a class="btn" href={getArtifactFileUrl(artifacts[0].id)} target="_blank">Open</a>
      </div>
    {/if}
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Unanswered questions</h3>
    <p class="muted">Fill &amp; Review never applies saved screening answers to an employer’s form.</p>
    {#if unansweredQuestions.length === 0}
      <p class="muted">{application?.mode === "fill_review" && !reviewOpen
        ? "No field report available for this run yet."
        : "No additional fields detected. Check the employer’s form yourself."}</p>
    {:else}
      <div class="form-grid" style="margin-top: 12px;">
        {#each unansweredQuestions as q, index (index)}
          <label>
            {q.label}
            {#if q.required}
              <span class="tag" style="margin-left: 8px;">required</span>
            {/if}
            {#if q.options && q.options.length > 0}
              <div class="muted" style="margin: 6px 0 4px;">
                Options: {q.options.join(", ")}
              </div>
            {/if}
            {#if !q.manual && answerSuggestions[q.label]}
              <div class="muted" style="margin: 6px 0 4px;">
                Suggested: {answerSuggestions[q.label].value}
                <button
                  class="btn ghost"
                  style="margin-left: 8px;"
                  on:click={() => (answerDrafts[q.label] = answerSuggestions[q.label].value)}
                >
                  Use
                </button>
              </div>
            {/if}
            {#if !q.manual}<input
              bind:value={answerDrafts[q.label]}
              placeholder="Your answer"
            />{/if}
          </label>
        {/each}
      </div>
      {#if unansweredQuestions.some(q => !q.manual)}
        <div class="hero-actions" style="margin-top: 12px;">
          <button class="btn" on:click={handleSaveAnswers}>Save answers</button>
        </div>
      {/if}
      {#if saveAnswersError}
        <p class="muted" style="margin-top: 12px;">{saveAnswersError}</p>
      {/if}
      {#if saveAnswersSuccess}
        <p class="muted" style="margin-top: 12px;">{saveAnswersSuccess}</p>
      {/if}
    {/if}
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>History</h3>
    <p class="muted">All recorded state transitions.</p>
    <ul class="list">
      {#if history.length === 0}
        <li>
          <span>No history yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each history as entry (entry.id)}
          <li>
            <div>
              <strong>{entry.event}</strong>
              <div class="muted">{entry.state} · {entry.actor}</div>
            </div>
            <span class="tag">{new Date(entry.created_at).toLocaleString()}</span>
          </li>
        {/each}
      {/if}
    </ul>
  </section>
</main>
