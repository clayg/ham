import imp
import os

from fabric import api as fab
_orig_task = fab.task


def load_project_tasks(project_root):
    registry = {}

    def _register_task(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            f = args[0]
            registry[f.__name__] = _orig_task(f)
            return

        def _register_task_with_options(f):
            registry[f.__name__] = _orig_task(*args, **kwargs)(f)
        return _register_task_with_options

    try:
        fab.task = _register_task
        imp.load_source('ham.project_d', os.path.join(
            project_root, 'project.py'))
    finally:
        fab.task = _orig_task

    return registry
