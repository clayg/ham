from ham import project

RACKSPACE_PRECISE_IMAGE = 'e19a734c-c7e6-443a-830c-242209c4d65d'
RACKSPACE_TINY_FLAVOR = '2'

import argparse

parser = argparse.ArgumentParser('ham create [name]')
parser.add_argument('--image-id', default=RACKSPACE_PRECISE_IMAGE,
                    help='image id of example1 vm')


class Project(project.Project):

    def create(self, env, extra_args):
        options = parser.parse_args(extra_args)
        node_name = 'example1'
        options = {
            'image_id': options.image_id,
            'flavor_id': RACKSPACE_TINY_FLAVOR,
        }
        env.create_server(node_name, **options)


from fabric import api as fab


@fab.task
@fab.roles('all')
def check():
    fab.run('hostname')


@fab.task
def roles():
    for role, hosts in fab.env.roledefs.items():
        print(role)
        for host in hosts:
            print('  {0}'.format(host))
