* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f2f5;
    color: #333;
    line-height: 1.6;
}

header {
    background: ${header_color};
    color: #fff;
    padding: 20px 40px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

header h1 {
    font-size: 1.5rem;
    font-weight: 600;
}

main {
    max-width: 1100px;
    margin: 30px auto;
    padding: 0 20px;
}

.stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 16px;
    margin-bottom: 30px;
}

.stat-card {
    background: #fff;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.stat-value {
    display: block;
    font-size: 2rem;
    font-weight: 700;
    color: ${primary_color};
}

.stat-label {
    display: block;
    font-size: 0.85rem;
    color: #888;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.charts {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
}

.chart-card {
    background: #fff;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.chart-card h2 {
    font-size: 1rem;
    font-weight: 600;
    margin-bottom: 16px;
    color: #555;
}
