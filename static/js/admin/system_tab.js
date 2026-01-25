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
                    this.logs = data.logs;
                    this.logPath = data.path;
                    this.$nextTick(() => {
                        const el = this.$refs.logBox;
                        if (el) el.scrollTop = el.scrollHeight;
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
