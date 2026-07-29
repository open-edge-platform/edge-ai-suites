/**
 * Chart management utilities
 */
const ChartManager = (function () {
    let statsChart = null;
    const datasetIndex = {};
    const datasetKeys = [];
    const seriesColors = {};
    const maxPoints = 60;
    const gpuPalette = [
        '#ffb347', '#ff8c42', '#ffd166', '#06d6a0', '#4cc9f0', '#f72585', '#90be6d', '#f8961e'
    ];

    function createDataset(ctx, label, color, fill = true) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 140);
        gradient.addColorStop(0, `${color}33`);
        gradient.addColorStop(1, `${color}05`);
        return {
            label,
            data: [],
            borderColor: color,
            backgroundColor: gradient,
            tension: 0.35,
            fill,
            pointRadius: 0,
            borderWidth: 2,
            spanGaps: true,
        };
    }

    function getOrAssignColor(key) {
        if (seriesColors[key]) return seriesColors[key];

        if (key.startsWith('gpu:')) {
            const id = key.slice(4);
            const idNum = Number(id);
            const paletteIndex = Number.isFinite(idNum) ? Math.abs(idNum) % gpuPalette.length : Object.keys(seriesColors).length % gpuPalette.length;
            seriesColors[key] = gpuPalette[paletteIndex];
            return seriesColors[key];
        }

        seriesColors[key] = '#8ca0c2';
        return seriesColors[key];
    }

    function ensureDataset(key, label, fill = true) {
        if (!statsChart) return null;
        if (datasetIndex[key] !== undefined) return statsChart.data.datasets[datasetIndex[key]];

        const ctx = statsChart.ctx;
        const color = getOrAssignColor(key);
        const ds = createDataset(ctx, label, color, fill);
        if (statsChart.data.labels.length > 0) {
            ds.data = new Array(statsChart.data.labels.length).fill(null);
        }
        datasetIndex[key] = statsChart.data.datasets.length;
        datasetKeys.push(key);
        statsChart.data.datasets.push(ds);
        return ds;
    }

    function trimChart() {
        if (!statsChart) return;
        while (statsChart.data.labels.length > maxPoints) {
            statsChart.data.labels.shift();
            statsChart.data.datasets.forEach((ds) => ds.data.shift());
        }
    }

    function createConsolidatedChart(elId, metrics) {
        const ctx = document.getElementById(elId)?.getContext('2d');
        if (!ctx) return null;
        const colors = ThemeManager.getChartColors();
        Object.keys(datasetIndex).forEach((key) => delete datasetIndex[key]);
        datasetKeys.length = 0;
        Object.keys(seriesColors).forEach((key) => delete seriesColors[key]);
        const datasets = metrics.map(({ key, label, color, fill = true }, index) => {
            datasetIndex[key] = index;
            datasetKeys[index] = key;
            seriesColors[key] = color;
            return createDataset(ctx, label, color, fill);
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

    function pushStatFrame(samples) {
        if (!statsChart || !samples || typeof samples !== 'object') return;

        // Ensure datasets for all keys in this frame.
        Object.keys(samples).forEach((key) => {
            if (datasetIndex[key] !== undefined) return;
            if (key.startsWith('gpu:')) {
                const deviceId = key.slice(4);
                ensureDataset(key, `GPU ${deviceId} %`, false);
            }
        });

        statsChart.data.labels.push(new Date().toLocaleTimeString());
        statsChart.data.datasets.forEach((ds, index) => {
            const key = datasetKeys[index];
            const value = key && Object.prototype.hasOwnProperty.call(samples, key) ? samples[key] : null;
            ds.data.push(value);
        });

        trimChart();
        statsChart.update('none');
    }

    function pushStatSample(key, value) {
        pushStatFrame({ [key]: value });
    }

    function getSeriesColor(key) {
        return getOrAssignColor(key);
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
        pushStatFrame,
        pushStatSample,
        getSeriesColor,
        updateChartColors
    };
})();
