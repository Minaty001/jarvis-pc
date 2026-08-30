/* JARVIS PC — Web UI Application
   Fully rewritten to match the HUD HTML layout:
   rail + topbar + views (chat/dashboard/memory/tools/workflows/settings)
   with SSE real-time updates, command palette, and full API wiring.
*/

class JarvisUI {
    constructor() {
        this.currentTab = 'chat';
        this.sessionId = 'web-' + Date.now();
        this.memoryFilter = 'all';
        this.sse = null;
        this.isMicActive = false;
        this.toastCounter = 0;
        this.policies = {};

        this.init();
    }

    /* ══ INITIALIZATION ══ */

    init() {
        this.loadSettings();
        this.bindEvents();
        this.connectSSE();
        this.setNetworkStatus(true);
        this.refreshAll();
        this.checkPermissions();
        setInterval(() => this.refreshSidebarTelemetry(), 5000);
    }

    /* ══ Settings ── persist theme/accent to localStorage */

    loadSettings() {
        const theme = localStorage.getItem('jarvis_theme') || 'dark';
        const accent = localStorage.getItem('jarvis_accent') || 'cyan';
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-accent', accent);

        const themeSelect = document.getElementById('themeSelect');
        if (themeSelect) themeSelect.value = theme;

        const accentSelect = document.getElementById('accentSelect');
        if (accentSelect) accentSelect.value = accent;

        this.applyThemeVars();
    }

    saveSettings() {
        const theme = document.getElementById('themeSelect')?.value || 'dark';
        const accent = document.getElementById('accentSelect')?.value || 'cyan';
        localStorage.setItem('jarvis_theme', theme);
        localStorage.setItem('jarvis_accent', accent);
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-accent', accent);
        this.applyThemeVars();
        this.toast('Settings saved', 'success');
    }

    applyThemeVars() {
        /* accent color variables are already defined via [data-accent] in CSS */
    }

    /* ══ Event Binding ══ */

    bindEvents() {
        /* Navigation — rail items */
        document.querySelectorAll('.rail-item[data-tab]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchTab(btn.dataset.tab);
            });
        });

        /* Network dot / command palette button */
        document.getElementById('cmdBtn')?.addEventListener('click', () => {
            this.toggleCommandPalette();
        });

        /* Chat send */
        const sendBtn = document.getElementById('sendBtn');
        sendBtn?.addEventListener('click', () => this.sendMessage());

        const chatInput = document.getElementById('chatInput');
        chatInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        chatInput?.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        });

        /* Mic button */
        document.getElementById('micBtn')?.addEventListener('click', () => this.toggleMic());

        /* Chip suggestions */
        document.querySelectorAll('.chip[data-msg]').forEach(chip => {
            chip.addEventListener('click', () => {
                chatInput.value = chip.dataset.msg;
                this.sendMessage();
            });
        });

        /* New conversation */
        document.getElementById('newChatBtn')?.addEventListener('click', () => this.newConversation());

        /* Dashboard refresh */
        document.getElementById('refreshDash')?.addEventListener('click', () => this.loadDashboard());

        /* Memory tabs */
        document.querySelectorAll('.pill[data-mem]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.pill').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.memoryFilter = btn.dataset.mem;
                this.loadMemory(btn.dataset.mem);
            });
        });
        document.getElementById('addMemoryBtn')?.addEventListener('click', () => this.showAddMemoryDialog());
        document.getElementById('memorySearch')?.addEventListener('input', (e) => this.filterMemory(e.target.value));

        /* Tools search */
        document.getElementById('toolSearch')?.addEventListener('input', (e) => this.filterTools(e.target.value));

        /* Workflows refresh */
        document.getElementById('refreshWorkflows')?.addEventListener('click', () => this.loadWorkflows());

        /* Voice test button */
        document.getElementById('voiceTestBtn')?.addEventListener('click', () => this.testVoice());

        /* Settings inputs */
        document.querySelectorAll('#settingsView .setting-input, #settingsView select').forEach(el => {
            el.addEventListener('change', () => this.saveSettings());
        });

        /* Wake word toggle */
        document.getElementById('wakeWordToggle')?.addEventListener('change', () => {
            const on = document.getElementById('wakeWordToggle').checked;
            localStorage.setItem('jarvis_wake_word', on);
            this.toast('Wake word ' + (on ? 'enabled' : 'disabled'), 'success');
        });

        /* Refresh permissions button */
        document.getElementById('refreshPermsBtn')?.addEventListener('click', () => this.checkPermissions());

        /* Command palette keyboard shortcut */
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                this.toggleCommandPalette();
            }
            if (e.key === 'Escape') {
                this.closeCommandPalette();
            }
        });
        document.getElementById('palette')?.addEventListener('click', (e) => {
            if (e.target.id === 'palette') this.closeCommandPalette();
        });
        document.getElementById('paletteInput')?.addEventListener('input', (e) => this.filterCommands(e.target.value));

        /* Keyboard nav in command palette */
        document.getElementById('paletteInput')?.addEventListener('keydown', (e) => {
            const items = document.querySelectorAll('.cmd-item');
            const active = document.querySelector('.cmd-item.active');
            let idx = parseInt(active?.dataset.index || 0);
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                idx = Math.min(idx + 1, items.length - 1);
                this._focusCommand(idx);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                idx = Math.max(idx - 1, 0);
                this._focusCommand(idx);
            } else if (e.key === 'Enter') {
                e.preventDefault();
                const results = this._filteredCommands || [];
                results[idx]?.action();
                this.closeCommandPalette();
            }
        });
    }

    _focusCommand(idx) {
        document.querySelectorAll('.cmd-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.cmd-item')[idx]?.classList.add('active');
    }

    /* ══ Tab Switching ══ */

    switchTab(tab) {
        this.currentTab = tab;
        document.querySelectorAll('.rail-item[data-tab]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        document.querySelectorAll('.view').forEach(view => {
            view.classList.toggle('active', view.id === tab + 'View');
        });

        const titleEl = document.getElementById('viewTitle');
        if (titleEl) {
            const titles = {
                chat: 'Chat', dashboard: 'Dashboard', memory: 'Memory',
                tools: 'Tools', workflows: 'Workflows', settings: 'Settings',
            };
            titleEl.textContent = titles[tab] || 'Chat';
        }

        /* Lazy-load tabbed content */
        if (tab === 'dashboard') this.loadDashboard();
        if (tab === 'memory') this.loadMemory(this.memoryFilter);
        if (tab === 'tools') this.loadTools();
        if (tab === 'workflows') this.loadWorkflows();
    }

    /* ══ Network / Connection Status ══ */

    setNetworkStatus(online) {
        const dot = document.getElementById('netDot');
        if (!dot) return;
        if (online) {
            dot.classList.remove('offline');
            dot.title = 'Connected';
        } else {
            dot.classList.add('offline');
            dot.title = 'Offline — retrying...';
        }
    }

    /* ══ SSE — Real-time Server-Sent Events ══ */

    connectSSE() {
        try {
            this.sse = new EventSource('/events/stream');
            this.sse.addEventListener('system_metrics', (e) => {
                const data = JSON.parse(e.data);
                this.updateSidebarTelemetry(data);
                if (this.currentTab === 'dashboard') this.updateDashboardMetrics(data);
            });
            this.sse.addEventListener('event', (e) => {
                const data = JSON.parse(e.data);
                this.addEventToList(data);
                if (this.currentTab === 'dashboard') this.loadDashboard();
            });
            this.sse.addEventListener('chat', (e) => {
                const data = JSON.parse(e.data);
                this.removeThinking();
                this.addMessage('assistant', data.content || data.text || '');
            });
            this.sse.addEventListener('tool_result', (e) => {
                const data = JSON.parse(e.data);
                this.displayToolResult(data);
            });
            this.sse.addEventListener('workflow_update', (e) => {
                const data = JSON.parse(e.data);
                if (this.currentTab === 'workflows') this.loadWorkflows();
            });
            this.sse.onopen = () => {
                this.setNetworkStatus(true);
                this.toast('Connected to JARVIS', 'success');
            };
            this.sse.onerror = () => {
                this.setNetworkStatus(false);
                if (this.sse) this.sse.close();
                setTimeout(() => this.connectSSE(), 5000);
            };
        } catch (e) {
            console.log('SSE not available');
            this.setNetworkStatus(true);
        }
    }

    /* ══ Telemetry (sidebar bars) ══ */

    async refreshSidebarTelemetry() {
        try {
            const res = await fetch('/api/system');
            const data = await res.json();
            this.updateSidebarTelemetry(data);
        } catch { }
    }

    updateSidebarTelemetry(data) {
        const bars = {
            cpu: document.querySelector('.tele[data-metric="cpu"] .tele-bar i'),
            mem: document.querySelector('.tele[data-metric="mem"] .tele-bar i'),
            disk: document.querySelector('.tele[data-metric="disk"] .tele-bar i'),
        };
        const vals = {
            cpu: document.querySelector('.tele[data-metric="cpu"] .tele-val'),
            mem: document.querySelector('.tele[data-metric="mem"] .tele-val'),
            disk: document.querySelector('.tele[data-metric="disk"] .tele-val'),
            uptime: document.querySelector('.tele[data-metric="uptime"] .tele-val'),
        };

        const cpu = data.cpu_percent ?? 0;
        const mem = data.memory_percent ?? 0;
        const disk = data.disk_percent ?? 0;

        if (bars.cpu) bars.cpu.style.width = cpu + '%';
        if (vals.cpu) vals.cpu.textContent = cpu.toFixed(1) + '%';
        if (bars.mem) bars.mem.style.width = mem + '%';
        if (vals.mem) vals.mem.textContent = mem.toFixed(1) + '%';
        if (bars.disk) bars.disk.style.width = disk + '%';
        if (vals.disk) vals.disk.textContent = disk.toFixed(1) + '%';

        if (data.uptime && vals.uptime) {
            const h = Math.floor(data.uptime / 3600);
            const m = Math.floor((data.uptime % 3600) / 60);
            vals.uptime.textContent = h + 'h ' + m + 'm';
        }
    }

    /* ══ Refresh All — called on init and manual refresh */

    async refreshAll() {
        await Promise.all([
            this.loadConversations(),
            this.refreshSidebarTelemetry(),
        ]);
    }

    /* ══ CHAT ══ */

    async sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        if (!message) return;

        this.addMessage('user', message);
        input.value = '';
        input.style.height = 'auto';
        this.showThinking();

        /* Clear empty chat state */
        const empty = document.getElementById('emptyChat');
        if (empty) empty.style.display = 'none';

        try {
            const res = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: this.sessionId }),
            });
            const data = await res.json();
            this.removeThinking();
            if (data.response) {
                this.addMessage('assistant', data.response);
            } else if (data.error) {
                this.addMessage('system', 'Error: ' + data.error);
            }
        } catch (err) {
            this.removeThinking();
            this.addMessage('system', 'Error: ' + err.message);
        }
    }

    addMessage(role, content, avatar) {
        const messages = document.getElementById('chatMessages');
        if (!messages) return;

        /* Remove welcome/empty state on first real message */
        const empty = document.getElementById('emptyChat');
        if (empty) empty.style.display = 'none';

        const div = document.createElement('div');
        div.className = 'message ' + role;

        let avatarText = avatar || (role === 'user' ? 'U' : role === 'assistant' ? 'J' : 'J');

        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        div.innerHTML =
            '<div class="msg-avatar">' + avatarText + '</div>' +
            '<div class="msg-body">' +
                '<div class="msg-content">' + (role === 'assistant' ? this.renderMarkdown(content) : this.escapeHtml(content)) + '</div>' +
                '<div class="msg-meta">' + time + '</div>' +
            '</div>';

        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    clearChat() {
        const messages = document.getElementById('chatMessages');
        if (!messages) return;
        messages.innerHTML = '';
        this.showWelcomeState();
    }

    showWelcomeState() {
        const messages = document.getElementById('chatMessages');
        if (!messages) return;
        messages.innerHTML =
            '<div class="empty-chat" id="emptyChat">' +
                '<div class="empty-ring">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">' +
                        '<circle cx="12" cy="12" r="9"/>' +
                        '<path d="M12 7v5l3 2"/>' +
                    '</svg>' +
                '</div>' +
                '<h2>How can I help you today?</h2>' +
                '<p>Ask anything, or try a suggestion. JARVIS runs locally.</p>' +
                '<div class="chips">' +
                    '<button class="chip" data-msg="What is the system status?">System status</button>' +
                    '<button class="chip" data-msg="Open Firefox">Open an app</button>' +
                    '<button class="chip" data-msg="Search the web for Python tips">Web search</button>' +
                    '<button class="chip" data-msg="Take a screenshot">Screenshot</button>' +
                '</div>' +
            '</div>';

        /* Re-bind chip click handlers */
        messages.querySelectorAll('.chip[data-msg]').forEach(chip => {
            chip.addEventListener('click', () => {
                document.getElementById('chatInput').value = chip.dataset.msg;
                this.sendMessage();
            });
        });
    }

    showThinking() {
        const messages = document.getElementById('chatMessages');
        if (!messages) return;
        const empty = document.getElementById('emptyChat');
        if (empty) empty.style.display = 'none';

        const div = document.createElement('div');
        div.className = 'message assistant thinking-msg';
        div.id = 'thinkingMsg';
        div.innerHTML =
            '<div class="msg-avatar">J</div>' +
            '<div class="msg-body">' +
                '<div class="msg-content">' +
                    '<div class="thinking-dots">' +
                        '<div class="thinking-dot"></div>' +
                        '<div class="thinking-dot"></div>' +
                        '<div class="thinking-dot"></div>' +
                    '</div>' +
                '</div>' +
            '</div>';
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    removeThinking() {
        document.getElementById('thinkingMsg')?.remove();
    }

    /* ══ Conversations (sidebar) ═─ */

    async loadConversations() {
        const list = document.getElementById('chatList');
        if (!list) return;
        list.innerHTML = '<div class="empty-state">Loading…</div>';
        try {
            const res = await fetch('/api/conversations');
            const data = await res.json();
            const sessions = data.sessions || [];
            if (!sessions.length) {
                list.innerHTML = '<div class="empty-state">No conversations</div>';
                return;
            }
            /* Sort by timestamp descending (most recent first) */
            list.innerHTML = sessions.map(s =>
                '<div class="conversation-item" data-session="' + this.escapeHtml(s) + '">' +
                    '<div class="conversation-name">' + this.escapeHtml(s) + '</div>' +
                    '<div class="conversation-preview">Click to load</div>' +
                '</div>'
            ).join('');
            /* Bind click */
            list.querySelectorAll('.conversation-item').forEach(item => {
                item.addEventListener('click', () => {
                    list.querySelectorAll('.conversation-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    /* In a full impl, this would load the conversation history */
                });
            });
        } catch (e) {
            list.innerHTML = '<div class="empty-state">No conversations</div>';
        }
    }

    newConversation() {
        this.sessionId = 'web-' + Date.now();
        const messages = document.getElementById('chatMessages');
        if (messages) {
            messages.innerHTML = '';
            this.showWelcomeState();
        }
        this.loadConversations();
        this.toast('New conversation started', 'success');
    }

    /* ══ Dashboard ══ */

    async loadDashboard() {
        const el = document.querySelector('#dashboardView .scroll');
        if (!el) return;
        el.style.opacity = '0.5';

        try {
            const [statusRes, metricsRes, systemRes, toolsRes] = await Promise.all([
                fetch('/api/status').catch(() => ({ json: () => ({}) })),
                fetch('/api/metrics').catch(() => ({ json: () => ({}) })),
                fetch('/api/system').catch(() => ({ json: () => ({}) })),
                fetch('/api/tools').catch(() => ({ json: () => ({}) })),
            ]);

            const status = await statusRes.json();
            const metrics = await metricsRes.json();
            const system = await systemRes.json();
            const tools = await toolsRes.json();

            this.updateDashboardMetrics(system);
            this.updateDashboardMetrics(status.world_state || {});

            /* Tool usage stats */
            const statsEl = document.getElementById('toolStats');
            if (statsEl && tools.stats) {
                const stats = tools.stats;
                const totalCalls = Object.values(stats).reduce((s, v) => s + (v.calls || 0), 0);
                const totalSuccess = Object.values(stats).reduce((s, v) => s + (v.successes || 0), 0);
                const rate = totalCalls > 0 ? ((totalSuccess / totalCalls) * 100).toFixed(0) : '--';

                statsEl.innerHTML =
                    '<div style="display:flex;flex-direction:column;gap:8px">' +
                        '<div style="display:flex;justify-content:space-between;font-size:13px">' +
                            '<span style="color:var(--text-2)">Total Calls</span>' +
                            '<span style="color:var(--accent);font-family:monospace">' + totalCalls + '</span>' +
                        '</div>' +
                        '<div style="display:flex;justify-content:space-between;font-size:13px">' +
                            '<span style="color:var(--text-2)">Success Rate</span>' +
                            '<span style="color:var(--green);font-family:monospace">' + rate + '%</span>' +
                        '</div>' +
                        '<div style="display:flex;justify-content:space-between;font-size:13px">' +
                            '<span style="color:var(--text-2)">Registered</span>' +
                            '<span style="color:var(--accent);font-family:monospace">' + (tools.tools?.length || 0) + '</span>' +
                        '</div>' +
                    '</div>';
            }

            /* Active workflows */
            await this.loadWorkflowsMini();

            /* Events */
            try {
                const evRes = await fetch('/api/events');
                const evData = await evRes.json();
                const eventsEl = document.getElementById('recentEvents');
                if (eventsEl && evData.events?.length) {
                    eventsEl.innerHTML = evData.events.slice(-10).reverse().map(ev =>
                        '<div class="event-item">' +
                            '<div class="event-dot ' + (ev.severity || 'info') + '"></div>' +
                            '<div>' +
                                '<div class="event-text">' + (ev.source || 'system') + ': ' + this.truncate(JSON.stringify(ev.payload || ev.data || ''), 80) + '</div>' +
                                '<div class="event-time">' + (ev.timestamp ? new Date(ev.timestamp * 1000).toLocaleTimeString() : '') + '</div>' +
                            '</div>' +
                        '</div>'
                    ).join('');
                }
            } catch { }

            /* Suggestions */
            this.updateSuggestions();

            const lastUpdate = document.getElementById('lastUpdate');
            if (lastUpdate) lastUpdate.textContent = 'Updated ' + new Date().toLocaleTimeString();
        } catch (e) {
            console.error('Dashboard error:', e);
        } finally {
            el.style.opacity = '1';
        }
    }

    updateDashboardMetrics(data) {
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        const cpu = data.cpu_percent ?? 0;
        const mem = data.memory_percent ?? 0;
        const disk = data.disk_percent ?? 0;

        set('gCpu', cpu.toFixed(1) + '%');
        set('gMem', mem.toFixed(1) + '%');
        set('gDisk', disk.toFixed(1) + '%');

        this.drawGauge('cpuGauge', cpu, cpu > 80 ? 'var(--red)' : cpu > 60 ? 'var(--yellow)' : 'var(--accent)');
        this.drawGauge('memGauge', mem, mem > 80 ? 'var(--red)' : mem > 60 ? 'var(--yellow)' : 'var(--accent)');
        this.drawGauge('diskGauge', disk, disk > 85 ? 'var(--red)' : disk > 70 ? 'var(--yellow)' : 'var(--accent)');

        if (data.uptime) {
            const h = Math.floor(data.uptime / 3600);
            const m = Math.floor((data.uptime % 3600) / 60);
            set('gUptime', h + 'h ' + m + 'm');
        }
    }

    drawGauge(canvasId, percent, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const size = canvas.width;
        const center = size / 2;
        const radius = center - 8;
        const lineWidth = 6;

        ctx.clearRect(0, 0, size, size);

        /* Background arc */
        ctx.beginPath();
        ctx.arc(center, center, radius, 0, Math.PI * 2);
        ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--bg-4').trim();
        ctx.lineWidth = lineWidth;
        ctx.stroke();

        /* Value arc */
        const angle = (percent / 100) * Math.PI * 2 - Math.PI / 2;
        ctx.beginPath();
        ctx.arc(center, center, radius, -Math.PI / 2, angle);
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.lineCap = 'round';
        ctx.stroke();
    }

    async loadWorkflowsMini() {
        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            const active = data.active || [];
            const activeEl = document.getElementById('activeWorkflows');
            if (activeEl) {
                if (!active.length) {
                    activeEl.innerHTML = '<div class="empty-state">No active workflows</div>';
                } else {
                    activeEl.innerHTML = active.map(w =>
                        '<div style="font-size:12px;padding:4px 0">' +
                            '<strong>' + this.escapeHtml(w.name || w.id || 'Unknown') + '</strong> ' +
                            '<span style="color:var(--text-3)">(' + (w.status || 'running') + ')</span>' +
                        '</div>'
                    ).join('');
                }
            }
        } catch { }
    }

    updateSuggestions() {
        const el = document.getElementById('suggestions');
        if (!el) return;
        el.innerHTML =
            '<div style="font-size:12px;color:var(--text-2);line-height:1.6">' +
                '<div>• CPU: <span style="color:var(--accent)">' + document.getElementById('gCpu')?.textContent || '--' + '</span></div>' +
                '<div>• Memory: <span style="color:var(--accent)">' + document.getElementById('gMem')?.textContent || '--' + '</span></div>' +
                '<div>\u2022 Try saying \u201CHey Jarvis, what\u2019s the system status?\u201D</div>' +
            '</div>';
    }

    addEventToList(ev) {
        const el = document.getElementById('recentEvents');
        if (!el) return;
        if (el.querySelector('.empty-state')) el.innerHTML = '';

        const item = document.createElement('div');
        item.className = 'event-item';
        item.innerHTML =
            '<div class="event-dot ' + (ev.severity || 'info') + '"></div>' +
            '<div>' +
                '<div class="event-text">' + (ev.source || 'system') + ': ' + this.truncate(JSON.stringify(ev.payload || ev.data || ''), 80) + '</div>' +
                '<div class="event-time">' + new Date().toLocaleTimeString() + '</div>' +
            '</div>';
        el.insertBefore(item, el.firstChild);
        while (el.children.length > 15) el.removeChild(el.lastChild);
    }

    /* ══ Memory View ══ */

    async loadMemory(type) {
        const content = document.getElementById('memoryContent');
        if (!content) return;
        content.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Loading memory…</div>';

        try {
            if (type === 'all') {
                const [sumRes, workingRes, episodicRes, semanticRes] = await Promise.all([
                    fetch('/api/memory').catch(() => ({ json: () => ({}) })),
                    fetch('/api/memory/working').catch(() => ({ json: () => ({ entries: [] }) })),
                    fetch('/api/memory/episodic').catch(() => ({ json: () => ({ entries: [] }) })),
                    fetch('/api/memory/semantic').catch(() => ({ json: () => ({ entries: [] }) })),
                ]);

                const summary = await sumRes.json();
                const working = await workingRes.json();
                const episodic = await episodicRes.json();
                const semantic = await semanticRes.json();

                let cards = [];

                (working.entries || []).forEach(e => {
                    cards.push(this.createMemoryCard('working', e.key || '', e.value || ''));
                });
                (episodic.entries || []).forEach(e => {
                    cards.push(this.createMemoryCard('episodic', e.id || '', e.content || '',
                        'Outcome: ' + (e.outcome || 'N/A') + ' | Tags: ' + ((e.tags || []).join(', '))));
                });
                (semantic.entries || []).forEach(e => {
                    cards.push(this.createMemoryCard('semantic', e.id || '', e.content || '',
                        'Category: ' + (e.category || 'general') + ' | Confidence: ' + ((e.confidence || 0).toFixed(2))));
                });

                if (cards.length === 0) {
                    content.innerHTML = '<div class="empty-state" style="grid-column:1/-1">' +
                        this.escapeHtml(summary.summary || 'No memories stored yet') + '</div>';
                } else {
                    content.innerHTML = cards.join('');
                    this.bindMemoryDelete();
                }
            } else {
                const res = await fetch('/api/memory/' + type);
                const data = await res.json();
                let cards = [];
                (data.entries || []).forEach(e => {
                    const title = e.key || e.name || e.id || '';
                    let body = e.value || e.content || e.steps || '';
                    if (Array.isArray(body)) body = body.join('\n');
                    body = typeof body === 'object' ? JSON.stringify(body) : String(body);
                    const meta = this.getMemoryMeta(type, e);
                    cards.push(this.createMemoryCard(type, title, body, meta));
                });
                if (cards.length === 0) {
                    content.innerHTML = '<div class="empty-state" style="grid-column:1/-1">No ' + type + ' memories found</div>';
                } else {
                    content.innerHTML = cards.join('');
                    this.bindMemoryDelete();
                }
            }
        } catch (e) {
            content.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Error loading memories</div>';
        }
    }

    createMemoryCard(type, title, content, meta) {
        return '<div class="mem-card" data-type="' + type + '" data-id="' + this.escapeHtml(title) + '">' +
            '<div class="mem-card-header">' +
                '<span class="mem-card-type ' + type + '">' + type + '</span>' +
                '<button class="mem-card-delete" title="Delete">' +
                    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">' +
                        '<line x1="18" y1="6" x2="6" y2="18"/>' +
                        '<line x1="6" y1="6" x2="18" y2="18"/>' +
                    '</svg>' +
                '</button>' +
            '</div>' +
            '<div class="mem-card-content"><strong>' + this.escapeHtml(title) + '</strong><br>' +
                this.escapeHtml(this.truncate(String(content), 200)) +
            '</div>' +
            (meta ? '<div class="mem-card-meta">' + this.escapeHtml(meta) + '</div>' : '') +
        '</div>';
    }

    bindMemoryDelete() {
        document.querySelectorAll('.mem-card-delete').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const card = btn.closest('.mem-card');
                const type = card.dataset.type;
                const id = card.dataset.id;
                if (confirm('Delete this memory?')) {
                    await fetch('/api/memory/' + type + '/' + id, { method: 'DELETE' });
                    card.remove();
                    this.toast('Memory deleted', 'success');
                }
            });
        });
    }

    showAddMemoryDialog() {
        const content = prompt('Memory content:');
        if (content) {
            fetch('/memory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content, type: 'episodic' }),
            }).then(() => {
                this.loadMemory(this.memoryFilter);
                this.toast('Memory added', 'success');
            });
        }
    }

    getMemoryMeta(type, e) {
        switch (type) {
            case 'episodic':    return 'Outcome: ' + (e.outcome || 'N/A') + ' | Importance: ' + (e.importance || 0);
            case 'semantic':    return 'Category: ' + (e.category || '') + ' | Confidence: ' + ((e.confidence || 0).toFixed(2));
            case 'procedural':  return 'Success: ' + (e.success_count || 0) + ' | Rate: ' + ((e.success_rate || 0) * 100).toFixed(0) + '%';
            case 'preference':  return 'Category: ' + (e.category || '');
            case 'failure':     return 'Occurrences: ' + (e.occurrence_count || 0);
            default:            return '';
        }
    }

    filterMemory(query) {
        document.querySelectorAll('.mem-card').forEach(card => {
            const text = card.textContent.toLowerCase();
            card.style.display = text.includes(query.toLowerCase()) ? '' : 'none';
        });
    }

    /* ══ Tools View ══ */

    async loadTools() {
        const grid = document.getElementById('toolsGrid');
        if (!grid) return;
        grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Loading tools…</div>';

        try {
            const res = await fetch('/api/tools');
            const data = await res.json();
            if (!data.tools?.length) {
                grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">No tools registered</div>';
                return;
            }
            grid.innerHTML = data.tools.map(tool =>
                '<div class="tool-card" data-name="' + this.escapeHtml(tool.name) + '">' +
                    '<div class="tool-card-header">' +
                        '<div class="tool-name">' + this.escapeHtml(tool.name) + '</div>' +
                        '<span class="tool-badge risk-' + (tool.risk || 'low') + '">' + (tool.risk || 'low') + '</span>' +
                    '</div>' +
                    '<div class="tool-desc">' + this.escapeHtml(tool.description || '') + '</div>' +
                    '<div class="tool-meta">' +
                        '<span class="tool-badge">' + this.escapeHtml(tool.category || 'custom') + '</span>' +
                        (tool.requires_confirmation ? '<span class="tool-badge" style="border-left:2px solid var(--yellow)">confirmation</span>' : '') +
                    '</div>' +
                    (tool.parameters && Object.keys(tool.parameters).length > 0 ?
                        '<div class="tool-execute">' +
                            '<div class="tool-execute-form">' +
                                Object.entries(tool.parameters).map(([k, v]) =>
                                    '<input class="tool-execute-input" data-tool="' + this.escapeHtml(tool.name) + '" data-param="' + this.escapeHtml(k) + '" placeholder="' + this.escapeHtml(k) + '" />'
                                ).join('') +
                                '<button class="tool-execute-btn" onclick="jarvis.executeTool(\'' + this.escapeHtml(tool.name) + '\')">Run</button>' +
                            '</div>' +
                            '<div class="tool-result" id="toolResult-' + this.escapeHtml(tool.name) + '" style="display:none"></div>' +
                        '</div>'
                    : '') +
                '</div>'
            ).join('');
        } catch (e) {
            grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1">Error loading tools</div>';
        }
    }

    filterTools(query) {
        document.querySelectorAll('.tool-card').forEach(card => {
            const name = card.dataset.name?.toLowerCase() || '';
            card.style.display = name.includes(query.toLowerCase()) ? '' : 'none';
        });
    }

    async executeTool(toolName) {
        const resultEl = document.getElementById('toolResult-' + toolName);
        if (!resultEl) return;

        const inputs = document.querySelectorAll('.tool-execute-input[data-tool="' + toolName + '"]');
        const args = {};
        inputs.forEach(inp => { args[inp.dataset.param] = inp.value; });

        resultEl.style.display = 'block';
        resultEl.className = 'tool-result';
        resultEl.textContent = 'Executing…';

        try {
            const res = await fetch('/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool: toolName, args }),
            });
            const data = await res.json();
            resultEl.className = 'tool-result ' + (data.success ? 'success' : 'error');
            resultEl.textContent = data.success
                ? JSON.stringify(data.result, null, 2)
                : 'Error: ' + (data.error || 'Unknown error');
        } catch (e) {
            resultEl.className = 'tool-result error';
            resultEl.textContent = 'Error: ' + e.message;
        }
    }

    displayToolResult(data) {
        const el = document.getElementById('toolResult-' + (data.tool || ''));
        if (el) {
            el.className = 'tool-result ' + (data.success ? 'success' : 'error');
            el.textContent = data.success
                ? JSON.stringify(data.result, null, 2)
                : 'Error: ' + (data.error || 'Unknown');
            el.style.display = 'block';
        }
    }

    /* ══ Workflows View ══ */

    async loadWorkflows() {
        const el = document.getElementById('workflowsContent');
        if (!el) return;
        el.innerHTML = '<div class="empty-state">Loading…</div>';

        try {
            const res = await fetch('/api/tasks');
            const data = await res.json();
            const all = [...(data.active || []), ...(data.pending || []), ...(data.completed || [])];

            if (!all.length) {
                el.innerHTML = '<div class="empty-state">No workflows</div>';
                return;
            }

            el.innerHTML = all.map(w => {
                const pct = w.steps_total > 0 ? ((w.steps_completed / w.steps_total) * 100) : 0;
                return '<div class="workflow-card">' +
                    '<div class="workflow-header">' +
                        '<div class="workflow-name">' + this.escapeHtml(w.name || w.id || 'Unknown') + '</div>' +
                        '<span class="workflow-status ' + (w.status || 'running') + '">' + (w.status || 'running') + '</span>' +
                    '</div>' +
                    (w.steps_total > 0 ?
                        '<div class="workflow-progress"><div class="workflow-progress-fill" style="width:' + pct + '%"></div></div>'
                    : '') +
                    '<div class="workflow-meta">' +
                        '<span>' + (w.started_at ? 'Started: ' + new Date(w.started_at).toLocaleTimeString() : '') + '</span>' +
                        '<span>' + (w.duration ? 'Duration: ' + w.duration + 's' : '') + '</span>' +
                        '<span>' + (w.steps_completed || 0) + '/' + (w.steps_total || '?') + ' steps</span>' +
                    '</div>' +
                '</div>';
            }).join('');
        } catch (e) {
            el.innerHTML = '<div class="empty-state">Error loading workflows</div>';
        }
    }

    /* ══ Voice ══ */

    toggleMic() {
        const btn = document.getElementById('micBtn');
        const viz = document.getElementById('voiceVisualization');
        this.isMicActive = !this.isMicActive;
        if (this.isMicActive) {
            btn.classList.add('recording');
            viz.classList.add('active');
            this.toast('Listening… (voice input is browser-based, optional)', 'info');
        } else {
            btn.classList.remove('recording');
            viz.classList.remove('active');
        }
    }

    testVoice() {
        this.toast('Voice test: mic access would be requested here. Browser Web Speech API is optional.', 'info');
    }

    /* ══ Hardware Permissions ══ */

    async checkPermissions() {
        try {
            const response = await fetch('/api/health');
            if (response.ok) {
                // Server is running, check permissions via API
                const micStatus = document.getElementById('micPermStatus');
                const speakerStatus = document.getElementById('speakerPermStatus');
                const cameraStatus = document.getElementById('cameraPermStatus');
                
                if (micStatus) micStatus.textContent = 'Available';
                if (micStatus) micStatus.className = 'perm-status granted';
                if (speakerStatus) speakerStatus.textContent = 'Available';
                if (speakerStatus) speakerStatus.className = 'perm-status granted';
                if (cameraStatus) cameraStatus.textContent = 'Available';
                if (cameraStatus) cameraStatus.className = 'perm-status granted';
            }
        } catch (error) {
            console.error('Permission check failed:', error);
        }
    }

    /* ══ Command Palette ══ */

    toggleCommandPalette() {
        const overlay = document.getElementById('palette');
        overlay.classList.toggle('active');
        if (overlay.classList.contains('active')) {
            document.getElementById('paletteInput').value = '';
            document.getElementById('paletteInput').focus();
            this.filterCommands('');
        }
    }

    closeCommandPalette() {
        document.getElementById('palette')?.classList.remove('active');
    }

    filterCommands(query) {
        const commands = [
            { label: 'Go to Chat',       icon: '🏠', action: () => this.switchTab('chat') },
            { label: 'Go to Dashboard',  icon: '📊', action: () => this.switchTab('dashboard') },
            { label: 'Go to Memory',     icon: '💾', action: () => this.switchTab('memory') },
            { label: 'Go to Tools',      icon: '🔧', action: () => this.switchTab('tools') },
            { label: 'Go to Workflows',  icon: '⚡', action: () => this.switchTab('workflows') },
            { label: 'Go to Settings',   icon: '⚙️', action: () => this.switchTab('settings') },
            { label: 'New Conversation', icon: '💬', action: () => this.newConversation() },
            { label: 'Clear Chat',       icon: '🗑', action: () => this.clearChat() },
            { label: 'Refresh Dashboard',icon: '↻', action: () => this.loadDashboard() },
            { label: 'Test Connection',  icon: '🔌', action: () => this.testConnection() },
        ];

        this._filteredCommands = commands.filter(c =>
            c.label.toLowerCase().includes(query.toLowerCase())
        );

        const el = document.getElementById('paletteResults');
        if (!this._filteredCommands.length) {
            el.innerHTML = '<div class="cmd-item" style="color:var(--text-3)">No commands found</div>';
            return;
        }
        el.innerHTML = this._filteredCommands.map((c, i) =>
            '<div class="cmd-item ' + (i === 0 ? 'active' : '') + '" data-index="' + i + '">' +
                '<span>' + c.icon + '</span>' +
                '<span>' + c.label + '</span>' +
                '<span class="cmd-shortcut">' + c.label.substring(0, 1) + '</span>' +
            '</div>'
        ).join('');

        el.querySelectorAll('.cmd-item').forEach((item, i) => {
            item.addEventListener('click', () => {
                this._filteredCommands[i].action();
                this.closeCommandPalette();
            });
        });
    }

    /* ══ Connection test ══ */

    async testConnection() {
        try {
            const res = await fetch('/health');
            const data = await res.json();
            if (data.status === 'healthy') {
                this.toast('JARVIS is online and responding', 'success');
            } else {
                this.toast('JARVIS responded but status unclear', 'info');
            }
        } catch (e) {
            this.toast('Cannot reach JARVIS. Start with: python3 run.py', 'error');
        }
    }

    /* ══ Toast ══ */

    toast(message, type = 'info') {
        const container = document.getElementById('toasts');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = 'toast ' + type;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    }

    /* ══ Markdown ══ */

    renderMarkdown(text) {
        let html = this.escapeHtml(text);

        /* Code blocks */
        html = html.replace(/```[\w]?\\n([\s\S]*?)```/g, function(m, code) {
            return '<pre><code>' + code + '</code></pre>';
        });

        /* Inline code — do after code blocks */
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        /* Bold */
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        /* Italic */
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        /* Links */
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

        /* Blockquotes */
        html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');

        /* Lists (unordered) */
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*?<\/li>)/gs, '<ul>$1</ul>');

        /* Paragraphs */
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');
        html = '<p>' + html + '</p>';
        html = html.replace(/<p><\/p>/g, '');

        return html;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = String(text || '');
        return div.innerHTML;
    }

    truncate(text, max) {
        return (String(text || '').length > max) ? String(text).slice(0, max) + '...' : String(text);
    }
}

/* Initialize on DOM ready */
document.addEventListener('DOMContentLoaded', () => {
    window.jarvis = new JarvisUI();
});
