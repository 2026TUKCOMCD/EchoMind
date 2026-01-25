document.addEventListener('alpine:init', () => {
    Alpine.data('dashboardApp', () => ({
        activeTab: new URLSearchParams(window.location.search).get('tab') || 'dashboard',
        viewingFile: false,
        viewingFileName: '',
        viewingFileContent: '',
        viewingPersonality: false,
        personalityFileName: '',
        personalityData: null,

        async viewFile(filename) {
            this.viewingFileName = filename;
            this.viewingFile = true;
            this.viewingFileContent = 'Loading...';
            try {
                const res = await fetch(`/admin/candidates/view/${filename}`);
                const data = await res.json();
                if (data.success) {
                    this.viewingFileContent = JSON.stringify(data.content, null, 2);
                } else {
                    this.viewingFileContent = 'Error: ' + data.message;
                }
            } catch (e) {
                this.viewingFileContent = 'Error loading file.';
            }
        },

        closeFileViewer() {
            this.viewingFile = false;
            this.viewingFileName = '';
            this.viewingFileContent = '';
        },

        async viewPersonality(filename) {
            this.personalityFileName = filename;
            this.viewingPersonality = true;
            this.personalityData = null;
            try {
                const res = await fetch(`/admin/candidates/view/${filename}`);
                const data = await res.json();
                if (data.success && data.content) {
                    const llm = data.content.llm_profile || {};
                    this.personalityData = {
                        name: data.content.meta?.speaker_name || filename,
                        mbti: llm.mbti?.type || 'Unknown',
                        socionics: llm.socionics?.type || 'Unknown',
                        big5: llm.big5?.scores_0_100 || {}
                    };
                } else {
                    this.personalityData = { error: data.message || 'Failed to load' };
                }
            } catch (e) {
                this.personalityData = { error: 'Error loading file.' };
            }
        },

        closePersonalityViewer() {
            this.viewingPersonality = false;
            this.personalityFileName = '';
            this.personalityData = null;
        }
    }));
});
