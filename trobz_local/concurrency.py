from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn


@dataclass
class TaskResult:
    name: str
    success: bool
    message: str | None = None
    error: Exception | None = None


def run_tasks(tasks, max_workers: int = 4):
    results = []
    total = len(tasks)
    completed_count = 0

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=Console(stderr=True),
    ) as progress:
        overall = progress.add_task(f"[cyan]0/{total} done", total=total)

        future_to_task = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            try:
                # Submit tasks with hidden progress rows; reveal them on start
                for task_info in tasks:
                    name = task_info["name"]
                    func = task_info["func"]
                    kwargs = task_info.get("args", {})
                    task_id = progress.add_task(name, total=100, visible=False)

                    def _run(f=func, tid=task_id, kw=kwargs):
                        progress.update(tid, visible=True)
                        return f(progress, tid, **kw)

                    future = executor.submit(_run)
                    future_to_task[future] = {"name": name, "task_id": task_id}

                # Wait for all tasks to complete
                for future in as_completed(future_to_task):
                    task_data = future_to_task[future]
                    name = task_data["name"]
                    task_id = task_data["task_id"]

                    try:
                        future.result()
                        task = next(t for t in progress.tasks if t.id == task_id)
                        label = task.description or name
                        progress.update(task_id, completed=100, visible=False)
                        completed_count += 1
                        progress.update(
                            overall, completed=completed_count, description=f"[cyan]{completed_count}/{total} done"
                        )
                        progress.console.print(label)
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
