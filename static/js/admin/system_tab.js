document.addEventListener('alpine:init', () => {
    Alpine.data('systemTab', () => ({
        sysConfig: { hide_dummies: false, log_level: 4 },
        logs: [],
        logPath: '',
        sysLoading: false,
        initSystem() {
            console.log('System Tab Initialized');
            this.fetchConfig();
            this.fetchLogs();
            setInterval(() => this.fetchLogs(), 5000);
        },
        async fetchConfig() {
            try {
                const res = await fetch('/admin/api/system/config');
                const data = await res.json();
                if (data.success && data.config) this.sysConfig = data.config;
            } catch (e) { console.error("Config Fetch Error:", e); }
        },
        async updateConfig(key, value) {
            this.sysLoading = true;
            try {
                const payload = {};
                payload[key] = value;
                await fetch('/admin/api/system/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                await this.fetchConfig();
                alert('설정이 저장되었습니다.');
            } catch (e) { alert(e.message); }
            finally { this.sysLoading = false; }
        },
        async fetchLogs() {
            try {
                const res = await fetch('/admin/api/system/logs');
                const data = await res.json();
                if (data.success) {
                    // [Modified] Log Colorization
                    this.logs = data.logs.map(line => {
                        // Simple parser for layout
                        // Expected format: Date Time Level: Message
                        let className = 'text-slate-600 dark:text-slate-400'; // Default
                        if (line.includes('INFO')) className = 'text-blue-600 dark:text-blue-400';
                        else if (line.includes('WARNING')) className = 'text-amber-600 dark:text-amber-400';
                        else if (line.includes('ERROR') || line.includes('CRITICAL')) className = 'text-red-600 dark:text-red-500 font-bold';
                        else if (line.includes('DEBUG')) className = 'text-slate-500 dark:text-slate-500';

                        // We return an object or HTML string? Alpine x-html might be risky, 
                        // but let's assume we use a structured object or just handle styling via binding if possible.
                        // Ideally: return { text: line, class: className }
                        // But existing template uses `x-text="line"`. 
                        // To allow styling, we need to change template to use x-html or bind class.
                        // Let's change the template logic too. But wait, I can only edit JS here.
                        // Actually, I should change the template to iterate objects.
                        return { text: line, class: className };
                    });
                    this.logPath = data.path;

                    // Auto scroll to bottom
                    this.$nextTick(() => {
                        const box = this.$refs.logBox;
                        if (box) box.scrollTop = box.scrollHeight;
                    });
                }
            } catch (e) { console.error("Log Fetch Error:", e); }
        },
        async resetAllDummies() {
            const msg = '🚨 경고: 모든 더미 사용자 데이터가 영구적으로 삭제됩니다.\\n매칭 기록과 성향 분석 결과도 함께 삭제됩니다.\\n\\n정말 초기화하시겠습니까?';
            if (!confirm(msg)) return;

            this.sysLoading = true;
            try {
                const res = await fetch('/admin/api/system/reset_dummies', { method: 'POST' });
                const data = await res.json();
                alert(data.message);
                if (data.success) {
                    if (window.refreshCharts) window.refreshCharts();
                }
            } catch (e) { alert(e.message); }
            finally { this.sysLoading = false; }
        }
    }));
});
