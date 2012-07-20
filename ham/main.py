import sys
import time
from optparse import OptionParser
from fabric.api import execute, task, env, run

from novaclient.shell import OpenStackComputeShell
from novaclient.client import Client


class ClientBuildError(Exception):
    pass


def get_clients():
    """
    Get compute and volume clients from novaclient using envrionment vars.

    STEAL THIS FUNCTION
    """
    shell = OpenStackComputeShell()
    parser = shell.get_base_parser()
    options, args = parser.parse_known_args()
    kwargs = dict(vars(options))
    del kwargs['help']
    shell.setup_debugging(kwargs.pop('debug'))
    # some options can show up under multiple names
    multi_name_keys = (
        ('os_username', 'username'),
        ('os_password', 'apikey'),
        ('os_tenant_name', 'projectid'),
        ('os_auth_url', 'url'),
        ('region_name', 'os_region_name'),
    )
    for k, alias in multi_name_keys:
        val = kwargs.pop(alias)
        if val and not kwargs[k]:
            kwargs[k] = val
    # required args
    required_args= (
        'os_compute_api_version',
        'os_username',
        'os_password',
        'os_tenant_name',
        'os_auth_url',
    )
    args = []
    for arg in required_args:
        val = kwargs.pop(arg)
        if not val:
            raise ClientBuildError('missing required env %s' % arg.upper())
        args.append(val)
    kwargs['service_type'] = 'compute'
    compute = Client(*args, **kwargs)
    kwargs['service_type'] = 'volume'
    volume = Client(*args, **kwargs)
    return compute, volume


def select_image(compute, image_id=None):
    images = compute.images.list()
    image_options = []
    for image in images:
        if image.id == image_id:
            return image
        if 'Ubuntu' in image.name:
            image_options.append(image)
    return sorted(image_options, key=lambda x: x.name)[-1]


@task
def hostname():
    run('hostname')


def on_server(server, task):
    env.host_string = 'root@%s' % server.accessIPv4
    env.passwords[env.host_string] = server.adminPass
    execute(task)


def main():
    try:
        compute, volume = get_clients()
    except ClientBuildError, e:
        return 'ERROR: %s' % e
    parser = OptionParser('%prog [options] <SCRIPT>')
    parser.add_option('-i', '--image', help='over-ride image')
    parser.add_option('-f', '--flavor', type='int', default=2,
                      help='over-ride flavor')
    parser.add_option('-H', '--hostname', default='monkey',
                      help='over-ride hostname')
    parser.add_option('-n', '--count', type='int', default=1,
                      help='number of servers to build')
    parser.add_option('-p', '--persist', action='store_true',
                     help='servers built are permanent')
    options, args = parser.parse_args()
    image = select_image(compute, options.image)
    flavor = compute.flavors.get(options.flavor)

    build_map = {}
    for i in range(options.count):
        name = options.hostname + '%0.2d' % (i + 1)
        server = compute.servers.create(name, image, flavor)
        build_map[server.id] = server
        print 'build', server

    active_map = {}
    try:
        timeout = time.time() + 300
        while time.time() < timeout:
            for server_id in build_map.keys():
                server = compute.servers.get(server_id)
                if server.status == 'ACTIVE':
                    build = build_map.pop(server_id)
                    server.adminPass = build.adminPass
                    active_map[server_id] = server
                print timeout - time.time(), server, 'status', server.status
            if not build_map:
                break
            time.sleep((timeout - time.time()) * 0.1)
        for server in build_map.values():
            return 'ERROR: %s took too long to boot' % server
        for server in active_map.values():
            print server, server.status
            on_server(server, hostname)
    finally:
        if options.persist:
            return
        for server_id in build_map:
            compute.servers.delete(server_id)
        for server_id in active_map:
            compute.servers.delete(server_id)

if __name__ == "__main__":
    sys.exit(main())
