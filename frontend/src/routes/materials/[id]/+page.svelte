<script>
  import { onMount } from "svelte";
  import { getMaterial } from "../../../lib/api";

  export let params;
  let material = null;
  let error = "";
  let copied = false;

  async function loadMaterial() {
    try {
      material = await getMaterial(params.id);
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load material";
    }
  }

  async function copyToClipboard() {
    copied = false;
    if (!material?.content_text) return;
    try {
      await navigator.clipboard.writeText(material.content_text);
      copied = true;
      setTimeout(() => {
        copied = false;
      }, 1500);
    } catch {
      copied = false;
    }
  }

  function downloadText() {
    if (!material?.content_text) return;
    const blob = new Blob([material.content_text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${material.type || "material"}-${material.id}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  onMount(loadMaterial);
</script>

<svelte:head>
  <title>Material {params?.id} · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>Material detail</h1>
    <p>View, copy, or export generated content.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/jobs">Back to jobs</a>
      <button class="btn" on:click={loadMaterial}>Refresh</button>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}

  {#if material}
    <section class="card fade-in delay-1" style="margin-top: 24px;">
      <h3>Summary</h3>
      <div class="list">
        <li><span>ID</span><strong>{material.id}</strong></li>
        <li><span>Job</span><strong>{material.job_id}</strong></li>
        <li><span>Type</span><strong>{material.type}</strong></li>
        <li><span>Model</span><strong>{material.model_used}</strong></li>
        <li><span>Created</span><strong>{material.created_at}</strong></li>
      </div>
      <div class="hero-actions" style="margin-top: 12px;">
        <button class="btn" on:click={copyToClipboard}>Copy</button>
        <button class="btn" on:click={downloadText}>Download</button>
        {#if copied}
          <span class="tag">Copied</span>
        {/if}
      </div>
    </section>

    <section class="card fade-in delay-2" style="margin-top: 24px;">
      <h3>Content</h3>
      <pre class="material-pre">{material.content_text}</pre>
    </section>
  {/if}
</main>
