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
        randomCount: 5,
        bulkDeleteCount: 10,
        bulkDeleteOrder: 'recent',

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

        // Chart instance
        chart: null,

        async init() {
            await this.fetchCandidates();
        },

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
                    this.refreshStats();
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
                    this.refreshStats();
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
                    this.refreshStats();
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
                    this.refreshStats();
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

        getSelectedInfo(index) {
            const id = this.selectedIds[index];
            if (!id) return null;
            return this.candidates.find(u => u.user_id === id);
        },
        getSelectedName(index) {
            const user = this.getSelectedInfo(index);
            return user ? (user.nickname || user.username) : '';
        },

        getBig5Label(key) {
            const lowerKey = key.toLowerCase();
            const map = {
                'openness': '개방성', 'o': '개방성',
                'conscientiousness': '성실성', 'c': '성실성',
                'extraversion': '외향성', 'e': '외향성',
                'agreeableness': '우호성', 'a': '우호성',
                'neuroticism': '신경성', 'n': '신경성'
            };
            return map[lowerKey] || key;
        },

        getBig5Tooltip(key, val) {
            const lowerKey = key.toLowerCase();
            const fullNames = {
                'o': 'Openness', 'openness': 'Openness',
                'c': 'Conscientiousness', 'conscientiousness': 'Conscientiousness',
                'e': 'Extraversion', 'extraversion': 'Extraversion',
                'a': 'Agreeableness', 'agreeableness': 'Agreeableness',
                'n': 'Neuroticism', 'neuroticism': 'Neuroticism'
            };
            const name = fullNames[lowerKey] || (key.charAt(0).toUpperCase() + key.slice(1));
            return name + ': ' + val;
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

            // 1. 값 보정 (Number 보장 및 Range 제한)
            let val = parseFloat(this.dummyWeights[trigger]);
            if (isNaN(val)) val = 0;
            val = Math.max(0, Math.min(1, val));
            this.dummyWeights[trigger] = val;

            // 2. 나머지 배분
            const others = Object.keys(this.dummyWeights).filter(k => k !== trigger);
            const remaining = 1.0 - val;

            const unlockedOthers = others.filter(k => !this.locked[k]);

            // 나머지 합계 계산
            let sumOthers = 0;
            others.forEach(k => sumOthers += parseFloat(this.dummyWeights[k]));

            if (unlockedOthers.length === 0) {
                let sumLocked = 0;
                others.forEach(k => { if (this.locked[k]) sumLocked += parseFloat(this.dummyWeights[k]); });

                if (val + sumLocked > 1.0001 || val + sumLocked < 0.9999) {
                    this.dummyWeights[trigger] = parseFloat((1.0 - sumLocked).toFixed(2));
                }
                return;
            }

            // 2-2. Unlocked가 있으면 비례 배분
            const currentSumUnlocked = unlockedOthers.reduce((sum, key) => sum + parseFloat(this.dummyWeights[key]), 0);

            if (currentSumUnlocked === 0) {
                const share = remaining / unlockedOthers.length;
                unlockedOthers.forEach(k => {
                    this.dummyWeights[k] = parseFloat(share.toFixed(2));
                });
            } else {
                let sumLockedOthers = 0;
                const lockedOthers = others.filter(k => this.locked[k]);
                lockedOthers.forEach(k => sumLockedOthers += parseFloat(this.dummyWeights[k]));

                let availableForUnlocked = 1.0 - val - sumLockedOthers;

                if (availableForUnlocked < 0) {
                    availableForUnlocked = 0;
                    this.dummyWeights[trigger] = parseFloat((1.0 - sumLockedOthers).toFixed(2));
                    val = this.dummyWeights[trigger];
                }

                if (currentSumUnlocked > 0) {
                    unlockedOthers.forEach(k => {
                        const original = parseFloat(this.dummyWeights[k]);
                        const ratio = original / currentSumUnlocked;
                        this.dummyWeights[k] = parseFloat((availableForUnlocked * ratio).toFixed(2));
                    });
                } else {
                    const share = availableForUnlocked / unlockedOthers.length;
                    unlockedOthers.forEach(k => this.dummyWeights[k] = parseFloat(share.toFixed(2)));
                }
            }

            // 3. Final Rounding Correction
            let currentSumAll = Object.values(this.dummyWeights).reduce((a, b) => a + parseFloat(b), 0);
            const diff = 1.0 - currentSumAll;

            if (Math.abs(diff) > 0.001 && unlockedOthers.length > 0) {
                const target = unlockedOthers[0];
                this.dummyWeights[target] = parseFloat((parseFloat(this.dummyWeights[target]) + diff).toFixed(2));
            }

            // [Modified] Instant Chart Update (Client-side)
            // Don't wait for server response to update the shape
            if (this.dummyResult && this.dummyResult.details) {
                try {
                    this.updateChart(this.dummyResult.details);
                } catch (e) {
                    console.error("Chart update error:", e);
                }
            }

            // Debounce Simulation (for Total Score from Server)
            if (this.selectedIds.length === 2) {
                if (this.debounceSim) clearTimeout(this.debounceSim);
                this.debounceSim = setTimeout(() => {
                    console.log("Triggering simulation...");
                    this.runSimulation();
                }, 200);
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

                // [Modified] Update Chart
                if (this.dummyResult.details) {
                    // Use nextTick to ensure DOM is ready if x-show triggered
                    this.$nextTick(() => {
                        this.updateChart(this.dummyResult.details);
                    });
                } else {
                    // Reset chart if no details
                    if (this.chart) {
                        this.chart.destroy();
                        this.chart = null;
                    }
                }

            } catch (e) {
                this.dummyError = e.message;
            } finally {
                this.loading = false;
            }
        },

        updateChart(details) {
            const ctx = document.getElementById('matchRadarChart');
            if (!ctx) return;

            const labels = ['성향 유사도 (Similarity)', '케미스트리 (Chemistry)', '대화 스타일 (Activity)'];

            // [Modified] Display Weighted Contribution
            // Raw scores (0.0-1.0) * Weight (0.0-1.0) * Scaling Factor (300)
            const w_sim = parseFloat(this.dummyWeights.sim) || 0;
            const w_chem = parseFloat(this.dummyWeights.chem) || 0;
            const w_act = parseFloat(this.dummyWeights.act) || 0;

            const weightedData = [
                (details.similarity_score * w_sim * 300).toFixed(0),
                (details.chemistry_score * w_chem * 300).toFixed(0),
                (details.activity_score * w_act * 300).toFixed(0)
            ];

            console.log("Updating chart with:", weightedData);

            // [Modified] Force Re-render by Destroying Old Instance
            // This ensures no state issues prevent the update
            if (this.chart) {
                this.chart.destroy();
                this.chart = null;
            }

            this.chart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Weighted Impact',
                        data: weightedData,
                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                        borderColor: 'rgba(99, 102, 241, 1)',
                        pointBackgroundColor: 'rgba(99, 102, 241, 1)',
                        pointBorderColor: '#fff',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: 'rgba(99, 102, 241, 1)'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        r: {
                            angleLines: {
                                display: true,
                                color: document.documentElement.classList.contains('dark') ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)'
                            },
                            grid: {
                                color: document.documentElement.classList.contains('dark') ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.05)'
                            },
                            suggestedMin: 0,
                            suggestedMax: 100,
                            ticks: {
                                display: false,
                                backdropColor: 'transparent'
                            },
                            pointLabels: {
                                color: document.documentElement.classList.contains('dark') ? '#e4e4e7' : '#475569', // Zinc 200 vs Slate 600
                                font: {
                                    size: 11,
                                    weight: 'bold'
                                }
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    return context.raw + ' (Impact)';
                                }
                            }
                        }
                    },
                    animation: false // Disable animation for instant feel
                }
            });
        }
    }));
});
