from fastapi import APIRouter, Depends, HTTPException

from fastapi_server.models import Task

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"]
)

fake_db = []


def pagination_params(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}


@router.get("/")
def read_root():
    return {"message": "Привет!"}


@router.get("/task/{task_id}")
def get_task(task_id: int):
    if task_id >= len(fake_db): 
        raise HTTPException(status_code=404, detail=f'Нет задачи под номером {task_id!s}')
    return fake_db[task_id]


@router.get("/list")
def get_tasks(pagination: dict = Depends(pagination_params)):  # noqa: B008
    skip = pagination["skip"]
    limit = pagination["limit"]
    return fake_db[skip: skip + limit]


@router.post("/create")
def create_task(task: Task):
    # Здесь task — это уже готовый объект Pydantic, а не просто сырой словарь!
    # Мы можем обращаться к полям через точку: task.title, task.description
    new_task = task.model_dump()
    new_task["id"] = len(fake_db)
    fake_db.append(new_task)
    # Имитируем сохранение в базу данных и возвращаем ответ
    return {
        "message": "Задача успешно создана",
        "task": new_task
    }


@router.put("/task/{task_id}")
def update_task(task_id: int, task: Task):
    for idx, t in enumerate(fake_db):
        if t['id'] == task_id:
            updated_task = task.model_dump()
            updated_task["id"] = task_id
            fake_db[idx] = updated_task
            return updated_task

    raise HTTPException(status_code=404, detail="Задача не найдена")


@router.delete('/task/{task_id}')
def delete_task(task_id: int):
    for idx, t in enumerate(fake_db):
        if t['id'] == task_id:
            del fake_db[idx]
            return {"message": "Задача успешно удалена"}

    raise HTTPException(status_code=404, detail="Задача не найдена")
