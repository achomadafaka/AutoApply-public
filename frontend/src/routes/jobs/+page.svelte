<script>
  import { onMount } from "svelte";
  import {
    analyzeJob,
    createJob,
    deleteJob,
    discoverJobs,
    generateMaterials,
    listJobs
  } from "../../lib/api";

  let jobs = [];
  let error = "";
  let success = "";
  let actionError = "";
  let deleteError = "";
  let pendingDeleteId = "";
  let selectedJobIds = new Set();
  let bulkDeleteError = "";
  let importError = "";
  let importResult = "";
  let discoverError = "";
  let discoverResult = "";
  let discoverBusy = false;
  let discoverRemoteOnly = true;
  let discoverLimit = 50;
  let discoverKeywords =
    "ai, artificial intelligence, machine learning, software, web, frontend, backend, full stack, data, data engineer, data scientist, analytics";
  let resumeVersionId = "";
  let includeCoverLetter = true;
  let analysis = {};
  let materials = {};
  let form = {
    title: "",
    company: "",
    url: "",
    location: "",
    description: "",
    requirements: ""
  };

  async function loadJobs() {
    try {
      jobs = await listJobs(50);
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load jobs";
    }
  }

  async function handleSubmit() {
    error = "";
    success = "";
    if (!form.title.trim() || !form.company.trim()) {
      error = "Title and company are required.";
      return;
    }
    try {
      const created = await createJob({
        title: form.title.trim(),
        company: form.company.trim(),
        url: form.url.trim() || undefined,
        location: form.location.trim() || undefined,
        description: form.description.trim() || undefined,
        requirements: form.requirements.trim() || undefined
      });
      success = created.deduped ? "Job already exists. Using existing entry." : "Job created.";
      form = {
        title: "",
        company: "",
        url: "",
        location: "",
        description: "",
        requirements: ""
      };
      await loadJobs();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to create job";
    }
  }

  function toggleSelect(jobId) {
    if (selectedJobIds.has(jobId)) {
      selectedJobIds.delete(jobId);
    } else {
      selectedJobIds.add(jobId);
    }
    selectedJobIds = new Set(selectedJobIds);
  }

  function selectAllJobs() {
    selectedJobIds = new Set(jobs.map((job) => job.id));
  }

  function clearSelectedJobs() {
    selectedJobIds = new Set();
  }

  async function handleBulkDelete() {
    bulkDeleteError = "";
    if (selectedJobIds.size === 0) {
      bulkDeleteError = "Select at least one job.";
      return;
    }
    const confirmed = window.confirm(`Delete ${selectedJobIds.size} job(s)?`);
    if (!confirmed) return;
    const ids = Array.from(selectedJobIds);
    const results = await Promise.allSettled(ids.map((id) => deleteJob(id)));
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed > 0) {
      bulkDeleteError = `${failed} delete(s) failed. Active runs must be cancelled first.`;
    }
    selectedJobIds = new Set();
    await loadJobs();
  }

  function requestDelete(jobId) {
    pendingDeleteId = jobId;
    deleteError = "";
    success = "";
  }

  function cancelDelete() {
    pendingDeleteId = "";
  }

  async function handleDelete(jobId) {
    deleteError = "";
    success = "";
    try {
      await deleteJob(jobId);
      pendingDeleteId = "";
      jobs = jobs.filter((job) => job.id !== jobId);
      await loadJobs();
    } catch (err) {
      deleteError = err instanceof Error ? err.message : "Unable to delete job";
    }
  }

  function parseCsv(text) {
    const rows = [];
    let row = [];
    let current = "";
    let inQuotes = false;
    for (let i = 0; i < text.length; i++) {
      const char = text[i];
      const next = text[i + 1];
      if (char === '"' && inQuotes && next === '"') {
        current += '"';
        i++;
        continue;
      }
      if (char === '"') {
        inQuotes = !inQuotes;
        continue;
      }
      if (char === "," && !inQuotes) {
        row.push(current);
        current = "";
        continue;
      }
      if ((char === "\n" || char === "\r") && !inQuotes) {
        if (current.length || row.length) {
          row.push(current);
          rows.push(row);
          row = [];
          current = "";
        }
        continue;
      }
      current += char;
    }
    if (current.length || row.length) {
      row.push(current);
      rows.push(row);
    }
    return rows;
  }

  async function handleImport(event) {
    importError = "";
    importResult = "";
    const file = event.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    let items;
    try {
      if (file.name.endsWith(".json")) {
        const parsed = JSON.parse(content);
        if (!Array.isArray(parsed)) {
          throw new Error("JSON must be an array of jobs.");
        }
        items = parsed;
      } else {
        const rows = parseCsv(content);
        if (rows.length < 2) {
          throw new Error("CSV must include a header row.");
        }
        const headers = rows[0].map((h) => h.trim().toLowerCase());
        items = rows.slice(1).filter((r) => r.length).map((row) => {
          const entry = {};
          headers.forEach((key, idx) => {
            entry[key] = (row[idx] || "").trim();
          });
          return entry;
        });
      }
    } catch (err) {
      importError = err instanceof Error ? err.message : "Unable to parse file";
      return;
    }
    const created = [];
    const deduped = [];
    const failed = [];
    for (const item of items) {
      const title = item.title?.trim();
      const company = item.company?.trim();
      if (!title || !company) {
        failed.push({ item, reason: "Missing title/company" });
        continue;
      }
      try {
        const result = await createJob({
          title,
          company,
          url: item.url?.trim() || undefined,
          location: item.location?.trim() || undefined,
          description: item.description?.trim() || undefined,
          requirements: item.requirements?.trim() || undefined
        });
        if (result.deduped) {
          deduped.push(result.job.id);
        } else {
          created.push(result.job.id);
        }
      } catch (err) {
        failed.push({ item, reason: err instanceof Error ? err.message : "Failed" });
      }
    }
    await loadJobs();
    importResult = `Imported ${items.length} jobs: ${created.length} created, ${deduped.length} deduped, ${failed.length} failed.`;
  }

  async function handleDiscover() {
    discoverError = "";
    discoverResult = "";
    discoverBusy = true;
    try {
      const keywords = discoverKeywords
        .split(",")
        .map((k) => k.trim())
        .filter(Boolean);
      const limitValue = Number(discoverLimit);
      const result = await discoverJobs({
        remote_only: discoverRemoteOnly,
        keywords,
        limit: Number.isFinite(limitValue) && limitValue > 0 ? limitValue : undefined
      });
      discoverResult = `Found ${result.created} new, ${result.deduped} deduped, ${result.skipped} filtered.`;
      if (result.failed > 0) {
        discoverResult += ` ${result.failed} sources failed.`;
      }
      await loadJobs();
    } catch (err) {
      discoverError = err instanceof Error ? err.message : "Unable to discover jobs";
    } finally {
      discoverBusy = false;
    }
  }

  async function handleAnalyze(jobId, force = false) {
    actionError = "";
    try {
      const result = await analyzeJob(jobId, force);
      analysis = { ...analysis, [jobId]: result };
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to analyze job";
    }
  }

  async function handleGenerate(jobId) {
    actionError = "";
    try {
      const result = await generateMaterials(jobId, {
        resume_version_id: resumeVersionId.trim() || undefined,
        include_cover_letter: includeCoverLetter
      });
      materials = { ...materials, [jobId]: result };
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to generate materials";
    }
  }

  onMount(loadJobs);
</script>

<svelte:head>
  <title>Jobs · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>Jobs</h1>
    <p>Capture listings, then generate materials and start runs.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/">Back to dashboard</a>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}
  {#if success}
    <p class="muted" style="margin-top: 12px;">{success}</p>
  {/if}
  {#if actionError}
    <p class="muted" style="margin-top: 12px;">{actionError}</p>
  {/if}
  {#if deleteError}
    <p class="muted" style="margin-top: 12px;">{deleteError}</p>
  {/if}
  {#if bulkDeleteError}
    <p class="muted" style="margin-top: 12px;">{bulkDeleteError}</p>
  {/if}
  {#if importError}
    <p class="muted" style="margin-top: 12px;">{importError}</p>
  {/if}
  {#if importResult}
    <p class="muted" style="margin-top: 12px;">{importResult}</p>
  {/if}

  <section class="card fade-in delay-1" style="margin-top: 24px;">
    <h3>New job</h3>
    <p class="muted">Add a listing to your local queue.</p>
    <div class="form-grid">
      <label>
        Title
        <input bind:value={form.title} placeholder="Backend Engineer" />
      </label>
      <label>
        Company
        <input bind:value={form.company} placeholder="Example Labs" />
      </label>
      <label>
        URL
        <input bind:value={form.url} placeholder="https://..." />
      </label>
      <label>
        Location
        <input bind:value={form.location} placeholder="Remote" />
      </label>
      <label>
        Description
        <textarea rows="4" bind:value={form.description}></textarea>
      </label>
      <label>
        Requirements
        <textarea rows="4" bind:value={form.requirements}></textarea>
      </label>
    </div>
    <div style="margin-top: 12px;">
      <button class="btn primary" on:click={handleSubmit}>Create job</button>
    </div>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Materials defaults</h3>
    <p class="muted">Used when generating a cover letter.</p>
    <div class="list">
      <li>
        <span>Résumé version ID (optional)</span>
        <input bind:value={resumeVersionId} placeholder="Uses the configured base résumé" />
      </li>
    </div>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Discover remote jobs</h3>
    <p class="muted">
      Pulls from existing Greenhouse/Lever boards in your database. Add at least one job URL first.
    </p>
    <div class="form-grid">
      <label>
        Keywords (comma-separated)
        <input bind:value={discoverKeywords} />
      </label>
      <label>
        Result limit
        <input type="number" min="1" max="500" bind:value={discoverLimit} />
      </label>
      <label style="display:flex;align-items:center;gap:10px;">
        <input type="checkbox" bind:checked={discoverRemoteOnly} />
        Remote only
      </label>
    </div>
    <div style="margin-top: 12px;">
      <button class="btn primary" on:click={handleDiscover} disabled={discoverBusy}>
        {discoverBusy ? "Finding..." : "Discover jobs"}
      </button>
    </div>
    {#if discoverError}
      <p class="muted" style="margin-top: 12px;">{discoverError}</p>
    {/if}
    {#if discoverResult}
      <p class="muted" style="margin-top: 12px;">{discoverResult}</p>
    {/if}
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Recent jobs</h3>
    <p class="muted">Latest listings in your queue.</p>
    <div class="hero-actions" style="margin: 12px 0;">
      <button class="btn" on:click={selectAllJobs}>Select all</button>
      <button class="btn" on:click={clearSelectedJobs}>Clear</button>
      <button class="btn ghost" on:click={handleBulkDelete}>Delete selected</button>
    </div>
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
              <input type="checkbox" checked={selectedJobIds.has(job.id)} on:change={() => toggleSelect(job.id)} />
              <strong>{job.title}</strong>
              <div class="muted">{job.company}</div>
              {#if analysis[job.id]}
                <div class="muted" style="margin-top: 6px;">
                  Keywords ({analysis[job.id].source}): {analysis[job.id].keywords.join(", ")}
                </div>
              {/if}
              {#if materials[job.id]}
                <div class="muted" style="margin-top: 6px;">
                  Materials: {materials[job.id].created?.length ?? 0} created
                </div>
              {/if}
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{job.status}</span>
              <a class="btn" href={`/jobs/${job.id}`}>Details</a>
              <button class="btn" on:click={() => handleAnalyze(job.id)}>Analyze</button>
              <button class="btn" on:click={() => handleAnalyze(job.id, true)}>Force</button>
              <button class="btn" on:click={() => handleGenerate(job.id)}>Cover letter</button>
              {#if pendingDeleteId === job.id}
                <button class="btn ghost" on:click={() => handleDelete(job.id)}>Confirm delete</button>
                <button class="btn" on:click={cancelDelete}>Cancel</button>
              {:else}
                <button class="btn ghost" on:click={() => requestDelete(job.id)}>Delete</button>
              {/if}
            </div>
          </li>
        {/each}
      {/if}
    </ul>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Import jobs (CSV/JSON)</h3>
    <p class="muted">
      CSV headers: title, company, url, location, description, requirements.
      JSON must be an array of objects with those keys.
    </p>
    <input type="file" accept=".csv,.json" on:change={handleImport} />
  </section>
</main>
