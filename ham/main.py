import sys
import time
import os
from optparse import OptionParser
import traceback

from fabric.api import execute, task, env, run, put, get, parallel, settings

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
        val = kwargs.pop(alias, None)
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
    kwargs['no_cache'] = True
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


def parse_disks(disk_strings):
    """
    Extract disk options from input strings in the format:
        <size>[:volume_type][:snapshot_id]

    :param disk_strings: list of strings in the above format
    """
    disks = []
    for i, disk_string in enumerate(disk_strings):
        parts = disk_string.split(':')
        volume_type = snapshot_id = None
        size = parts.pop(0)
        try:
            volume_type = parts.pop(0)
        except IndexError:
            pass
        try:
            snapshot_id = parts.pop(0)
        except IndexError:
            pass
        disk = {
            'size': int(size),
            'volume_type': volume_type or None,
            'snapshot_id': snapshot_id or None,
            'mount_point': '/dev/vd%s' % chr(101 + i) # start at /dev/vde
        }
        disks.append(disk)
    return disks


def validate_disks(volume, disks):
    """
    Verify disk options

    :param volume: volume api connection
    :param disks: list of dicts describing disks
    """
    # validate disk types
    valid_types = volume.volume_types.list()
    valid_type_names = [str(vt.name) for vt in valid_types]
    for disk in disks:
        if not disk['volume_type']:
            continue
        if disk['volume_type'] not in valid_type_names:
            raise Exception('Volume type %s is not valid %r' %
                            (disk['volume_type'], valid_type_names))


def wait_on_status(status, manager, resource, timeout=300):
    timeout = time.time() + timeout
    while time.time() < timeout:
        resource = manager.get(resource.id)
        time_remaining = timeout - time.time()
        print time_remaining, resource, resource.status
        if resource.status == status:
            return resource
        if time_remaining > 0:
            time.sleep(time_remaining * 0.1)
    raise Exception('timeout waiting for %r to be %s' % (resource, status))


def build_servers(compute, image, flavor, hostname, count=1, timeout=300):
    """
    Wait for server(s) to build

    :param compute: compute api connection
    :param hostname: hostname for servers
    :param count: number of servers to build
    :param timeout: maximum time to wait for build to finish
    """
    # create servers in build queue
    build_map = {}
    for i in range(count):
        name = hostname + '%0.2d' % (i + 1)
        server = compute.servers.create(name, image, flavor)
        build_map[server.id] = server
        print server, server.status

    servers = []
    try:
        # wait for servers to build
        timeout = time.time() + timeout
        while time.time() < timeout:
            time_remaining = timeout - time.time()
            for server_id in build_map.keys():
                server = compute.servers.get(server_id)
                if server.status == 'ACTIVE':
                    # remove active servers from build queue
                    build = build_map.pop(server_id)
                    server.adminPass = build.adminPass
                    servers.append(server)
                print time_remaining, server, server.status
            # no more servers to build
            if not build_map:
                break
            # check more frequently closer to timeout
            if time_remaining > 0:
                time.sleep(time_remaining * 0.1)
        # alert on servers that did not finish building in time
        for server in build_map.values():
            print 'WARNING: %s took too long to boot' % server
        return servers
    finally:
        # always clean up timeout servers
        for server in build_map.values():
            server.delete()


def wait_on_status_all(status, manager, resources, timeout=300):
    wait_map = dict((r.id, r) for r in resources)
    resources = []
    timeout = time.time() + timeout
    while time.time() < timeout:
        time_remaining = timeout - time.time()
        for resource_id in wait_map.keys():
            resource = manager.get(resource_id)
            print time_remaining, resource, resource.status
            if resource.status == status:
                wait_map.pop(resource_id)
                resources.append(resource)
            else:
                wait_map[resource_id] = resource
        if not wait_map:
            return resources
        if time_remaining > 0:
            time.sleep(time_remaining * 0.1)
    raise Exception('timeout waiting for %r to be %s' % (
        wait_map.values(), status))


def build_volumes(compute, servers, volume, disk_params):
    volumes = []
    for server in servers:
        # each server gets a set of disks
        for param in disk_params:
            display_name = '.'.join([server.name, param['mount_point']])
            vol = volume.volumes.create(param['size'],
                                        display_name=display_name,
                                        volume_type=param['volume_type'])
            print vol, vol.status, vol.size, vol.display_name
            volumes.append(vol)
            # TODO: snapshots!
            vol = wait_on_status('available', volume.volumes, vol, timeout=10)
            # make attachments
            compute.volumes.create_server_volume(server.id, vol.id,
                                                 param['mount_point'])
            vol = wait_on_status('attaching', volume.volumes, vol, timeout=10)

    # wait on in-use
    volumes = wait_on_status_all('in-use', volume.volumes, volumes, timeout=60)
    return volumes


def clean_up(servers, volumes, **kwargs):
    # we can't just terminate because of xen/nova bug
    compute = kwargs.pop('compute')
    for volume in volumes:
        vol = volume.manager.get(volume.id)
        for attachment in vol.attachments:
            compute.volumes.delete_server_volume(
                attachment['server_id'], volume.id)
    wait_on_status_all('available', volume.manager, volumes, timeout=30)
    for server in servers:
        server.delete()
    for volume in volumes:
        volume.delete()


@task
@parallel
def _run_task(scriptname):
    """
    Execute scriptname on remote host(s) and save results locally
    """
    remotename = os.path.normpath(
        os.path.join('/root', os.path.basename(scriptname))
    )
    put(scriptname, remotename)
    run('chmod +x %s' % remotename)
    with settings(warn_only=True):
        result = run(remotename + ' 2>&1 | tee /root/out')
    if result.failed:
        ext = 'err'
    else:
        ext = 'out'
    remote_hostname = run('hostname').strip()
    get('/root/out', '.'.join([scriptname, remote_hostname, ext]))


def run_tasks(servers, scriptname):
    # env.abort_on_prompts = True
    env.user = 'root'
    for server in servers:
        host_string = 'root@%s' % server.accessIPv4
        env.hosts.append(host_string)
        env.passwords[host_string] = server.adminPass
    for host in env.hosts:
        print host, env.passwords[host]
    execute(_run_task, scriptname)


def main():
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
    parser.add_option('-d', '--disk', action='append',
                      help='add some disks to server')
    options, args = parser.parse_args()
    try:
        scriptname = args.pop(0)
    except IndexError:
        return 'ERROR: need to specify scriptname'

    # get services connections
    try:
        compute, volume = get_clients()
    except ClientBuildError, e:
        return 'ERROR: %s' % e

    # validation of api options
    image = select_image(compute, options.image)
    flavor = compute.flavors.get(options.flavor)
    disk_params = parse_disks(options.disk or [])
    try:
        validate_disks(volume, disk_params)
    except Exception, e:
        return 'ERROR: %s' % e

    servers = []
    volumes = []
    try:
        # build servers
        servers = build_servers(compute, image, flavor, options.hostname,
                                count=options.count)
        # create volumes
        volumes = build_volumes(compute, servers, volume, disk_params)
        # run tasks
        run_tasks(servers, scriptname)
    finally:
        # clean up
        if not options.persist:
            try:
                clean_up(servers, volumes, compute=compute)
            except Exception, e:
                print 'exception in clean up'
                traceback.print_exc()


if __name__ == "__main__":
    sys.exit(main())
