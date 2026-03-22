(function () {
  const { FileSystemSelectionModel, normalizePath } = window.DumpBuilderSelectionModel;
  const api = window.dumpBuilderApi;
  const model = new FileSystemSelectionModel();
  const previewLimit = 14;
  const formatExtensions = { txt: ".txt", md: ".md", html: ".html" };

  const elements = {
    treeRoot: document.getElementById("treeRoot"),
    chooseRootButton: document.getElementById("chooseRootButton"),
    openPathButton: document.getElementById("openPathButton"),
    clearSelectionButton: document.getElementById("clearSelectionButton"),
    browseOutputButton: document.getElementById("browseOutputButton"),
    generateButton: document.getElementById("generateButton"),
    outputPathInput: document.getElementById("outputPathInput"),
    countLabel: document.getElementById("countLabel"),
    fileCountLabel: document.getElementById("fileCountLabel"),
    directoryCountLabel: document.getElementById("directoryCountLabel"),
    sizeLabel: document.getElementById("sizeLabel"),
    summaryLabel: document.getElementById("summaryLabel"),
    warningLabel: document.getElementById("warningLabel"),
    previewList: document.getElementById("previewList"),
    statusBadge: document.getElementById("statusBadge"),
    statusLabel: document.getElementById("statusLabel"),
    busyBar: document.getElementById("busyBar"),
    formatInputs: [...document.querySelectorAll('input[name="format"]')],
  };

  const state = {
    isGenerating: false,
    lastDirectory: "",
    summaryTimer: null,
  };

  function currentFormat() {
    return elements.formatInputs.find((input) => input.checked)?.value || "txt";
  }

  function currentSelection() {
    return model.buildNormalizedSelection();
  }

  function setStatus(message, tone = "neutral") {
    elements.statusLabel.textContent = message;
    elements.statusBadge.className = `status-badge ${tone}`;
    elements.statusBadge.textContent =
      tone === "success" ? "Completato" :
      tone === "error" ? "Errore" :
      tone === "working" ? "In corso" : "Stato";
  }

  function setBusyState(isBusy) {
    state.isGenerating = isBusy;
    const controls = [
      elements.chooseRootButton,
      elements.openPathButton,
      elements.clearSelectionButton,
      elements.browseOutputButton,
      elements.generateButton,
      elements.outputPathInput,
      ...elements.formatInputs,
    ];
    for (const control of controls) {
      control.disabled = isBusy;
    }
    elements.busyBar.classList.toggle("hidden", !isBusy);
  }

  function savePreferences() {
    api.saveSettings({
      format: currentFormat(),
      outputPath: elements.outputPathInput.value.trim(),
      lastDirectory: state.lastDirectory,
      treeState: model.exportState(),
    });
  }

  function replaceOutputExtension() {
    const output = elements.outputPathInput.value.trim();
    if (!output) {
      return;
    }
    const extension = formatExtensions[currentFormat()];
    const normalized = output.replace(/\\/g, "/");
    const lastSlash = normalized.lastIndexOf("/");
    const lastDot = normalized.lastIndexOf(".");
    const hasExtension = lastDot > lastSlash;
    elements.outputPathInput.value = hasExtension ? `${output.slice(0, lastDot)}${extension}` : `${output}${extension}`;
  }

  function suggestOutputPath() {
    if (elements.outputPathInput.value.trim() || !model.rootIds.length) {
      return;
    }
    const rootNode = model.nodes.get(model.rootIds[0]);
    if (!rootNode) {
      return;
    }
    const separator = rootNode.path.includes("/") ? "/" : "\\";
    const baseDir =
      rootNode.kind === "file"
        ? rootNode.path.slice(0, rootNode.path.lastIndexOf(separator))
        : rootNode.path;
    elements.outputPathInput.value = `${baseDir}${separator}dump${formatExtensions[currentFormat()]}`;
  }

  function scheduleSummaryRefresh() {
    clearTimeout(state.summaryTimer);
    state.summaryTimer = setTimeout(() => {
      refreshSummary().catch((error) => {
        setStatus(error.message || "Errore nel riepilogo", "error");
      });
    }, 120);
  }

  async function ensureChildrenLoaded(nodeId) {
    const node = model.nodes.get(nodeId);
    if (!node || node.kind !== "directory" || node.childrenLoaded) {
      return;
    }
    const children = await api.listDirectory(node.path);
    model.storeChildren(nodeId, children);
  }

  async function ensureNodeReachable(targetId) {
    if (!targetId || !model.rootIds.length) {
      return false;
    }
    if (model.nodes.has(targetId)) {
      return true;
    }

    const rootId = model.rootIds[0];
    if (targetId === rootId) {
      return true;
    }
    if (!targetId.startsWith(`${rootId}/`)) {
      return false;
    }

    const relative = targetId.slice(rootId.length + 1);
    const parts = relative.split("/").filter(Boolean);
    let currentId = rootId;
    for (const part of parts) {
      await ensureChildrenLoaded(currentId);
      const currentNode = model.nodes.get(currentId);
      if (!currentNode) {
        return false;
      }
      const nextId = currentNode.childrenIds.find((childId) => {
        const childNode = model.nodes.get(childId);
        return childNode && childNode.name === part;
      });
      if (!nextId) {
        return false;
      }
      currentId = nextId;
    }
    return currentId === targetId;
  }

  function renderNode(nodeId) {
    const node = model.nodes.get(nodeId);
    const item = document.createElement("li");
    item.className = "tree-item";
    if (!node) {
      return item;
    }

    const checkState = model.getNodeCheckState(nodeId);
    const isExpanded = model.expandedIds.has(nodeId);

    const row = document.createElement("div");
    row.className = `tree-row ${checkState}${model.focusedId === nodeId ? " focused" : ""}`;

    const expander = document.createElement("button");
    expander.className = `expander ${node.kind === "directory" && node.hasChildren ? "" : "hidden"}`;
    expander.textContent = isExpanded ? "−" : "+";
    expander.addEventListener("click", async (event) => {
      event.stopPropagation();
      model.setFocus(nodeId);
      if (model.expandedIds.has(nodeId)) {
        model.collapseNode(nodeId);
      } else {
        model.expandNode(nodeId);
        await ensureChildrenLoaded(nodeId);
      }
      renderTree();
      savePreferences();
    });

    const check = document.createElement("span");
    check.className = `check ${checkState}`;
    check.textContent = checkState === "checked" ? "✓" : checkState === "indeterminate" ? "—" : "";

    const name = document.createElement("span");
    name.className = "tree-name";
    name.textContent = node.name;
    name.title = node.name;

    const kind = document.createElement("span");
    kind.className = "tree-kind";
    kind.textContent = node.kind === "directory" ? "Cartella" : node.kind === "file" ? "File" : "Symlink";
    kind.title = kind.textContent;

    const pathLabel = document.createElement("span");
    pathLabel.className = "tree-path";
    pathLabel.textContent = node.path;
    pathLabel.title = node.path;

    row.append(expander, check, name, kind, pathLabel);
    row.addEventListener("click", async (event) => {
      model.setFocus(nodeId);
      if (event.ctrlKey) {
        await openSelectedPath();
        renderTree();
        savePreferences();
        return;
      }
      model.setSubtreeIncluded(nodeId, checkState !== "checked");
      renderTree();
      scheduleSummaryRefresh();
      savePreferences();
    });
    row.addEventListener("dblclick", async () => {
      model.setFocus(nodeId);
      await openSelectedPath();
      renderTree();
      savePreferences();
    });

    item.appendChild(row);

    if (isExpanded && node.childrenLoaded && node.childrenIds.length) {
      const childrenList = document.createElement("ul");
      childrenList.className = "tree-list";
      for (const childId of node.childrenIds) {
        childrenList.appendChild(renderNode(childId));
      }
      item.appendChild(childrenList);
    }

    return item;
  }

  function renderTree() {
    elements.treeRoot.innerHTML = "";
    if (!model.rootIds.length) {
      const empty = document.createElement("p");
      empty.className = "tree-empty";
      empty.textContent = "Nessuna root caricata.";
      elements.treeRoot.appendChild(empty);
      return;
    }

    const list = document.createElement("ul");
    list.className = "tree-list root";
    for (const rootId of model.rootIds) {
      list.appendChild(renderNode(rootId));
    }
    elements.treeRoot.appendChild(list);
  }

  async function refreshSummary() {
    const selection = currentSelection();
    if (!selection.includes.length) {
      elements.countLabel.textContent = "0 file / 0 cartelle";
      elements.fileCountLabel.textContent = "0";
      elements.directoryCountLabel.textContent = "0";
      elements.sizeLabel.textContent = "0 B";
      elements.warningLabel.textContent = "Nessun warning";
      elements.summaryLabel.textContent =
        "Nessun elemento selezionato per il dump. La root resta navigabile ma non esporta nulla finche non selezioni qualcosa.";
      elements.previewList.innerHTML = "";
      suggestOutputPath();
      return;
    }

    const manifest = await api.getSummary({
      selection,
      outputPath: elements.outputPathInput.value.trim(),
      format: currentFormat(),
    });

    elements.countLabel.textContent = `${manifest.files.length} file / ${manifest.directories.length} cartelle`;
    elements.fileCountLabel.textContent = String(manifest.files.length);
    elements.directoryCountLabel.textContent = String(manifest.directories.length);
    elements.sizeLabel.textContent = manifest.estimatedSizeLabel;
    elements.summaryLabel.textContent =
      `${selection.includes.length} include rule, ${selection.excludes.length} exclude rule. ` +
      `Formato: ${currentFormat().toUpperCase()}. Output: ${elements.outputPathInput.value.trim() || "non ancora scelto"}.`;
    elements.warningLabel.textContent =
      manifest.warnings.length ? `Warning: ${manifest.warnings.slice(0, 3).join(" | ")}` : "Nessun warning";

    elements.previewList.innerHTML = "";
    for (const filePath of manifest.files.slice(0, previewLimit)) {
      const item = document.createElement("li");
      item.textContent = filePath;
      elements.previewList.appendChild(item);
    }
    const remaining = manifest.files.length - previewLimit;
    if (remaining > 0) {
      const item = document.createElement("li");
      item.textContent = `... altri ${remaining} file`;
      elements.previewList.appendChild(item);
    }

    suggestOutputPath();
  }

  async function chooseRoot() {
    try {
      const node = await api.chooseRoot(state.lastDirectory);
      if (!node) {
        return;
      }
      model.addRoot(node);
      state.lastDirectory = node.path;
      renderTree();
      scheduleSummaryRefresh();
      savePreferences();
      setStatus(`Root impostata: ${node.path}`, "success");
    } catch (error) {
      setStatus(error.message || "Errore durante la scelta della root", "error");
    }
  }

  function focusedNode() {
    return model.focusedId ? model.nodes.get(model.focusedId) : null;
  }

  async function openSelectedPath() {
    const node = focusedNode();
    if (!node) {
      setStatus("Seleziona un elemento da aprire", "neutral");
      return;
    }
    const result = await api.openPath(node.path);
    if (!result.ok) {
      setStatus("Impossibile aprire il percorso selezionato", "error");
      window.alert(result.error || "Impossibile aprire il percorso selezionato.");
      return;
    }
    state.lastDirectory = node.path;
    setStatus(`Percorso aperto: ${node.path}`, "success");
  }

  function clearSelection() {
    model.clearSelection();
    renderTree();
    scheduleSummaryRefresh();
    savePreferences();
    setStatus("Selezione azzerata", "neutral");
  }

  async function browseOutput() {
    const nextPath = await api.selectOutput({
      format: currentFormat(),
      initialPath: elements.outputPathInput.value.trim(),
      initialDir: state.lastDirectory,
    });
    if (!nextPath) {
      return;
    }
    elements.outputPathInput.value = nextPath;
    state.lastDirectory = normalizePath(nextPath);
    savePreferences();
    scheduleSummaryRefresh();
    setStatus(`Output selezionato: ${nextPath}`, "success");
  }

  async function generateDump() {
    if (state.isGenerating) {
      return;
    }
    const selection = currentSelection();
    if (!selection.includes.length) {
      setStatus("Manca la selezione da esportare", "error");
      window.alert("Seleziona almeno un file o una cartella nel tree.");
      return;
    }
    const outputPath = elements.outputPathInput.value.trim();
    if (!outputPath) {
      setStatus("Manca il file di output", "error");
      window.alert("Seleziona il file di output.");
      return;
    }

    setBusyState(true);
    setStatus(
      `Generazione in corso con ${selection.includes.length} include rule e ${selection.excludes.length} exclude rule...`,
      "working",
    );

    try {
      const finalOutput = await api.generateDump({
        selection,
        outputPath,
        format: currentFormat(),
      });
      elements.outputPathInput.value = finalOutput;
      state.lastDirectory = normalizePath(finalOutput);
      savePreferences();
      await refreshSummary();
      setStatus(`Dump creato con successo: ${finalOutput}`, "success");
      window.alert(`Dump creato con successo:\n${finalOutput}`);
    } catch (error) {
      setStatus("Errore durante la generazione del dump", "error");
      window.alert(error.message || String(error));
    } finally {
      setBusyState(false);
    }
  }

  function applyTreeState(treeState) {
    model.expandedIds = new Set(Array.isArray(treeState.expandedIds) ? treeState.expandedIds.map(normalizePath) : []);
    model.focusedId = treeState.focusedId ? normalizePath(treeState.focusedId) : null;
    model.includeRules = new Set(Array.isArray(treeState.includeRules) ? treeState.includeRules.map(normalizePath) : []);
    model.excludeRules = new Set(Array.isArray(treeState.excludeRules) ? treeState.excludeRules.map(normalizePath) : []);
    model.pruneRulesOutsideRoots();
    model.simplifyRules();
  }

  async function restoreExpandedTreeState(treeState) {
    const targetIds = [
      ...(Array.isArray(treeState.expandedIds) ? treeState.expandedIds.map(normalizePath) : []),
      treeState.focusedId ? normalizePath(treeState.focusedId) : null,
    ].filter(Boolean);

    for (const targetId of targetIds) {
      await ensureNodeReachable(targetId);
    }

    for (const expandedId of [...model.expandedIds]) {
      const node = model.nodes.get(expandedId);
      if (node && node.kind === "directory") {
        await ensureChildrenLoaded(expandedId);
      }
    }
  }

  async function restoreFromSettings() {
    const settings = await api.loadSettings();
    if (!settings || typeof settings !== "object") {
      return;
    }

    if (settings.format && formatExtensions[settings.format]) {
      const selected = elements.formatInputs.find((input) => input.value === settings.format);
      if (selected) {
        selected.checked = true;
      }
    }
    if (settings.outputPath) {
      elements.outputPathInput.value = settings.outputPath;
    }
    if (settings.lastDirectory) {
      state.lastDirectory = settings.lastDirectory;
    }

    const treeState = settings.treeState;
    if (!treeState?.roots?.length) {
      return;
    }

    const rootId = normalizePath(treeState.roots[0]);
    const rootNode = await api.getNode(rootId, null);
    model.addRoot(rootNode);
    applyTreeState(treeState);
    await restoreExpandedTreeState(treeState);
    renderTree();
    await refreshSummary();
    setStatus("Preferenze caricate", "neutral");
  }

  elements.chooseRootButton.addEventListener("click", chooseRoot);
  elements.openPathButton.addEventListener("click", openSelectedPath);
  elements.clearSelectionButton.addEventListener("click", clearSelection);
  elements.browseOutputButton.addEventListener("click", browseOutput);
  elements.generateButton.addEventListener("click", generateDump);
  elements.outputPathInput.addEventListener("input", () => {
    savePreferences();
    scheduleSummaryRefresh();
  });
  for (const formatInput of elements.formatInputs) {
    formatInput.addEventListener("change", () => {
      replaceOutputExtension();
      savePreferences();
      scheduleSummaryRefresh();
    });
  }

  renderTree();
  restoreFromSettings()
    .catch(() => {
      setStatus("Preferenze non leggibili, uso i valori predefiniti", "error");
    })
    .finally(() => {
      renderTree();
      scheduleSummaryRefresh();
      if (elements.statusLabel.textContent === "Pronto per creare un nuovo dump") {
        setStatus("Pronto per creare un nuovo dump", "neutral");
      }
    });
})();
