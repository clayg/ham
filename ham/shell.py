"""
Launch (mostly trained) monkeys into the cloud.
"""
from __future__ import print_function
import argparse
import imp
import os
import sys

import functools

err = functools.partial(print, file=sys.stderr)


import ham

parser = argparse.ArgumentParser(description=__doc__.strip())
parser.add_argument('-p', '--project-dir', default=ham.project.PROJECT_ROOT,
                    help='the project config directory')

subparsers = parser.add_subparsers()


def _add_per_environment_args(subparser):
    subparser.add_argument('name', nargs='?', default=None,
                           help='the name of the environment')

# list


def project_list(project, **kwargs):
    found_one = False
    for name in sorted(project.environments):
        print(project.get_environment(name))
        found_one = True
    if not found_one:
        err('no environments created!')

parser_list = subparsers.add_parser(
    'list', help='list all environments of the project')
parser_list.set_defaults(func=project_list)

# status


def _env_status(project, name):
    env = project.get_environment(name)
    env.refresh()
    for server in env.servers.values():
        print(server)


def _server_status(project, name, server_name):
    env = project.get_environment(name)
    server = env.servers[server_name]
    server.refresh()
    print('ssh root@%s # %s' % (server.ip_address, server.admin_pass))


def project_status(project, name=None, server=None, **kwargs):
    key = name or project.workon_environment
    if not key:
        err('WARNING: not working on any environment!')
        return project_list(project)
    if server is not None:
        return _server_status(project, name, server)
    return _env_status(project, name)

parser_status = subparsers.add_parser(
    'status', help='status of environment')
_add_per_environment_args(parser_status)
parser_status.add_argument('server', nargs='?', default=None,
                           help='get info on an server')
parser_status.set_defaults(func=project_status)

# init


def project_init(project_dir):
    ham.project.Project(project_dir).init()

parser_init = subparsers.add_parser(
    'init', help='create a new ham project')
parser_init.set_defaults(func=project_init)

# create


def project_create(project, name, args, **kwargs):
    env = project._create(name, args)
    print(env)

parser_create = subparsers.add_parser(
    'create', help='create a new environment')
_add_per_environment_args(parser_create)
parser_create.set_defaults(func=project_create)
parser_create.add_argument('args', nargs=argparse.REMAINDER,
                           help='extra args for create')

# build


def project_build(project, name, **kwargs):
    project.get_environment(name).build()

parser_build = subparsers.add_parser(
    'build', help='bring up the nodes in an environment')
_add_per_environment_args(parser_build)
parser_build.set_defaults(func=project_build)

# workon


def project_workon(project, name, **kwargs):
    name = name or ''
    project.workon(name)

parser_workon = subparsers.add_parser(
    'workon', help='select a environment for subsequent commands')
_add_per_environment_args(parser_workon)
parser_workon.set_defaults(func=project_workon)

# wait


def project_wait(project, name, **kwargs):
    try:
        project.get_environment(name).wait()
    except KeyboardInterrupt:
        err('... not done')
    else:
        err('FINISHED!')

parser_wait = subparsers.add_parser(
    'wait', help='wait for an environment to finish builds')
_add_per_environment_args(parser_wait)
parser_wait.set_defaults(func=project_wait)

# fab


def project_fab(project, name, args, **kwargs):
    env = project.get_environment(name)
    cmd = 'fab -f %s ' % env.fabfile_path
    os.system(cmd + ' '.join(args))

parser_fab = subparsers.add_parser(
    'fab', help='fab command for environment')
_add_per_environment_args(parser_fab)
parser_fab.add_argument('args', nargs=argparse.REMAINDER,
                        metavar='...',
                        help='fab command line args')
parser_fab.set_defaults(func=project_fab)

# teardown


def project_teardown(project, name, **kwargs):
    project.get_environment(name).teardown()

parser_teardown = subparsers.add_parser(
    'teardown', help='terminate the existing instances')
_add_per_environment_args(parser_teardown)
parser_teardown.set_defaults(func=project_teardown)

# delete


def project_delete(project, name, **kwargs):
    project.get_environment(name).delete()

parser_delete = subparsers.add_parser(
    'delete', help='destroy the environment files')
_add_per_environment_args(parser_delete)
parser_delete.set_defaults(func=project_delete)


def main(raw_args=sys.argv[1:]):
    args, unknown_args = parser.parse_known_args(raw_args)
    if args.func == project_fab and unknown_args:
        raw_args.insert(sys.argv.index(unknown_args[0]) - 1, '--')
    args = parser.parse_args(raw_args)
    if args.func == project_init:
        project_init(args.project_dir)
        return
    project_d = imp.load_source('ham.project_d', os.path.join(
        args.project_dir, 'project.py'))
    project = project_d.Project(args.project_dir)
    if args.func == project_fab and args.name and (
            args.name not in project.environments):
        # we're going to assume this was ment for fab rather than a typo
        args.args.insert(0, args.name)
        args.name = None
    try:
        return args.func(project=project, **vars(args))
    except ham.exc.ProjectLookupError as e:
        return 'ERROR: %s' % e


if __name__ == "__main__":
    sys.exit(main())
