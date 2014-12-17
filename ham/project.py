import sys
import collections
import ConfigParser
import errno
import os
import shutil
import time

from ham import cloud, exc

PROJECT_ROOT = os.environ.get('HAM_PROJECT_ROOT', 'ham.d')

TEMPLATES = os.path.join(os.path.dirname(__file__), 'templates')


def safe_listdir(path):
    try:
        dirs = os.listdir(path)
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        dirs = []
    return dirs


def safe_read(path):
    try:
        with open(path) as f:
            body = f.read()
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
        body = ''
    return body


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
        'disk_config': ('boot', str),
        'server_id': ('instance', str),
        'admin_pass': ('instance', str),
        'ip_address': ('instance', str),
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
            raise exc.ProjectError('server is already running')
        server = self.env.cloud.boot(
            name=self.name,
            image_id=self.image_id,
            flavor_id=self.flavor_id,
        )
        self.admin_pass = server.adminPass
        self.status = server.status
        self.server_id = server.id
        self.save()

    def refresh(self):
        server = self.env.cloud.status(self.server_id)
        self.ip_address = getattr(server, 'accessIPv4', '')
        self.status = server.status
        self.save()

    def delete(self):
        self.env.cloud.delete(self.server_id)

    def __str__(self):
        return '   %-20s %-10s %s' % (self.name, self.status, self.server_id)


class Environment(object):

    def __init__(self, project, name):
        self.project = project
        self.name = name
        self.root = os.path.join(self.project.root_envs, self.name)
        self.root_servers = os.path.join(self.root, 'servers')
        self.fabfile_path = os.path.join(self.root, 'fabfile.py')
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
            if server.is_active():
                continue
            server.boot()

    def refresh(self):
        for server in self.servers.values():
            server.refresh()

    def wait(self):
        unfinished = set(self.servers.keys())
        while unfinished:
            for name, server in self.servers.items():
                if name not in unfinished:
                    continue
                server.refresh()
                if server.is_active():
                    unfinished.remove(name)
                sys.stderr.write('.')
                time.sleep(5)

    def teardown(self):
        for server in self.servers.values():
            server.delete()

    def delete(self):
        self.refresh()
        if self.is_active():
            raise exc.ProjectError('environment is still active')
        shutil.rmtree(self.root)

    def is_active(self):
        return all(server.is_active() for server in self.servers.values())

    def deploy(self):
        if not self.is_active():
            raise exc.ProjectError('environment is not active')

    def create_server(self, name, **options):
        server = Server(self, name)
        for opt, value in options.items():
            setattr(server, opt, value)
        server.save()

    def create_fabfile(self):
        try:
            os.makedirs(self.root)
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
        with open(self.fabfile_path, 'w') as f:
            f.write(open(os.path.join(TEMPLATES, 'fabfile.py')).read())

    @property
    def status(self):
        if self.is_active():
            return 'ACTIVE'
        else:
            return 'NOT_ACTIVE'

    def __str__(self):
        if self.name == self.project.workon_environment:
            workon_status = '*'
        else:
            workon_status = ' '
        return ' %s %-20s %-10s' % (workon_status, self.name, self.status)


class Project(object):

    def __init__(self, root=PROJECT_ROOT):
        self.root = os.path.abspath(os.path.expanduser(root))
        self.root_envs = os.path.join(self.root, 'envs')
        self.workonfile_path = os.path.join(self.root_envs, '.workon')
        self.projectfile_path = os.path.join(self.root, 'project.py')
        self.workon_environment = ''
        if os.path.exists(self.root):
            # on init we can't load yet
            self.load()

    def _load_environments(self):
        self.environments = {}
        env_names = safe_listdir(self.root_envs)
        for name in env_names:
            if name.startswith('.'):
                continue
            self.environments[name] = Environment(self, name)

    def get_environment(self, name):
        key = name or self.workon_environment
        if not key:
            raise exc.ProjectLookupError('no environment specified!')
        try:
            return self.environments[key]
        except KeyError:
            raise exc.ProjectLookupError('unknown environment %r' % key)

    def workon(self, name):
        try:
            os.makedirs(self.root_envs)
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
        with open(self.workonfile_path, 'w') as f:
            f.write(name)

    def load(self):
        self._load_environments()
        workon = safe_read(self.workonfile_path).strip()
        if workon not in self.environments:
            workon = ''
            self.workon(workon)
        self.workon_environment = workon

    def init(self):
        try:
            os.makedirs(self.root)
        except EnvironmentError as e:
            if e.errno != errno.EEXIST:
                raise
            raise exc.ProjectError('project in %r already exists!' % self.root)
        with open(self.projectfile_path, 'w') as f:
            f.write(open(os.path.join(TEMPLATES, 'project.py')).read())

    def _create(self, name, extra_args):
        if name.startswith('.'):
            raise exc.ProjectError("Environment names can't start with a .")
        env = Environment(self, name)
        self.create(env, extra_args)
        env = Environment(self, name)
        if not env.servers:
            raise exc.ProjectError(
                "Environment did not create any servers!")
        env.create_fabfile()
        return env

    def create(self, env, extra_args):
        raise NotImplementedError()
