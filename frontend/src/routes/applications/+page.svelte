<script>
  import { onMount } from "svelte";
  import {
    cancelApplication,
    createApplication,
    deleteApplication,
    listApplications,
    listJobs,
    pauseApplication,
    resumeApplication,
    startApplication
  } from "../../lib/api";

  let applications = [];
  let jobs = [];
  let error = "";
  let createError = "";
  let createSuccess = "";
  let bulkError = "";
  let deleteSuccess = "";
  let pendingDeleteId = "";
  let selectedIds = new Set();
  let stateFilter = "";
  let platformFilter = "";
  let jobId = "";
  let platform = "greenhouse";
  let mode = "assisted";

  async function loadApplications() {
    try {
      applications = await listApplications({
        limit: 25,
        state: stateFilter || undefined,
        platform: platformFilter || undefined
      });
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load applications";
    }
  }

  async function loadJobs() {
    try {
      jobs = await listJobs(50);
      if (jobs.length > 0 && !jobId) {
        jobId = jobs[0].id;
      }
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load jobs";
    }
  }

  async function handleCreate() {
    createError = "";
    createSuccess = "";
    if (!jobId) {
      createError = "Select a job before starting a run.";
      return;
    }
    try {
      await createApplication({ job_id: jobId, platform, mode });
      createSuccess = "Application run created.";
      await loadApplications();
    } catch (err) {
      createError = err instanceof Error ? err.message : "Unable to create run";
    }
  }

  function toggleSelect(appId) {
    if (selectedIds.has(appId)) {
      selectedIds.delete(appId);
    } else {
      selectedIds.add(appId);
    }
    selectedIds = new Set(selectedIds);
  }

  async function handleBulk(action) {
    if (selectedIds.size === 0) {
      bulkError = "Select at least one run.";
      return;
    }
    bulkError = "";
    const ids = Array.from(selectedIds);
    const results = await Promise.allSettled(ids.map((id) => applyBulkAction(action, id)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed) {
      bulkError = `${failed} action(s) failed.`;
    } else {
      bulkError = "";
    }
    await loadApplications();
  }

  async function applyBulkAction(action, id) {
    if (action === "start") return await startApplication(id);
    if (action === "pause") return await pauseApplication(id);
    if (action === "resume") return await resumeApplication(id);
    if (action === "cancel") return await cancelApplication(id);
  }

  function requestDelete(appId) {
    pendingDeleteId = appId;
    deleteSuccess = "";
  }

  function cancelDelete() {
    pendingDeleteId = "";
  }

  async function handleDelete(appId) {
    deleteSuccess = "";
    try {
      await deleteApplication(appId);
      deleteSuccess = `Deleted run ${appId}.`;
      selectedIds.delete(appId);
      selectedIds = new Set(selectedIds);
      applications = applications.filter((app) => app.id !== appId);
      pendingDeleteId = "";
      await loadApplications();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to delete run";
    }
  }

  onMount(async () => {
    await Promise.all([loadApplications(), loadJobs()]);
  });
</script>

<svelte:head>
  <title>Applications · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>Applications</h1>
    <p>Track every run and keep the state machine visible.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/">Back to dashboard</a>
      <button class="btn" on:click={handleCreate}>Start new run</button>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}
  {#if bulkError}
    <p class="muted" style="margin-top: 12px;">{bulkError}</p>
  {/if}
  {#if deleteSuccess}
    <p class="muted" style="margin-top: 12px;">{deleteSuccess}</p>
  {/if}

  <section class="card fade-in delay-1" style="margin-top: 24px;">
    <h3>Start a new run</h3>
    <p class="muted">Select a job and platform to create an application run.</p>
    <div class="list">
      <li>
        <span>Job</span>
        <select bind:value={jobId}>
          {#if jobs.length === 0}
            <option value="">No jobs available</option>
          {:else}
            {#each jobs as job (job.id)}
              <option value={job.id}>{job.title} · {job.company}</option>
            {/each}
          {/if}
        </select>
      </li>
      <li>
        <span>Platform</span>
        <select bind:value={platform}>
          <option value="greenhouse">Greenhouse</option>
          <option value="lever">Lever</option>
          <option value="other">Other</option>
        </select>
      </li>
      <li>
        <span>Mode</span>
        <select bind:value={mode}>
          <option value="assisted">Manual</option>
          <option value="fill_review">Fill &amp; Review (Greenhouse)</option>
        </select>
      </li>
    </div>
    {#if createError}
      <p class="muted" style="margin-top: 12px;">{createError}</p>
    {/if}
    {#if createSuccess}
      <p class="muted" style="margin-top: 12px;">{createSuccess}</p>
    {/if}
  </section>

  <section class="grid" style="margin-top: 24px;">
    <div class="card fade-in delay-2">
      <h3>Filters</h3>
      <p class="muted">Refine by state or platform.</p>
      <div class="list">
        <li>
          <span>State</span>
          <select bind:value={stateFilter} on:change={loadApplications}>
            <option value="">All</option>
            <option value="pending">pending</option>
            <option value="analyzing_job">analyzing_job</option>
            <option value="generating_materials">generating_materials</option>
            <option value="awaiting_review">awaiting_review</option>
            <option value="filling_form">filling_form</option>
            <option value="submitting">submitting</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
        </li>
        <li>
          <span>Platform</span>
          <select bind:value={platformFilter} on:change={loadApplications}>
            <option value="">All</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="other">Other</option>
          </select>
        </li>
      </div>
    </div>
    <div class="card fade-in delay-3">
      <h3>Status</h3>
      <p class="muted">Total runs in view.</p>
      <div class="list">
        <li>
          <span>Visible runs</span>
          <strong>{applications.length}</strong>
        </li>
      </div>
    </div>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Bulk actions</h3>
    <p class="muted">Run actions across selected applications.</p>
    <div class="hero-actions">
      <button class="btn" on:click={() => handleBulk("start")}>Start</button>
      <button class="btn" on:click={() => handleBulk("pause")}>Pause</button>
      <button class="btn" on:click={() => handleBulk("resume")}>Resume</button>
      <button class="btn" on:click={() => handleBulk("cancel")}>Cancel</button>
    </div>
  </section>

  <section class="card fade-in delay-1" style="margin-top: 24px;">
    <h3>Recent runs</h3>
    <p class="muted">Showing the latest application records.</p>
    <ul class="list">
      {#if applications.length === 0}
        <li>
          <span>No applications yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each applications as app (app.id)}
          <li>
            <div>
              <input type="checkbox" checked={selectedIds.has(app.id)} on:change={() => toggleSelect(app.id)} />
              <strong>{app.platform}</strong>
              <div class="muted">{app.job_id}</div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{app.state}</span>
              <a class="btn" href={`/applications/${app.id}`}>Details</a>
              {#if pendingDeleteId === app.id}
                <button class="btn ghost" type="button" on:click={() => handleDelete(app.id)}>
                  Confirm delete
                </button>
                <button class="btn" type="button" on:click={cancelDelete}>
                  Cancel
                </button>
              {:else}
                <button
                  class="btn ghost"
                  type="button"
                  disabled={["analyzing_job","generating_materials","awaiting_review","filling_form","submitting"].includes(app.state)}
                  title={["analyzing_job","generating_materials","awaiting_review","filling_form","submitting"].includes(app.state) ? "Cancel the run before deleting" : ""}
                  on:click={() => requestDelete(app.id)}
                >
                  Delete
                </button>
              {/if}
            </div>
          </li>
        {/each}
      {/if}
    </ul>
  </section>
</main>
