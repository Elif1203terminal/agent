"""${app_name} - Flask Dashboard"""

from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Sample dataset
DATA = [
    {"label": "January", "value": 120},
    {"label": "February", "value": 85},
    {"label": "March", "value": 200},
    {"label": "April", "value": 150},
    {"label": "May", "value": 175},
    {"label": "June", "value": 95},
    {"label": "July", "value": 220},
    {"label": "August", "value": 180},
    {"label": "September", "value": 130},
    {"label": "October", "value": 160},
    {"label": "November", "value": 210},
    {"label": "December", "value": 190},
]


@app.route("/")
def index():
    total = sum(d["value"] for d in DATA)
    average = total / len(DATA) if DATA else 0
    maximum = max(d["value"] for d in DATA) if DATA else 0
    return render_template(
        "dashboard.html",
        total=total,
        average=round(average, 1),
        count=len(DATA),
        maximum=maximum,
    )


@app.route("/api/data")
def api_data():
    return jsonify(DATA)


if __name__ == "__main__":
    import os
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true"), port=5000)
