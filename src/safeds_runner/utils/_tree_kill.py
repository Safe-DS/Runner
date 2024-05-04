import psutil


def tree_kill(pid: int) -> None:
    """Kill the process and all its children."""
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        child.kill()
    parent.kill()
