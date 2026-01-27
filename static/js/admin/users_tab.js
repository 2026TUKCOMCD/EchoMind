document.addEventListener('alpine:init', () => {
    Alpine.data('userSearch', () => ({
        query: '',
        users: [],
        loading: false,
        sortBy: 'created_at',
        sortOrder: 'desc',

        async fetchUsers() {
            this.loading = true;
            try {
                // Sorting Params
                const params = new URLSearchParams({
                    q: this.query,
                    sort_by: this.sortBy,
                    order: this.sortOrder
                });

                const res = await fetch(`/admin/api/users?${params.toString()}`);
                const data = await res.json();
                if (data.success) {
                    this.users = data.users;
                }
            } catch (e) {
                console.error("User fetch error:", e);
            } finally {
                this.loading = false;
            }
        },

        sortTable(column) {
            if (this.sortBy === column) {
                // Toggle order
                this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                // New column, default to desc for dates/ids, asc for others if needed, but simple toggle is fine
                this.sortBy = column;
                this.sortOrder = 'desc';
            }
            this.fetchUsers();
        },

        async toggleBan(userId) {
            if (!confirm('사용자의 계정 상태를 변경하시겠습니까?')) return;
            try {
                const res = await fetch(`/admin/users/${userId}/toggle_ban`, { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    const user = this.users.find(u => u.user_id === userId);
                    if (user) user.is_banned = data.is_banned;
                    alert(data.message);
                } else {
                    alert(data.message);
                }
            } catch (e) {
                alert('요청 처리 중 오류가 발생했습니다.');
            }
        }
    }));
});
