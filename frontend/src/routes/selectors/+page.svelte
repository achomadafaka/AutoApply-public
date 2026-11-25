<script>
  import { onMount } from "svelte";
  import { createSelector, listSelectors, updateSelector } from "../../lib/api";

  let selectors = [];
  let error = "";
  let success = "";
  let platformFilter = "";

  let form = {
    platform: "greenhouse",
    name: "",
    selectorsText: ""
  };

  let editingId = "";
  let editName = "";
  let editSelectorsText = "";

  function parseSelectors(text) {
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  }

  async function loadSelectors() {
    try {
      selectors = await listSelectors({
        platform: platformFilter || undefined,
        limit: 100
      });
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to load selectors";
    }
  }

  async function handleCreate() {
    error = "";
    success = "";
    const parsed = parseSelectors(form.selectorsText);
    if (!form.name.trim() || parsed.length === 0) {
      error = "Name and at least one selector are required.";
      return;
    }
    try {
      await createSelector({
        platform: form.platform,
        name: form.name.trim(),
        selectors: parsed
      });
      success = "Selector created.";
      form = { platform: form.platform, name: "", selectorsText: "" };
      await loadSelectors();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to create selector";
    }
  }

  function startEdit(selector) {
    editingId = selector.id;
    editName = selector.name;
    editSelectorsText = (selector.selectors || []).join("\n");
  }

  function cancelEdit() {
    editingId = "";
    editName = "";
    editSelectorsText = "";
  }

  async function saveEdit(selectorId) {
    error = "";
    success = "";
    const parsed = parseSelectors(editSelectorsText);
    if (!editName.trim() || parsed.length === 0) {
      error = "Name and at least one selector are required.";
      return;
    }
    try {
      await updateSelector(selectorId, {
        name: editName.trim(),
        selectors: parsed
      });
      success = "Selector updated.";
      cancelEdit();
      await loadSelectors();
    } catch (err) {
      error = err instanceof Error ? err.message : "Unable to update selector";
    }
  }

  onMount(loadSelectors);
</script>

<svelte:head>
  <title>Selector Registry · AutoApply</title>
</svelte:head>

<main>
  <section class="hero fade-in">
    <h1>Selector registry</h1>
    <p>Keep stable selectors for automation and update when sites change.</p>
    <div class="hero-actions">
      <a class="btn primary" href="/">Back to dashboard</a>
      <button class="btn" on:click={loadSelectors}>Refresh</button>
    </div>
  </section>

  {#if error}
    <p class="muted" style="margin-top: 12px;">{error}</p>
  {/if}
  {#if success}
    <p class="muted" style="margin-top: 12px;">{success}</p>
  {/if}

  <section class="card fade-in delay-1" style="margin-top: 24px;">
    <h3>New selector</h3>
    <p class="muted">Add a new selector chain for a platform.</p>
    <div class="form-grid">
      <label>
        Platform
        <select bind:value={form.platform}>
          <option value="greenhouse">Greenhouse</option>
          <option value="lever">Lever</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label>
        Name
        <input bind:value={form.name} placeholder="apply_button" />
      </label>
      <label>
        Selectors (one per line)
        <textarea rows="4" bind:value={form.selectorsText}></textarea>
      </label>
    </div>
    <div style="margin-top: 12px;">
      <button class="btn primary" on:click={handleCreate}>Create selector</button>
    </div>
  </section>

  <section class="grid" style="margin-top: 24px;">
    <div class="card fade-in delay-2">
      <h3>Filters</h3>
      <p class="muted">Filter by platform.</p>
      <div class="list">
        <li>
          <span>Platform</span>
          <select bind:value={platformFilter} on:change={loadSelectors}>
            <option value="">All</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="other">Other</option>
          </select>
        </li>
      </div>
    </div>
    <div class="card fade-in delay-3">
      <h3>Registry status</h3>
      <p class="muted">Selectors currently tracked.</p>
      <div class="list">
        <li>
          <span>Total entries</span>
          <strong>{selectors.length}</strong>
        </li>
      </div>
    </div>
  </section>

  <section class="card fade-in delay-2" style="margin-top: 24px;">
    <h3>Selectors</h3>
    <p class="muted">Update selectors when sites change.</p>
    <ul class="list">
      {#if selectors.length === 0}
        <li>
          <span>No selectors yet</span>
          <span class="tag">waiting</span>
        </li>
      {:else}
        {#each selectors as selector (selector.id)}
          <li>
            <div>
              <strong>{selector.name}</strong>
              <div class="muted">{selector.platform}</div>
              <div class="muted" style="margin-top: 6px;">
                {selector.selectors?.join(" · ")}
              </div>
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
              <span class="tag">{selector.success_count}✓/{selector.failure_count}✕</span>
              {#if editingId === selector.id}
                <button class="btn" on:click={() => saveEdit(selector.id)}>Save</button>
                <button class="btn" on:click={cancelEdit}>Cancel</button>
              {:else}
                <button class="btn" on:click={() => startEdit(selector)}>Edit</button>
              {/if}
            </div>
          </li>
          {#if editingId === selector.id}
            <li>
              <div style="width:100%;">
                <div class="form-grid">
                  <label>
                    Name
                    <input bind:value={editName} />
                  </label>
                  <label>
                    Selectors (one per line)
                    <textarea rows="4" bind:value={editSelectorsText}></textarea>
                  </label>
                </div>
              </div>
            </li>
          {/if}
        {/each}
      {/if}
    </ul>
  </section>
</main>
