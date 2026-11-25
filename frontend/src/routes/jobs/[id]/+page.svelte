<script>
  import { onMount } from "svelte";
  import {
    analyzeJob,
    cvPreviewUrl,
    getCvWorkspace,
    createApplication,
    createSelector,
    deleteJob,
    deleteMaterial,
    generateMaterials,
    getMaterialFileUrl,
    getJob,
    getJobAnalysis,
    inspectGreenhouse,
    inspectLever,
    listJobMaterials,
    tailorResume
  } from "../../../lib/api";

  export let params;
  let job = null;
  let analysis = null;
  let materials = [];
  let error = "";
  let actionError = "";
  let actionSuccess = "";
  let deleteError = "";
  let pendingDelete = false;
  let deleteMaterialError = "";
  let pendingDeleteMaterialId = "";
  let resumeVersionId = "";
  let draftingBaseline = "";
  let cvWorkspace = null;

  async function loadCvWorkspace() {
    try { cvWorkspace = await getCvWorkspace(); }
    catch { cvWorkspace = null; }
  }

  let includeCoverLetter = true;
  let runPlatform = "greenhouse";
  let runMode = "assisted";
  let runCreatedId = "";
  let greenhouseJobUrl = "";
  let greenhouseError = "";
  let greenhouseLoading = false;
  let greenhouseResult = null;
  let greenhouseIncludeQuestions = true;
  let greenhouseIncludePay = false;
  let leverJobUrl = "";
  let leverError = "";
  let leverLoading = false;
  let leverResult = null;
  let leverRegion = "global";
  let leverIncludeApplyFields = false;
  let leverIncludeSelectorDrafts = false;
  let leverDraftMessage = "";

  async function loadAll() {
    try {
      job = await getJob(params.id);
      if (job?.url) {
        const host = new URL(job.url).hostname;
        if (["job-boards.greenhouse.io", "job-boards.eu.greenhouse.io", "boards.greenhouse.io"].includes(host)) {
          runPlatform = "greenhouse";
          runMode = "fill_review";
        } else {
          runPlatform = ["jobs.lever.co", "jobs.eu.lever.co"].includes(host) ? "lever" : "other";
          runMode = "assisted";
        }
      }
      if (!greenhouseJobUrl && job?.url) {
        greenhouseJobUrl = job.url;
      }
      if (!leverJobUrl && job?.url) {
        leverJobUrl = job.url;
      }
      try {
        analysis = await getJobAnalysis(params.id);
      } catch {
        analysis = null;
      }
      materials = await listJobMaterials(params.id, { limit: 50 });
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load job";
    }
  }

  async function handleAnalyze(force = false) {
    actionError = "";
    actionSuccess = "";
    try {
      analysis = await analyzeJob(params.id, force);
      actionSuccess = force ? "Analysis refreshed." : "Analysis updated.";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to analyze job";
    }
  }

  async function handleGenerate() {
    actionError = "";
    actionSuccess = "";
    try {
      await generateMaterials(params.id, {
        workspace_resume_id: draftingBaseline || undefined,
        resume_version_id: draftingBaseline ? undefined : resumeVersionId.trim() || undefined,
        include_cover_letter: includeCoverLetter
      });
      materials = await listJobMaterials(params.id, { limit: 50 });
      actionSuccess = "Materials generated.";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to generate materials";
    }
  }

  async function handleGenerateAll() {
    actionError = "";
    actionSuccess = "";
    try {
      await tailorResume(params.id, {
        workspace_resume_id: draftingBaseline || undefined,
        resume_version_id: draftingBaseline ? undefined : resumeVersionId.trim() || undefined
      });
      await generateMaterials(params.id, {
        workspace_resume_id: draftingBaseline || undefined,
        resume_version_id: draftingBaseline ? undefined : resumeVersionId.trim() || undefined,
        include_cover_letter: true
      });
      materials = await listJobMaterials(params.id, { limit: 50 });
      actionSuccess = "Tailored resume and cover letter generated.";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to generate materials";
    }
  }

  async function handleTailorResume() {
    actionError = "";
    actionSuccess = "";
    try {
      await tailorResume(params.id, {
        workspace_resume_id: draftingBaseline || undefined,
        resume_version_id: draftingBaseline ? undefined : resumeVersionId.trim() || undefined
      });
      materials = await listJobMaterials(params.id, { limit: 50 });
      actionSuccess = "Tailored resume generated.";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to tailor resume";
    }
  }

  async function handleStartRun() {
    actionError = "";
    actionSuccess = "";
    runCreatedId = "";
    try {
      const created = await createApplication({
        job_id: params.id,
        platform: runPlatform,
        mode: runMode
      });
      runCreatedId = created.id;
      actionSuccess = "Application run created.";
    } catch (err) {
      actionError = err instanceof Error ? err.message : "Unable to create run";
    }
  }

  function requestDelete() {
    pendingDelete = true;
    deleteError = "";
    actionSuccess = "";
  }

  function cancelDelete() {
    pendingDelete = false;
  }

  async function handleDelete() {
    deleteError = "";
    try {
      await deleteJob(params.id);
      window.location.href = "/jobs";
    } catch (err) {
      deleteError = err instanceof Error ? err.message : "Unable to delete job";
    }
  }

  function requestMaterialDelete(materialId) {
    pendingDeleteMaterialId = materialId;
    deleteMaterialError = "";
  }

  function cancelMaterialDelete() {
    pendingDeleteMaterialId = "";
  }

  async function handleMaterialDelete(materialId) {
    deleteMaterialError = "";
    try {
      await deleteMaterial(materialId);
      pendingDeleteMaterialId = "";
      materials = materials.filter((item) => item.id !== materialId);
    } catch (err) {
      deleteMaterialError = err instanceof Error ? err.message : "Unable to delete material";
    }
  }

  async function handleGreenhouseInspect() {
    greenhouseError = "";
    greenhouseLoading = true;
    greenhouseResult = null;
    try {
      if (!greenhouseJobUrl.trim()) {
        greenhouseError = "Job URL is required.";
        return;
      }
      greenhouseResult = await inspectGreenhouse({
        job_url: greenhouseJobUrl.trim(),
        include_questions: greenhouseIncludeQuestions,
        include_pay_transparency: greenhouseIncludePay
      });
    } catch (err) {
      greenhouseError = err instanceof Error ? err.message : "Unable to inspect Greenhouse job";
    } finally {
      greenhouseLoading = false;
    }
  }

  async function handleLeverInspect() {
    leverError = "";
    leverLoading = true;
    leverResult = null;
    leverDraftMessage = "";
    try {
      if (!leverJobUrl.trim()) {
        leverError = "Job URL is required.";
        return;
      }
      leverResult = await inspectLever({
        job_url: leverJobUrl.trim(),
        region: leverRegion,
        include_apply_fields: leverIncludeApplyFields || leverIncludeSelectorDrafts,
        include_selector_drafts: leverIncludeSelectorDrafts
      });
    } catch (err) {
      leverError = err instanceof Error ? err.message : "Unable to inspect Lever posting";
    } finally {
      leverLoading = false;
    }
  }

  async function handleAddSelectorDraft(draft) {
    leverDraftMessage = "";
    try {
      await createSelector({
        platform: "lever",
        name: draft.name,
        selectors: draft.selectors
      });
      leverDraftMessage = `Added selector: ${draft.name}`;
    } catch (err) {
      leverDraftMessage = err instanceof Error ? err.message : "Unable to create selector draft";
    }
  }

  onMount(() => { loadAll(); loadCvWorkspace(); });
</script>

<svelte:head>
  <title>Job {params?.id} · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>{job?.title ?? "Job detail"}</h1>
    <p>Review analysis and generated materials for this job.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/jobs">Back to jobs</a>
      <button class="btn" on:click={loadAll}>Refresh</button>
      {#if pendingDelete}
        <button class="btn ghost" on:click={handleDelete}>Confirm delete</button>
        <button class="btn" on:click={cancelDelete}>Cancel</button>
      {:else}
        <button class="btn ghost" on:click={requestDelete}>Delete</button>
      {/if}
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
  {#if deleteError}
    <p class="muted" style="margin-top: 12px;">{deleteError}</p>
  {/if}
  {#if deleteMaterialError}
    <p class="muted" style="margin-top: 12px;">{deleteMaterialError}</p>
  {/if}
  {#if greenhouseError}
    <p class="muted" style="margin-top: 12px;">{greenhouseError}</p>
  {/if}
  {#if leverError}
    <p class="muted" style="margin-top: 12px;">{leverError}</p>
  {/if}

  {#if job}
    <section class="card fade-in delay-1" style="margin-top: 24px;">
      <h3>Summary</h3>
      <div class="list">
        <li><span>Title</span><strong>{job.title}</strong></li>
        <li><span>Company</span><strong>{job.company}</strong></li>
        <li><span>Location</span><strong>{job.location ?? "—"}</strong></li>
        <li><span>Status</span><strong>{job.status}</strong></li>
      </div>
    </section>
  {/if}

  <section class="grid" style="margin-top: 24px;">
    <div class="card fade-in delay-2">
      <h3>Analysis</h3>
      <p class="muted">Cached keywords and skills.</p>
      {#if analysis}
        <div class="muted">Source: {analysis.source}</div>
        <div class="muted" style="margin-top: 6px;">
          Keywords: {analysis.keywords.join(", ")}
        </div>
        <div class="muted" style="margin-top: 6px;">
          Skills: {analysis.skills.join(", ")}
        </div>
      {:else}
        <p class="muted">No analysis yet.</p>
      {/if}
      <div class="hero-actions" style="margin-top: 12px;">
        <button class="btn" on:click={() => handleAnalyze(false)}>Analyze</button>
        <button class="btn" on:click={() => handleAnalyze(true)}>Force</button>
      </div>
    </div>

    <div class="card fade-in delay-3">
      <h3>Generate cover letter</h3>
    {#if cvWorkspace?.baselines.length}
      <label>
        Private résumé baseline for drafts
        <select bind:value={draftingBaseline}>
          <option value="">Use configured default</option>
          {#each cvWorkspace.baselines as cv (cv.id)}
            <option value={cv.id}>{cv.label}</option>
          {/each}
        </select>
      </label>
      {#if draftingBaseline}
        <a href={cvPreviewUrl(draftingBaseline)} target="_blank" rel="noreferrer">Open baseline PDF</a>
      {/if}
      {#if cvWorkspace.drafting_protocol_loaded}
        <p class="muted">Local CV drafting rules loaded. Check the evidence and layout before using a draft.</p>
      {/if}
    {/if}

      <p class="muted">Creates a cover letter from your base resume. Resume drafts are handled by tailor.</p>
      <div class="list">
        <li>
          <span>Résumé version ID (optional)</span>
          <input bind:value={resumeVersionId} />
        </li>
      </div>
      <div class="hero-actions" style="margin-top: 12px;">
        <button class="btn primary" on:click={handleGenerate}>Generate cover letter</button>
        <button class="btn" on:click={handleGenerateAll}>Tailor + cover letter</button>
      </div>
      <div class="hero-actions" style="margin-top: 8px;">
        <button class="btn" on:click={handleTailorResume}>Tailor resume (base file)</button>
      </div>
    </div>

    <div class="card fade-in delay-3">
      <h3>Start run</h3>
      <p class="muted">Create an application run for this job.</p>
      <div class="list">
        <li>
          <span>Platform</span>
          <select aria-label="Application platform" bind:value={runPlatform}>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="other">Other</option>
          </select>
        </li>
        <li>
          <span>Mode</span>
          <select aria-label="Application mode" bind:value={runMode}>
            <option value="fill_review">Fill &amp; Review (Greenhouse)</option>
            <option value="assisted">Manual</option>
          </select>
        </li>
      </div>
      <div class="hero-actions" style="margin-top: 12px;">
        <button class="btn primary" on:click={handleStartRun}>Create run</button>
        {#if runCreatedId}
          <a class="btn" href={`/applications/${runCreatedId}`}>Open run</a>
        {/if}
      </div>
    </div>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Materials</h3>
    <p class="muted">Latest generated outputs.</p>
    <ul class="list">
      {#if materials.length === 0}
        <li>
          <span>No materials yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each materials as material (material.id)}
          <li>
            <div>
              <strong>{material.type}</strong>
              <div class="muted">{material.created_at}</div>
              <details class="material-details">
                <summary>Preview</summary>
                <pre class="material-pre">{material.content_text}</pre>
              </details>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{material.model_used}</span>
              <a class="btn" href={`/materials/${material.id}`}>Open</a>
              <a class="btn" href={getMaterialFileUrl(material.id)} target="_blank" rel="noreferrer">
                Download docx
              </a>
              {#if pendingDeleteMaterialId === material.id}
                <button class="btn ghost" on:click={() => handleMaterialDelete(material.id)}>Confirm delete</button>
                <button class="btn" on:click={cancelMaterialDelete}>Cancel</button>
              {:else}
                <button class="btn ghost" on:click={() => requestMaterialDelete(material.id)}>Delete</button>
              {/if}
            </div>
          </li>
        {/each}
      {/if}
    </ul>
  </section>

  <section class="card fade-in delay-3" style="margin-top: 24px;">
    <h3>Greenhouse questions</h3>
    <p class="muted">Pull application questions from the Greenhouse Job Board API.</p>
    <div class="list">
      <li>
        <span>Job URL</span>
        <input bind:value={greenhouseJobUrl} placeholder="https://boards.greenhouse.io/company/jobs/12345" />
      </li>
      <li>
        <span>Include questions</span>
        <input type="checkbox" bind:checked={greenhouseIncludeQuestions} />
      </li>
      <li>
        <span>Include pay transparency</span>
        <input type="checkbox" bind:checked={greenhouseIncludePay} />
      </li>
    </div>
    <div class="hero-actions" style="margin-top: 12px;">
      <button class="btn primary" on:click={handleGreenhouseInspect} disabled={greenhouseLoading}>
        {greenhouseLoading ? "Inspecting..." : "Inspect"}
      </button>
    </div>

    {#if greenhouseResult}
      <div class="list" style="margin-top: 16px;">
        <li><span>Board</span><strong>{greenhouseResult.board_token}</strong></li>
        <li><span>Job ID</span><strong>{greenhouseResult.job_id}</strong></li>
        <li><span>Title</span><strong>{greenhouseResult.title ?? "—"}</strong></li>
        <li><span>Location</span><strong>{greenhouseResult.location ?? "—"}</strong></li>
      </div>
      <div class="grid" style="margin-top: 16px;">
        <div class="card">
          <h4>Questions</h4>
          {#if greenhouseResult.questions?.length}
            <ul class="list">
              {#each greenhouseResult.questions as q, index (index)}
                <li>
                  <div>
                    <strong>{q.label ?? q.question ?? "Question"}</strong>
                    <div class="muted">{q.type ?? q.field_type ?? "unknown"}</div>
                  </div>
                  <span class="tag">{q.required ? "required" : "optional"}</span>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No questions returned.</p>
          {/if}
        </div>
        <div class="card">
          <h4>Compliance</h4>
          <details>
            <summary>View raw compliance data</summary>
            <pre class="material-pre">{JSON.stringify({
              compliance: greenhouseResult.compliance,
              data_compliance: greenhouseResult.data_compliance,
              demographic_questions: greenhouseResult.demographic_questions,
              pay_input_ranges: greenhouseResult.pay_input_ranges
            }, null, 2)}</pre>
          </details>
        </div>
      </div>
    {/if}
  </section>

  <section class="card fade-in delay-3" style="margin-top: 24px;">
    <h3>Lever posting</h3>
    <p class="muted">Fetch posting metadata from the Lever public API. Application questions require an API key.</p>
    <div class="list">
      <li>
        <span>Job URL</span>
        <input bind:value={leverJobUrl} placeholder="https://jobs.lever.co/company/posting-id" />
      </li>
      <li>
        <span>Region</span>
        <select bind:value={leverRegion}>
          <option value="global">Global</option>
          <option value="eu">EU</option>
        </select>
      </li>
      <li>
        <span>Include apply fields (requires API key)</span>
        <input type="checkbox" bind:checked={leverIncludeApplyFields} />
      </li>
      <li>
        <span>Generate selector drafts</span>
        <input type="checkbox" bind:checked={leverIncludeSelectorDrafts} />
      </li>
    </div>
    <div class="hero-actions" style="margin-top: 12px;">
      <button class="btn primary" on:click={handleLeverInspect} disabled={leverLoading}>
        {leverLoading ? "Inspecting..." : "Inspect"}
      </button>
    </div>

    {#if leverResult}
      <div class="list" style="margin-top: 16px;">
        <li><span>Site</span><strong>{leverResult.site}</strong></li>
        <li><span>Posting ID</span><strong>{leverResult.posting_id}</strong></li>
        <li><span>Title</span><strong>{leverResult.title ?? "—"}</strong></li>
        <li><span>Location</span><strong>{leverResult.location ?? "—"}</strong></li>
        <li><span>Team</span><strong>{leverResult.team ?? "—"}</strong></li>
        <li><span>Commitment</span><strong>{leverResult.commitment ?? "—"}</strong></li>
        <li><span>Workplace type</span><strong>{leverResult.workplace_type ?? "—"}</strong></li>
      </div>
      <div class="grid" style="margin-top: 16px;">
        <div class="card">
          <h4>Lists</h4>
          {#if leverResult.lists?.length}
            <ul class="list">
              {#each leverResult.lists as item, index (index)}
                <li>
                  <div>
                    <strong>{item?.text ?? "Section"}</strong>
                    <div class="muted">{item?.content ?? ""}</div>
                  </div>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No list sections returned.</p>
          {/if}
        </div>
        <div class="card">
          <h4>Selector drafts</h4>
          {#if leverDraftMessage}
            <p class="muted">{leverDraftMessage}</p>
          {/if}
          {#if leverResult.selector_drafts?.length}
            <ul class="list">
              {#each leverResult.selector_drafts as draft, index (index)}
                <li>
                  <div>
                    <strong>{draft.name}</strong>
                    <div class="muted">{draft.selectors.join(", ")}</div>
                  </div>
                  <button class="btn" on:click={() => handleAddSelectorDraft(draft)}>Add</button>
                </li>
              {/each}
            </ul>
          {:else}
            <p class="muted">No selector drafts yet.</p>
          {/if}
          <details style="margin-top:12px;">
            <summary>View raw response</summary>
            <pre class="material-pre">{JSON.stringify(leverResult.raw, null, 2)}</pre>
          </details>
        </div>
      </div>
    {/if}
  </section>
</main>
