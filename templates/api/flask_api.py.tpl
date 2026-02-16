"""${app_name} - Flask REST API"""

from flask import Flask, jsonify, request, abort

app = Flask(__name__)

# In-memory storage
db = {}
next_id = 1


@app.route("/${resource}", methods=["GET"])
def list_items():
    return jsonify(list(db.values()))


@app.route("/${resource}/<int:item_id>", methods=["GET"])
def get_item(item_id):
    if item_id not in db:
        abort(404)
    return jsonify(db[item_id])


@app.route("/${resource}", methods=["POST"])
def create_item():
    global next_id
    data = request.get_json()
    if not data:
        abort(400)
    record = {"id": next_id, **data}
    db[next_id] = record
    next_id += 1
    return jsonify(record), 201


@app.route("/${resource}/<int:item_id>", methods=["PUT"])
def update_item(item_id):
    if item_id not in db:
        abort(404)
    data = request.get_json()
    db[item_id] = {"id": item_id, **data}
    return jsonify(db[item_id])


@app.route("/${resource}/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    if item_id not in db:
        abort(404)
    del db[item_id]
    return "", 204


if __name__ == "__main__":
    app.run(debug=True, port=8000)
