from novaclient.shell import OpenStackComputeShell
from novaclient.auth_plugin import discover_auth_systems, load_plugin
from novaclient.client import Client
from novaclient import exceptions as exc


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
        if val and not kwargs.get(k):
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

    # setup auth systems
    os_auth_system = kwargs.pop('os_auth_system', None)
    kwargs['auth_system'] = os_auth_system
    if os_auth_system and os_auth_system != "keystone":
        # Discover available auth plugins
        discover_auth_systems()
        kwargs['auth_plugin'] = load_plugin(os_auth_system)

    # invalid args
    invalid_args = (
        'os_cacert',
        'os_user_id',
        'os_auth_token',
        'os_tenant_id',
    )
    for arg in invalid_args:
        kwargs.pop(arg, None)
    kwargs['no_cache'] = True

    kwargs['service_type'] = 'compute'
    compute = Client(*args, **kwargs)
    # XXX figure out what cinder is doing these days
    volume = None
    return compute, volume


class ServerNotFound(object):

    status = 'NOT_FOUND'


class Cloud(object):

    def __init__(self):
        self.compute, self.volume = get_clients()

    def boot(self, name, image_id, flavor_id, **options):
        return self.compute.servers.create(name, image_id, flavor_id,
                                           **options)

    def status(self, server_id):
        if not server_id:
            return ServerNotFound()
        try:
            return self.compute.servers.get(server_id)
        except exc.NotFound:
            return ServerNotFound()

    def delete(self, server_id):
        self.compute.servers.delete(server_id)
