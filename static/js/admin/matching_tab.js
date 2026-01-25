document.addEventListener('alpine:init', () => {
    Alpine.data('dummyManager', () => ({
        // 유효한 유형 목록
        mbtiTypes: ['INTJ', 'INTP', 'ENTJ', 'ENTP', 'INFJ', 'INFP', 'ENFJ', 'ENFP',
            'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ', 'ISTP', 'ISFP', 'ESTP', 'ESFP'],
        socionicsTypes: ['ILE', 'SEI', 'ESE', 'LII', 'EIE', 'LSI', 'SLE', 'IEI',
            'SEE', 'ILI', 'LIE', 'ESI', 'LSE', 'EII', 'IEE', 'SLI'],

        // State
        loading: false,
        error: null,
        randomCount: 5,        // [Fix] Missing var
        bulkDeleteCount: 10,   // [Fix] Missing var
        bulkDeleteOrder: 'recent', // [Fix] Missing var

        // Dummy Form Data
        formData: {
            name: '',
            mbti: 'ISTJ',
            socionics: 'LII',
            big5: { openness: 50, conscientiousness: 50, extraversion: 50, agreeableness: 50, neuroticism: 50 },
            activity: 500
        },

        // Candidate Data (Users + Dummies)
        candidates: [],
        searchQuery: '',

        // Simulation Data
        selectedIds: [],
        dummyResult: null,
        dummyError: null,
        dummyWeights: { sim: 0.5, chem: 0.4, act: 0.1 },
        locked: { sim: false, chem: false, act: false },
        debounceTimer: null,
        debounceSim: null,

        async init() {
            await this.fetchCandidates();
        },

        // 후보군 목록 (Users + Dummies)
        async fetchCandidates() {
            this.loading = true;
            try {
                const url = '/admin/api/users' + (this.searchQuery ? '?q=' + encodeURIComponent(this.searchQuery) : '');
                const res = await fetch(url);
                const data = await res.json();
                if (data.success) {
                    this.candidates = data.users;
                }
            } catch (e) {
                console.error("Fetch candidates error:", e);
            } finally {
                this.loading = false;
            }
        },

        onSearchInput() {
            if (this.debounceTimer) clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.fetchCandidates();
            }, 300);
        },

        // 더미 생성
        async createDummy() {
            if (!this.formData.name) {
                alert('이름을 입력해주세요.');
                return;
            }
            this.loading = true;
            try {
                const res = await fetch('/admin/api/dummy/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.formData)
                });
                const data = await res.json();
                if (data.success) {
                    alert(data.message);
                    this.formData.name = '';
                    await this.fetchCandidates();
                    this.refreshStats(); // Refresh stats
                } else {
                    alert(data.message);
                }
            } catch (e) {
                alert(e.message);
            } finally {
                this.loading = false;
            }
        },

        async createRandomDummy() {
            this.loading = true;
            try {
                const res = await fetch('/admin/api/dummy/random', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ count: parseInt(this.randomCount) || 1 })
                });
                const data = await res.json();
                if (data.success) {
                    alert(data.message || '생성 완료');
                    await this.fetchCandidates();
                    this.refreshStats(); // Refresh stats after creating random dummies
                } else {
                    alert(data.message || '오류 발생');
                }
            } catch (e) {
                alert(e.message);
            } finally {
                this.loading = false;
            }
        },

        async deleteBulkDummies() {
            const count = parseInt(this.bulkDeleteCount) || 10;
            if (!confirm(`정말로 ${this.bulkDeleteOrder === 'recent' ? '최근' : '오래된'} 순으로 더미 사용자 ${count}명을 삭제하시겠습니까?\n(이 작업은 되돌릴 수 없습니다)`)) return;

            this.loading = true;
            try {
                const res = await fetch('/admin/api/dummy/bulk_delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        count: count,
                        order: this.bulkDeleteOrder
                    })
                });
                const data = await res.json();
                if (data.success) {
                    alert(data.message || '삭제 완료');
                    await this.fetchCandidates();
                    this.refreshStats(); // Refresh stats after bulk delete
                } else {
                    alert(data.message || '오류 발생');
                }
            } catch (e) {
                alert(e.message);
            } finally {
                this.loading = false;
            }
        },

        async deleteDummy(id) {
            if (!confirm('정말 삭제하시겠습니까? (이 작업은 되돌릴 수 없습니다)')) return;
            try {
                const res = await fetch(`/admin/api/dummy/${id}`, { method: 'DELETE' });
                const data = await res.json();
                if (data.success) {
                    this.removeFromSimulation(parseInt(id));
                    this.dummyError = data.message;
                    await this.fetchCandidates();
                    this.refreshStats(); // Refresh stats
                } else {
                    this.dummyError = data.message;
                }
            } catch (e) {
                this.dummyError = e.message;
            } finally {
                this.loading = false;
            }
        },

        addToSimulation(id) {
            if (!id) return;
            id = parseInt(id);
            if (this.selectedIds.includes(id)) return;

            if (this.selectedIds.length >= 2) {
                this.selectedIds.shift();
            }
            this.selectedIds.push(id);

            if (this.selectedIds.length === 2) {
                this.runSimulation();
            } else {
                this.dummyResult = null;
            }
        },

        removeFromSimulation(id) {
            this.selectedIds = this.selectedIds.filter(x => x !== id);
            this.dummyResult = null;
        },

        toggleSelect(id) {
            id = parseInt(id);
            if (this.selectedIds.includes(id)) {
                this.removeFromSimulation(id);
            } else {
                this.addToSimulation(id);
            }
        },

        getSelectedName(index) {
            const id = this.selectedIds[index];
            if (!id) return '';
            const user = this.candidates.find(u => u.user_id === id);
            return user ? (user.nickname || user.username) : 'Unknown';
        },

        resetWeights() {
            this.dummyWeights = { sim: 0.5, chem: 0.4, act: 0.1 };
            this.locked = { sim: false, chem: false, act: false };
            if (this.selectedIds.length === 2) {
                this.runSimulation();
            }
        },

        adjustDummyWeights(trigger) {
            if (this.locked[trigger]) return;

            this.dummyWeights[trigger] = Math.max(0, Math.min(1, parseFloat(this.dummyWeights[trigger])));

            const others = Object.keys(this.dummyWeights).filter(k => k !== trigger);
            const lockedOthers = others.filter(k => this.locked[k]);
            const unlockedOthers = others.filter(k => !this.locked[k]);

            if (lockedOthers.length === 2) {
                const sumLocked = this.dummyWeights[lockedOthers[0]] + this.dummyWeights[lockedOthers[1]];
                this.dummyWeights[trigger] = parseFloat((1.0 - sumLocked).toFixed(2));
                return;
            }

            if (lockedOthers.length === 1) {
                const lockedKey = lockedOthers[0];
                const unlockedKey = unlockedOthers[0];
                let remainingForUnlocked = 1.0 - this.dummyWeights[trigger] - this.dummyWeights[lockedKey];

                if (remainingForUnlocked < 0) {
                    this.dummyWeights[trigger] = parseFloat((1.0 - this.dummyWeights[lockedKey]).toFixed(2));
                    remainingForUnlocked = 0;
                }
                this.dummyWeights[unlockedKey] = parseFloat(remainingForUnlocked.toFixed(2));
                return;
            }

            const remaining = 1.0 - this.dummyWeights[trigger];
            const currentSumOthers = this.dummyWeights[others[0]] + this.dummyWeights[others[1]];

            if (currentSumOthers === 0) {
                this.dummyWeights[others[0]] = parseFloat((remaining / 2).toFixed(2));
                this.dummyWeights[others[1]] = parseFloat((remaining / 2).toFixed(2));
            } else {
                this.dummyWeights[others[0]] = parseFloat(((this.dummyWeights[others[0]] / currentSumOthers) * remaining).toFixed(2));
                this.dummyWeights[others[1]] = parseFloat(((this.dummyWeights[others[1]] / currentSumOthers) * remaining).toFixed(2));
            }

            // Final correction
            const sum = this.dummyWeights.sim + this.dummyWeights.chem + this.dummyWeights.act;
            if (Math.abs(sum - 1.0) > 0.001) {
                const diff = 1.0 - sum;
                const target = unlockedOthers.length > 0 ? unlockedOthers[0] : (lockedOthers.length < 2 ? others[0] : null);
                if (target) {
                    this.dummyWeights[target] = parseFloat((this.dummyWeights[target] + diff).toFixed(2));
                }
            }

            // [Fix] Trigger simulation update if 2 users selected
            if (this.selectedIds.length === 2 && this.debounceSim) {
                clearTimeout(this.debounceSim);
            }
            if (this.selectedIds.length === 2) {
                this.debounceSim = setTimeout(() => this.runSimulation(), 200);
            }
        },

        refreshStats() {
            if (window.refreshCharts) window.refreshCharts();
        },

        async runSimulation() {
            if (this.selectedIds.length !== 2) {
                this.dummyError = '시뮬레이션을 위해 2명의 사용자(더미 포함)를 선택하세요.';
                return;
            }

            const senderId = this.selectedIds[0];
            const receiverId = this.selectedIds[1];

            this.loading = true;
            this.dummyError = null;
            this.dummyResult = null;

            try {
                const res = await fetch('/admin/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sender_id: senderId,
                        receiver_id: receiverId,
                        w_sim: this.dummyWeights.sim,
                        w_chem: this.dummyWeights.chem,
                        w_act: this.dummyWeights.act
                    })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.message || 'Simulation failed');
                this.dummyResult = data;

                // Details formatting
                if (this.dummyResult.details) {
                    // Ensure details are properly formatted if needed
                }

            } catch (e) {
                this.dummyError = e.message;
            } finally {
                this.loading = false;
            }
        }
    }));
});
