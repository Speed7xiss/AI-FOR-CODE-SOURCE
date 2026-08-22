/*
 * Runa AI — lógica do frontend.
 * Fala com o backend via fetch(). Nenhuma chave/segredo fica aqui.
 * A URL da API é configurável (ver API_BASE_URL abaixo).
 */

const API_BASE_URL = window.RUNA_API_BASE_URL || "http://localhost:8000";

const state = {
    conversationId: null,
    conversations: [],
    pendingFiles: [], // File[] aguardando envio junto da próxima mensagem
};

const els = {
    messages: document.getElementById("messages"),
    emptyState: document.getElementById("empty-state"),
    composer: document.getElementById("composer"),
    input: document.getElementById("message-input"),
    sendBtn: document.getElementById("send-btn"),
    attachBtn: document.getElementById("attach-btn"),
    fileInput: document.getElementById("file-input"),
    attachedFiles: document.getElementById("attached-files"),
    conversationList: document.getElementById("conversation-list"),
    newChatBtn: document.getElementById("new-chat-btn"),
    chatTitle: document.getElementById("chat-title"),
    statusDot: document.getElementById("status-dot"),
    statusText: document.getElementById("status-text"),
    dropOverlay: document.getElementById("drop-overlay"),
    chatArea: document.querySelector(".chat-area"),
    exportBtn: document.getElementById("export-btn"),
    menuBtn: document.getElementById("menu-btn"),
    sidebarBackdrop: document.getElementById("sidebar-backdrop"),
    modelSelect: document.getElementById("model-select"),
};

marked.setOptions({ breaks: true });

/* ---------------- Utilidades ---------------- */

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function renderMarkdown(text) {
    const html = marked.parse(text);
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    wrapper.querySelectorAll("pre code").forEach((block) => {
        hljs.highlightElement(block);
        const pre = block.parentElement;
        const btn = document.createElement("button");
        btn.className = "code-copy-btn";
        btn.textContent = "Copiar";
        btn.onclick = () => {
            navigator.clipboard.writeText(block.textContent);
            btn.textContent = "Copiado!";
            setTimeout(() => (btn.textContent = "Copiar"), 1500);
        };
        pre.appendChild(btn);
    });
    return wrapper.innerHTML;
}

async function api(path, options = {}) {
    const defaultHeaders = {
        "ngrok-skip-browser-warning": "true",
    };

    options.headers = {
        ...defaultHeaders,
        ...(options.headers || {}),
    };

    const resp = await fetch(`${API_BASE_URL}${path}`, options);
    if (!resp.ok) {
        let detail = "Erro desconhecido.";
        try {
            detail = (await resp.json()).detail || detail;
        } catch {
            /* resposta sem corpo JSON */
        }
        throw new Error(detail);
    }
    return resp.status === 204 ? null : resp.json();
}

/* ---------------- Status do modelo ---------------- */

async function checkHealth() {
    try {
        const health = await api("/api/health");
        if (health.ollama_reachable) {
            els.statusDot.className = "status-dot online";
            els.statusText.textContent = `Modelo: ${health.model}`;
        } else {
            els.statusDot.className = "status-dot offline";
            els.statusText.textContent = "Ollama indisponível";
        }
    } catch {
        els.statusDot.className = "status-dot offline";
        els.statusText.textContent = "Backend indisponível";
    }
}

async function loadModels() {
    try {
        const result = await api("/api/models");
        els.modelSelect.innerHTML = "";
        if (!result.models.length) {
            els.modelSelect.add(new Option("Nenhum modelo encontrado", ""));
            return;
        }
        result.models.forEach((model) => {
            const label = model.name + (model.is_vision ? " · visão" : "");
            els.modelSelect.add(new Option(label, model.name));
        });
        const preferred = localStorage.getItem("runa-selected-model") || result.default_model;
        if (preferred && result.models.some((model) => model.name === preferred)) {
            els.modelSelect.value = preferred;
        }
    } catch {
        els.modelSelect.innerHTML = "";
        els.modelSelect.add(new Option("Ollama indisponível", ""));
    }
}

/* ---------------- Conversas ---------------- */

async function loadConversations() {
    try {
        state.conversations = await api("/api/conversations");
        renderConversationList();
    } catch (err) {
        console.error("Falha ao carregar conversas:", err);
    }
}

function renderConversationList() {
    els.conversationList.innerHTML = "";
    for (const conv of state.conversations) {
        const item = document.createElement("div");
        item.className = "conversation-item" + (conv.id === state.conversationId ? " active" : "");
        item.textContent = conv.title || "Conversa sem título";
        item.onclick = () => openConversation(conv.id);
        els.conversationList.appendChild(item);
    }
}

function closeSidebar() {
    document.querySelector(".sidebar").classList.remove("open");
    els.sidebarBackdrop.classList.remove("visible");
    els.menuBtn.setAttribute("aria-expanded", "false");
}

function toggleSidebar() {
    const sidebar = document.querySelector(".sidebar");
    const isOpen = sidebar.classList.toggle("open");
    els.sidebarBackdrop.classList.toggle("visible", isOpen);
    els.menuBtn.setAttribute("aria-expanded", String(isOpen));
}

async function openConversation(id) {
    try {
        state.conversationId = id;
        const detail = await api(`/api/conversations/${id}`);
        els.chatTitle.textContent = detail.title;
        els.messages.innerHTML = "";
        els.emptyState.style.display = detail.messages.length ? "none" : "block";
        for (const msg of detail.messages) {
            appendMessage(msg.role, msg.content);
        }
        renderConversationList();
        closeSidebar();
    } catch (err) {
        state.conversationId = null;
        appendMessage("assistant", `Erro ao abrir conversa: ${err.message}`, { error: true });
    }
}

function startNewChat() {
    state.conversationId = null;
    state.pendingFiles = [];
    els.chatTitle.textContent = "Nova conversa";
    els.messages.innerHTML = "";
    els.emptyState.style.display = "block";
    renderAttachedFiles();
    renderConversationList();
    closeSidebar();
}

/* ---------------- Mensagens ---------------- */

function setLoadingContent(bubble, text) {
    bubble.innerHTML = `<span class="typing-label">${escapeHtml(text)}</span><span class="typing-dots"><i></i><i></i><i></i></span>`;
}

function appendMessage(role, content, { loading = false, error = false } = {}) {
    els.emptyState.style.display = "none";
    const wrap = document.createElement("div");
    wrap.className = `message ${role}${loading ? " message-loading" : ""}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "EU" : "R";

    const bubble = document.createElement("div");
    bubble.className = "bubble" + (loading ? " loading" : "") + (error ? " error" : "");
    if (loading) {
        setLoadingContent(bubble, content);
    } else {
        bubble.innerHTML = error ? escapeHtml(content) : renderMarkdown(content);
    }

    wrap.appendChild(avatar);
    wrap.appendChild(bubble);
    els.messages.appendChild(wrap);
    els.messages.scrollTop = els.messages.scrollHeight;
    return bubble;
}

async function ensureConversation() {
    if (state.conversationId) return state.conversationId;
    const conv = await api("/api/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
    });
    state.conversationId = conv.id;
    await loadConversations();
    return conv.id;
}

async function uploadPendingFiles(conversationId) {
    for (const file of state.pendingFiles) {
        const formData = new FormData();
        formData.append("file", file);
        await api(`/api/files/upload?conversation_id=${conversationId}`, {
            method: "POST",
            body: formData,
        });
    }
    state.pendingFiles = [];
    renderAttachedFiles();
}

async function sendMessage(event) {
    event.preventDefault();
    const text = els.input.value.trim();
    if (!text && state.pendingFiles.length === 0) return;

    els.sendBtn.disabled = true;
    appendMessage("user", text || "(arquivos enviados)");
    els.input.value = "";
    autoResize();

    const loadingBubble = appendMessage("assistant", "Pensando", { loading: true });

    try {
        const conversationId = await ensureConversation();
        if (state.pendingFiles.length > 0) {
            setLoadingContent(loadingBubble, "Enviando arquivos...");
            await uploadPendingFiles(conversationId);
            setLoadingContent(loadingBubble, "Pensando");
        }

        const result = await api("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                conversation_id: conversationId,
                model: els.modelSelect.value || undefined,
            }),
        });

        loadingBubble.parentElement.remove();
        appendMessage("assistant", result.response);
        await loadConversations();
    } catch (err) {
        loadingBubble.parentElement.remove();
        appendMessage("assistant", `Erro: ${err.message}`, { error: true });
    } finally {
        els.sendBtn.disabled = false;
    }
}

/* ---------------- Anexos ---------------- */

function renderAttachedFiles() {
    els.attachedFiles.innerHTML = "";
    state.pendingFiles.forEach((file, idx) => {
        const chip = document.createElement("div");
        chip.className = "file-chip";
        const icon = file.name.endsWith(".zip") ? "🗂️" : /\.(png|jpe?g|webp)$/i.test(file.name) ? "🖼️" : "📄";
        chip.innerHTML = `${icon} ${escapeHtml(file.name)} <span class="remove" data-idx="${idx}">✕</span>`;
        els.attachedFiles.appendChild(chip);
    });
    els.attachedFiles.querySelectorAll(".remove").forEach((btn) => {
        btn.onclick = () => {
            state.pendingFiles.splice(Number(btn.dataset.idx), 1);
            renderAttachedFiles();
        };
    });
}

function addFiles(fileList) {
    for (const file of fileList) {
        state.pendingFiles.push(file);
    }
    renderAttachedFiles();
}

/* ---------------- Auto-resize do textarea ---------------- */

function autoResize() {
    els.input.style.height = "auto";
    els.input.style.height = `${Math.min(els.input.scrollHeight, 160)}px`;
}

/* ---------------- Exportar código da conversa ---------------- */

function extractCodeBlocks() {
    const blocks = [];
    document.querySelectorAll(".message.assistant .bubble pre code").forEach((code, i) => {
        // Encontra a classe que começa com "language-"
        const foundClass = [...code.classList].find((c) => c.startsWith("language-"));

        // Se encontrou, tira o "language-". Se não, usa "txt".
        const lang = foundClass ? foundClass.replace("language-", "") : "txt";

        blocks.push({ name: `bloco_${i + 1}.${lang}`, content: code.textContent });
    });
    return blocks;
}

function exportConversationCode() {
    const blocks = extractCodeBlocks();
    if (blocks.length === 0) {
        alert("Nenhum bloco de código encontrado nesta conversa ainda.");
        return;
    }
    blocks.forEach((block) => {
        const blob = new Blob([block.content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = block.name;
        a.click();
        URL.revokeObjectURL(url);
    });
}

/* ---------------- Eventos ---------------- */

els.composer.addEventListener("submit", sendMessage);
els.input.addEventListener("input", autoResize);
els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage(e);
    }
});

els.attachBtn.addEventListener("click", () => els.fileInput.click());
els.fileInput.addEventListener("change", (e) => {
    addFiles(e.target.files);
    els.fileInput.value = "";
});

els.newChatBtn.addEventListener("click", startNewChat);
els.exportBtn.addEventListener("click", exportConversationCode);
els.modelSelect.addEventListener("change", () => {
    if (els.modelSelect.value) localStorage.setItem("runa-selected-model", els.modelSelect.value);
});
els.menuBtn.addEventListener("click", toggleSidebar);
els.sidebarBackdrop.addEventListener("click", closeSidebar);

["dragenter", "dragover"].forEach((evt) =>
    els.chatArea.addEventListener(evt, (e) => {
        e.preventDefault();
        els.dropOverlay.classList.add("active");
    })
);
["dragleave", "drop"].forEach((evt) =>
    els.chatArea.addEventListener(evt, (e) => {
        e.preventDefault();
        if (evt === "drop") addFiles(e.dataTransfer.files);
        els.dropOverlay.classList.remove("active");
    })
);

/* ---------------- Início ---------------- */

checkHealth();
loadModels();
loadConversations();
setInterval(checkHealth, 30000);
