"""${app_name} - Flask Web Application"""

from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# In-memory storage
${data_store}


@app.route("/")
def index():
    return render_template("index.html", items=${items_var})


@app.route("/add", methods=["POST"])
def add():
    item = request.form.get("item", "").strip()
    if item:
        ${add_logic}
    return redirect(url_for("index"))


@app.route("/delete/<int:item_id>")
def delete(item_id):
    ${delete_logic}
    return redirect(url_for("index"))


if __name__ == "__main__":
    import os
    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true"), port=5000)
