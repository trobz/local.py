from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from rich.progress import BarColumn, Progress, TextColumn


@dataclass
class TaskResult:
    name: str
    success: bool
    message: str | None = None
    error: Exception | None = None


def run_tasks(tasks, max_workers: int = 4):
    results = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        future_to_task = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                # submit tasks
                for task_info in tasks:
                    name = task_info["name"]
                    func = task_info["func"]
                    kwargs = task_info.get("args", {})
                    task_id = progress.add_task(
                        name,
                        total=100,
                    )
                    future = executor.submit(func, progress, task_id, **kwargs)
                    future_to_task[future] = {"name": name, "task_id": task_id}

                # Wait for all tasks to complete
                for future in as_completed(future_to_task):
                    task_data = future_to_task[future]
                    name = task_data["name"]
                    task_id = task_data["task_id"]

                    try:
                        future.result()
                        progress.update(task_id, completed=100)
                        results.append(TaskResult(name=name, success=True, message="Completed"))

                    except Exception as e:
                        task = next(t for t in progress.tasks if t.id == task_id)
                        if "[red]" not in task.description and "✗" not in task.description:
                            progress.update(task_id, description=f"[red]✗ Error: {name}")
                        results.append(TaskResult(name=name, success=False, error=e, message=str(e)))
            except KeyboardInterrupt:
                executor.shutdown(wait=False, cancel_futures=True)
                for future, task_data in future_to_task.items():
                    if not future.done():
                        progress.update(task_data["task_id"], description="[yellow]⚠ Cancelled (Interrupted)")
                raise

    return results
