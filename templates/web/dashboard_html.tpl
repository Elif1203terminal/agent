<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${app_name}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
    <header>
        <h1>${app_name}</h1>
    </header>

    <main>
        <section class="stats">
            <div class="stat-card">
                <span class="stat-value">{{ total }}</span>
                <span class="stat-label">Total</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ average }}</span>
                <span class="stat-label">Average</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ count }}</span>
                <span class="stat-label">Entries</span>
            </div>
            <div class="stat-card">
                <span class="stat-value">{{ maximum }}</span>
                <span class="stat-label">Peak</span>
            </div>
        </section>

        <section class="charts">
            <div class="chart-card">
                <h2>Bar Chart</h2>
                <canvas id="barChart"></canvas>
            </div>
            <div class="chart-card">
                <h2>Doughnut Chart</h2>
                <canvas id="doughnutChart"></canvas>
            </div>
        </section>
    </main>

    <script>
        const COLORS = [
            "#3498db", "#2ecc71", "#e74c3c", "#f39c12",
            "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
            "#16a085", "#c0392b", "#8e44ad", "#2c3e50"
        ];

        fetch("{{ url_for('api_data') }}")
            .then(res => res.json())
            .then(data => {
                const labels = data.map(d => d.label);
                const values = data.map(d => d.value);

                new Chart(document.getElementById("barChart"), {
                    type: "bar",
                    data: {
                        labels: labels,
                        datasets: [{
                            label: "Value",
                            data: values,
                            backgroundColor: COLORS.slice(0, values.length),
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } }
                    }
                });

                new Chart(document.getElementById("doughnutChart"), {
                    type: "doughnut",
                    data: {
                        labels: labels,
                        datasets: [{
                            data: values,
                            backgroundColor: COLORS.slice(0, values.length),
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { position: "bottom" } }
                    }
                });
            });
    </script>
</body>
</html>
