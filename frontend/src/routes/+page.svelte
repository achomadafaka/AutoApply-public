<script>
  import { onMount } from "svelte";
  import {
    cancelApplication,
    getAIHealth,
    getHealth,
    getRecentHistory,
    getApplicationStats,
    listApplications,
    listJobs,
    getSettings,
    pauseApplication,
    resumeApplication,
    startApplication
  } from "../lib/api";

  let healthStatus = "checking...";
  let aiHealth = { status: "checking...", models: [] };
  let jobs = [];
  let applications = [];
  let recentEvents = [];
  let settings = { daily_limit: 25 };
  let pipelineStats = { pending_review: 0, in_progress: 0, completed: 0, failed: 0, total: 0 };
  let error = "";
  let appActionError = "";

  onMount(async () => {
    const results = await Promise.allSettled([
      getHealth(),
      listJobs(5),
      getSettings(),
      getAIHealth(),
      listApplications({ limit: 5 }),
      getRecentHistory(8),
      getApplicationStats()
    ]);
    const [
      healthRes,
      jobsRes,
      settingsRes,
      aiRes,
      appsRes,
      historyRes,
      statsRes
    ] = results;

    if (healthRes.status === "fulfilled") {
      healthStatus = healthRes.value.status;
    } else {
      healthStatus = "offline";
      error =
        healthRes.reason instanceof Error
          ? healthRes.reason.message
          : "Unable to reach API";
    }

    if (jobsRes.status === "fulfilled") jobs = jobsRes.value;
    if (settingsRes.status === "fulfilled") settings = settingsRes.value;
    if (aiRes.status === "fulfilled") {
      aiHealth = aiRes.value;
    } else {
      aiHealth = { status: "offline", models: [] };
    }
    if (appsRes.status === "fulfilled") applications = appsRes.value;
    if (historyRes.status === "fulfilled") recentEvents = historyRes.value;
    if (statsRes.status === "fulfilled") pipelineStats = statsRes.value;
  });

  function canAct(state) {
    return !["completed", "failed"].includes(state);
  }

  function canStart(state) {
    return state === "pending";
  }

  async function handleAppAction(id, action) {
    appActionError = "";
    try {
      if (action === "start") await startApplication(id);
      if (action === "pause") await pauseApplication(id);
      if (action === "resume") await resumeApplication(id);
      if (action === "cancel") await cancelApplication(id);
      applications = await listApplications({ limit: 5 });
    } catch (err) {
      appActionError = err instanceof Error ? err.message : "Action failed";
    }
  }

</script>

<svelte:head>
  <title>AutoApply Control Room</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>AutoApply Control Room</h1>
    <p>
      Save jobs, prepare application materials and track what you sent.
      Fill &amp; Review leaves the final submission to you.
    </p>
    <div class="hero-actions">
      <a class="btn primary" href="/jobs">New Job</a>
      <a class="btn" href="/applications">View Applications</a>
      <a class="btn" href="/selectors">Selector Registry</a>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}
  {#if appActionError}
    <p class="muted" style="margin-top: 12px;">{appActionError}</p>
  {/if}
  <section class="grid">
    <div class="card fade-in delay-1">
      <h3>API Status</h3>
      <p class="muted">Health check and runtime availability.</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px;">
        <span class="tag">{healthStatus}</span>
        <span class="muted">localhost</span>
      </div>
    </div>

    <div class="card fade-in delay-2">
      <h3>AI Status</h3>
      <p class="muted">Ollama connectivity and available models.</p>
      <div style="display:flex;align-items:center;gap:10px;margin-top:12px;">
        <span class="tag">{aiHealth.status}</span>
        <span class="muted">{aiHealth.models?.length ?? 0} models</span>
      </div>
    </div>

    <div class="card fade-in delay-2">
      <h3>Safety Limits</h3>
      <p class="muted">You review and submit each application yourself.</p>
      <ul class="list"><li><span>Daily start limit</span><strong>{settings.daily_limit}</strong></li></ul>
    </div>

    <div class="card fade-in delay-3">
      <h3>Pipeline Snapshot</h3>
      <p class="muted">Track progress across the application flow.</p>
      <div class="list">
        <li>
          <span>Pending review</span>
          <strong>{pipelineStats.pending_review}</strong>
        </li>
        <li>
          <span>In progress</span>
          <strong>{pipelineStats.in_progress}</strong>
        </li>
        <li>
          <span>Completed</span>
          <strong>{pipelineStats.completed}</strong>
        </li>
      </div>
    </div>
  </section>

  <h2 class="section-title">Recent Jobs</h2>
  <section class="card fade-in delay-1">
    <p class="muted">
      Jobs are pulled from the local database. Add a new job to populate the list.
    </p>
    <ul class="list">
      {#if jobs.length === 0}
        <li>
          <span>No jobs yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each jobs as job (job.id)}
          <li>
            <div>
              <strong>{job.title}</strong>
              <div class="muted">{job.company}</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{job.status}</span>
              <a class="btn" href={`/jobs/${job.id}`}>Details</a>
            </div>
          </li>
        {/each}
      {/if}
    </ul>
  </section>

  <h2 class="section-title">Recent Runs</h2>
  <section class="card fade-in delay-1">
    <p class="muted">Quick controls for the latest application runs.</p>
    <ul class="list">
      {#if applications.length === 0}
        <li>
          <span>No runs yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each applications as app (app.id)}
          <li>
            <div>
              <strong>{app.platform}</strong>
              <div class="muted">{app.job_id}</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{app.state}</span>
              {#if canStart(app.state)}
                <button class="btn" on:click={() => handleAppAction(app.id, "start")}>
                  Start
                </button>
              {/if}
              {#if canAct(app.state)}
                <button class="btn" on:click={() => handleAppAction(app.id, "pause")}>
                  Pause
                </button>
                <button class="btn" on:click={() => handleAppAction(app.id, "resume")}>
                  Resume
                </button>
                <button class="btn" on:click={() => handleAppAction(app.id, "cancel")}>
                  Cancel
                </button>
              {/if}
              <a class="btn" href={`/applications/${app.id}`}>Details</a>
            </div>
          </li>
        {/each}
      {/if}
    </ul>
  </section>

  <h2 class="section-title">Activity Log</h2>
  <section class="card fade-in delay-1">
    <p class="muted">Latest state transitions across all runs.</p>
    <ul class="list">
      {#if recentEvents.length === 0}
        <li>
          <span>No activity yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each recentEvents as evt (evt.id)}
          <li>
            <div>
              <strong>{evt.event}</strong>
              <div class="muted">{evt.state} · {evt.actor}</div>
            </div>
            <span class="tag">{new Date(evt.created_at).toLocaleString()}</span>
          </li>
        {/each}
      {/if}
    </ul>
  </section>

  <h2 class="section-title">Next Actions</h2>
  <section class="grid">
    <div class="card fade-in delay-2">
      <h3>Analyze a job</h3>
      <p class="muted">Run keyword extraction and skill mapping.</p>
      <button class="btn">Run analysis</button>
    </div>
    <div class="card fade-in delay-3">
      <h3>Generate materials</h3>
      <p class="muted">Create ATS-friendly resume and cover letter drafts.</p>
      <button class="btn">Generate</button>
    </div>
  </section>
</main>
