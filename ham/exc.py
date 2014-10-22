class ProjectError(Exception):
    pass


class ProjectLookupError(ProjectError, LookupError):
    pass
