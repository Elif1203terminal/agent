"""${app_name} - FastAPI CRUD API"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="${app_name}")

# In-memory storage
db: dict[int, dict] = {}
next_id = 1


class ${model_name}Create(BaseModel):
    ${model_fields_create}


class ${model_name}Response(BaseModel):
    id: int
    ${model_fields_response}


@app.get("/${resource}")
def list_items():
    return list(db.values())


@app.get("/${resource}/{item_id}")
def get_item(item_id: int):
    if item_id not in db:
        raise HTTPException(status_code=404, detail="${model_name} not found")
    return db[item_id]


@app.post("/${resource}", status_code=201)
def create_item(item: ${model_name}Create):
    global next_id
    record = {"id": next_id, **item.model_dump()}
    db[next_id] = record
    next_id += 1
    return record


@app.put("/${resource}/{item_id}")
def update_item(item_id: int, item: ${model_name}Create):
    if item_id not in db:
        raise HTTPException(status_code=404, detail="${model_name} not found")
    db[item_id] = {"id": item_id, **item.model_dump()}
    return db[item_id]


@app.delete("/${resource}/{item_id}", status_code=204)
def delete_item(item_id: int):
    if item_id not in db:
        raise HTTPException(status_code=404, detail="${model_name} not found")
    del db[item_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
