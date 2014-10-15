import collections
import ConfigParser
import errno
import os

from ham import cloud


def safe_listdir(path):
    try:
        dirs = os.listdir(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        dirs = []
    return dirs


class ProjectError(Exception):
    pass


def _write_config(section, options, path):
    try:
        os.makedirs(os.path.dirname(path))
    except EnvironmentError as e:
        if e.errno != errno.EEXIST:
            raise
    conf = ConfigParser.ConfigParser()
    conf.add_section(section)
    for k, v in options.items():
        conf.set(section, k, v)
    with open(path, 'w') as f:
        conf.write(f)


def _read_config(config_root):
    conf_files = []
    for root, dirs, files in os.walk(config_root):
        for filename in files:
            if not filename.endswith('.conf'):
                continue
            conf_files.append(os.path.join(root, filename))
    conf = ConfigParser.ConfigParser()
    conf.read(sorted(conf_files))
    return conf


class Server(object):

    options = {
        'image_id': ('boot', str),
        'flavor_id': ('boot', str),
        'server_id': ('instance', str),
        'admin_pass': ('instance', str),
        'status': ('cache', str),
    }

    def __init__(self, env, name):
        self.env = env
        self.name = name
        self.root = os.path.join(self.env.root_servers, self.name)
        self.root_config = os.path.join(self.root, 'conf.d')
        self.load()

    def load(self):
        conf = _read_config(self.root_config)
        conf_get = {
            str: conf.get,
            int: conf.getint,
            bool: conf.getboolean,
        }
        for name, (section, type_) in self.options.items():
            try:
                value = conf_get[type_](section, name)
            except ConfigParser.Error:
                value = type_()
            setattr(self, name, value)

    def _section_config_path(self, section):
        return os.path.join(self.root_config, '20_%s.conf' % section)

    def save(self):
        section_map = collections.defaultdict(dict)
        for name, (section, type_) in self.options.items():
            section_map[section][name] = getattr(self, name)
        for section, options in section_map.items():
            _write_config(section, options,
                          self._section_config_path(section))

    def is_active(self):
        return self.status == 'ACTIVE'

    def boot(self):
        if self.is_active():
            raise ProjectError('server is already running')
        server = self.env.cloud.boot(
            name=self.name,
            image_id=self.image_id,
            flavor_id=self.flavor_id,
        )
        self.admin_pass = server.adminPass
        self.status = server.status
        self.server_id = server.id
        self.save()


class Environment(object):

    def __init__(self, project, name):
        self.project = project
        self.name = name
        self.root = os.path.join(self.project.root_envs, self.name)
        self.root_servers = os.path.join(self.root, 'servers')
        self.load()
        self.cloud = cloud.Cloud()

    def _load_servers(self):
        self.servers = {}
        server_names = safe_listdir(self.root_servers)
        for name in server_names:
            self.servers[name] = Server(self, name)

    def load(self):
        self._load_servers()

    def save(self):
        for server in self.servers.values():
            server.save()

    def build(self):
        for server in self.servers.values():
            server.boot()

    def is_active(self):
        return all(server.is_active() for server in self.servers.values())

    def deploy(self):
        if not self._is_active():
            raise ProjectError('build is not running')
        pass


PROJECT_ROOT = os.environ.get('HAM_PROJECT_ROOT', 'ham.d')


class Project(object):

    def __init__(self, root=PROJECT_ROOT):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.root_envs = os.path.join(self.root, 'envs')
        self.load()

    def _load_environments(self):
        self.environments = {}
        env_names = safe_listdir(self.root_envs)
        for name in env_names:
            self.environments[name] = Environment(self, name)

    def load(self):
        self._load_environments()

    def create(self, name):
        env = Environment(self, name)
        options = {
            'image_id': 'e19a734c-c7e6-443a-830c-242209c4d65d',
            'flavor_id': '2',
        }
        for node_name in ('node1', 'node2'):
            server = Server(env, node_name)
            for opt, value in options.items():
                setattr(server, opt, value)
            server.save()
        return Environment(self, name)
