/**
 * Chart management utilities
 */
const ChartManager = (function() {
    let statsChart = null;
    const datasetIndex = { cpu: 0, ram: 1, gpu: 2 };
    const maxPoints = 60;

    function createConsolidatedChart(elId, metrics) {
        const ctx = document.getElementById(elId)?.getContext('2d');
        if (!ctx) return null;
        const colors = ThemeManager.getChartColors();
        const datasets = metrics.map(({ label, color }) => {
            const gradient = ctx.createLinearGradient(0, 0, 0, 140);
            gradient.addColorStop(0, `${color}33`);
            gradient.addColorStop(1, `${color}05`);
            return { label, data: [], borderColor: color, backgroundColor: gradient, tension: 0.35, fill: true, pointRadius: 0, borderWidth: 2, spanGaps: true };
        });
        statsChart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { display: false },
                    y: { suggestedMin: 0, suggestedMax: 100, grid: { color: colors.gridColor }, ticks: { color: colors.tickColor } },
                },
                plugins: { legend: { display: false } },
            },
        });
        return statsChart;
    }

    function pushStatSample(key, value) {
        if (!statsChart || datasetIndex[key] === undefined) return;
        const labels = statsChart.data.labels;
        const ds = statsChart.data.datasets[datasetIndex[key]];
        // Advance the shared label when this dataset needs a new slot
        if (ds.data.length >= labels.length) {
            labels.push(new Date().toLocaleTimeString());
            if (labels.length > maxPoints) labels.shift();
        }
        ds.data.push(value);
        if (ds.data.length > maxPoints) ds.data.shift();
        statsChart.update('none');
    }

    function updateChartColors() {
        if (!statsChart) return;
        const colors = ThemeManager.getChartColors();
        statsChart.options.scales.y.grid.color = colors.gridColor;
        statsChart.options.scales.y.ticks.color = colors.tickColor;
        statsChart.update('none');
    }

    return {
        createConsolidatedChart,
        pushStatSample,
        updateChartColors
    };
})();
