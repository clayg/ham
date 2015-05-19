import os

from ham import project

PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..'))

ENV_NAME = os.path.basename(os.path.dirname(__file__))

ENV = project.Project(PROJECT_ROOT).environments[ENV_NAME]

from fabric import api as fab

fab.env.ham = ENV
fab.env.disable_known_hosts = True
fab.env.passwords = {'root@%s:22' % server.ip_address: server.admin_pass
                     for server in ENV.servers.values()}

fab.env.roledefs['all'] = []
for name, server in ENV.servers.items():
    host_str = 'root@%s' % server.ip_address
    fab.env.roledefs[name] = [host_str]
    fab.env.roledefs['all'].append(host_str)

from ham import fab_helpers

globals().update(fab_helpers.load_project_tasks(PROJECT_ROOT))
