"""
Launch (mostly trained) monkeys into the cloud.
"""
import argparse
import imp
import os
import sys

import ham

parser = argparse.ArgumentParser(description=__doc__.strip())
parser.add_argument('-p', '--project-dir', default=ham.project.PROJECT_ROOT,
                    help='the project config directory')

subparsers = parser.add_subparsers()


def _env_status(project, name):
    env = project.environments[name]
    env.refresh()
    for name, server in env.servers.items():
        print '%s: %s' % (name, server)


def _server_status(project, name, server_name):
    env = project.environments[name]
    server = env.servers[server_name]
    server.refresh()
    print 'ssh root@%s # %s' % (server.ip_address, server.admin_pass)


def project_status(project, name=None, server=None, **kwargs):
    if name is not None:
        if server is not None:
            return _server_status(project, name, server)
        return _env_status(project, name)
    for name, env in project.environments.items():
        print '%s: %s' % (name, env)


def project_create(project, name, **kwargs):
    env = project._create(name)
    print '%s: %s' % (name, env)


def project_build(project, name, **kwargs):
    project.environments[name].build()


def project_wait(project, name, **kwargs):
    project.environments[name].wait()


def project_fab(project, name, args, **kwargs):
    cmd = 'fab -f %s ' % project.environments[name].fabfile_path
    os.system(cmd + ' '.join(args))


def project_teardown(project, name, **kwargs):
    project.environments[name].teardown()


def project_delete(project, name, **kwargs):
    project.environments[name].delete()


def _add_per_build_args(subparser):
    subparser.add_argument('name', help='the name of the environment')


parser_status = subparsers.add_parser(
    'status', help='list all environments of the project')
parser_status.add_argument('name', nargs='?', default=None,
                           help='get info on an environment')
parser_status.add_argument('server', nargs='?', default=None,
                           help='get info on an server')
parser_status.set_defaults(func=project_status)

parser_create = subparsers.add_parser(
    'create', help='create a new environment')
_add_per_build_args(parser_create)
parser_create.set_defaults(func=project_create)

parser_build = subparsers.add_parser(
    'build', help='bring up the nodes in an environment')
_add_per_build_args(parser_build)
parser_build.set_defaults(func=project_build)

parser_wait = subparsers.add_parser(
    'wait', help='wait for an environment to finish builds')
_add_per_build_args(parser_wait)
parser_wait.set_defaults(func=project_wait)

parser_fab = subparsers.add_parser(
    'fab', help='fab command for environment')
_add_per_build_args(parser_fab)
parser_fab.set_defaults(func=project_fab)
parser_fab.add_argument('args', nargs=argparse.REMAINDER,
                        help='fab command line args')

parser_teardown = subparsers.add_parser(
    'teardown', help='terminate the existing instances')
_add_per_build_args(parser_teardown)
parser_teardown.set_defaults(func=project_teardown)

parser_delete = subparsers.add_parser(
    'delete', help='destroy the environment files')
_add_per_build_args(parser_delete)
parser_delete.set_defaults(func=project_delete)


def main():
    args = parser.parse_args()
    project_d = imp.load_source('ham.project_d', os.path.join(
        args.project_dir, 'project.py'))
    project = project_d.Project(args.project_dir)
    args.func(project=project, **vars(args))


if __name__ == "__main__":
    sys.exit(main())
