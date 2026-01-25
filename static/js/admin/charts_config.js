// Chart instances
let mbtiChartPtr = null;
let socionicsChartPtr = null;
let big5ChartPtr = null;

// Initialize when data is available (will be set from template)
window.initCharts = function (statsData) {
    if (!statsData) return;

    const indigo = '79, 70, 229';
    const rose = '244, 63, 94';
    const amber = '251, 191, 36';

    try {
        mbtiChartPtr = createBarChart('mbtiChartFull', statsData.mbti.full.labels, statsData.mbti.full.data, indigo, '사용자 수');
        createBarChart('mbtiChartEI', statsData.mbti.ei.labels, statsData.mbti.ei.data, indigo, '인원');
        createBarChart('mbtiChartSN', statsData.mbti.sn.labels, statsData.mbti.sn.data, indigo, '인원');
        createBarChart('mbtiChartTF', statsData.mbti.tf.labels, statsData.mbti.tf.data, indigo, '인원');
        createBarChart('mbtiChartPJ', statsData.mbti.pj.labels, statsData.mbti.pj.data, indigo, '인원');

        socionicsChartPtr = createBarChart('socionicsChartFull', statsData.socionics.full.labels, statsData.socionics.full.data, rose, '사용자 수');
        createBarChart('socionicsChartEI', statsData.socionics.ei.labels, statsData.socionics.ei.data, rose, '인원');
        createBarChart('socionicsChartSN', statsData.socionics.sn.labels, statsData.socionics.sn.data, rose, '인원');
        createBarChart('socionicsChartTF', statsData.socionics.tf.labels, statsData.socionics.tf.data, rose, '인원');
        createBarChart('socionicsChartPJ', statsData.socionics.pj.labels, statsData.socionics.pj.data, rose, '인원');

        if (document.getElementById('big5Chart')) {
            big5ChartPtr = new Chart(document.getElementById('big5Chart').getContext('2d'), {
                type: 'bar',
                data: {
                    labels: statsData.big5.labels,
                    datasets: [{
                        label: '평균 점수',
                        data: statsData.big5.data,
                        backgroundColor: `rgba(${amber}, 0.6)`,
                        borderColor: `rgba(${amber}, 1)`,
                        borderWidth: 1,
                        borderRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, ticks: { stepSize: 20 } }
                    }
                }
            });
        }
    } catch (e) {
        console.error("Chart Init Error:", e);
    }
};

window.refreshCharts = async function () {
    try {
        const res = await fetch('/admin/api/stats');
        const data = await res.json();
        if (data.success && data.chart_data) {
            const stats = data.chart_data;
            const updateChart = (chart, newData) => {
                if (chart) {
                    chart.data.labels = newData.labels;
                    chart.data.datasets[0].data = newData.data;
                    chart.update();
                }
            };

            if (mbtiChartPtr) updateChart(mbtiChartPtr, stats.mbti.full);
            if (socionicsChartPtr) updateChart(socionicsChartPtr, stats.socionics.full);
            if (big5ChartPtr) {
                big5ChartPtr.data.labels = stats.big5.labels;
                big5ChartPtr.data.datasets[0].data = stats.big5.data;
                big5ChartPtr.update();
            }
        }
    } catch (e) {
        console.error("Chart refresh failed:", e);
    }
};

function createBarChart(id, labels, data, color, labelText) {
    const ctx = document.getElementById(id);
    if (!ctx) return null;
    return new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: labelText,
                data: data,
                backgroundColor: `rgba(${color}, 0.6)`,
                borderColor: `rgba(${color}, 1)`,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, ticks: { stepSize: 1 } }
            }
        }
    });
}
