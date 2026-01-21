/**
 * Chart management utilities
 */
const ChartManager = (function() {
    const statsCharts = {};

    function createStatChart(elId, label, color) {
        const ctx = document.getElementById(elId)?.getContext('2d');
        if (!ctx) return null;
        const gradient = ctx.createLinearGradient(0, 0, 0, 140);
        gradient.addColorStop(0, `${color}55`);
        gradient.addColorStop(1, `${color}0f`);
        const colors = ThemeManager.getChartColors();
        const chart = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets: [{ label, data: [], borderColor: color, backgroundColor: gradient, tension: 0.35, fill: true, pointRadius: 0, borderWidth: 2 }] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                scales: {
                    x: { display: false },
                    y: {
                        suggestedMin: 0,
                        suggestedMax: 100,
                        grid: { color: colors.gridColor },
                        ticks: {
                            color: colors.tickColor,
                        },
                    },
                },
                plugins: { legend: { display: false } },
            },
        });
        statsCharts[elId.replace('Chart', '')] = chart;
        return chart;
    }

    function pushStatSample(key, value) {
        const chart = statsCharts[key];
        if (!chart) return;
        const maxPoints = 60;
        const labels = chart.data.labels;
        labels.push(new Date().toLocaleTimeString());
        if (labels.length > maxPoints) labels.shift();
        const ds = chart.data.datasets[0];
        ds.data.push(value);
        if (ds.data.length > maxPoints) ds.data.shift();
        chart.update('none');
    }

    function updateChartColors() {
        const colors = ThemeManager.getChartColors();
        Object.values(statsCharts).forEach(chart => {
            if (chart && chart.options && chart.options.scales && chart.options.scales.y) {
                chart.options.scales.y.grid.color = colors.gridColor;
                chart.options.scales.y.ticks.color = colors.tickColor;
                chart.update('none');
            }
        });
    }

    function getChart(key) {
        return statsCharts[key];
    }

    return {
        createStatChart,
        pushStatSample,
        updateChartColors,
        getChart
    };
})();
