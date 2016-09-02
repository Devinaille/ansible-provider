
#
import os
import re
import warnings
import StringIO
import footmark

# from footmark.compat import expanduser, ConfigParser, NoOptionError, NoSectionError, StringIO
from ConfigParser import SafeConfigParser as ConfigParser
try:
    os.path.expanduser('~')
    expanduser = os.path.expanduser
except (AttributeError, ImportError):
    # This is probably running on App Engine.
    expanduser = (lambda x: x)
try:
    import simplejson as json
except ImportError:
    import json


# By default we use two locations for the footmark configurations,
# /etc/footmark.cfg and ~/.footmark (which works on Windows and Unix).
FootmarkConfigPath = '/etc/footmark.cfg'
FootmarkConfigLocations = [FootmarkConfigPath]
UserConfigPath = os.path.join(expanduser('~'), '.footmark')
FootmarkConfigLocations.append(UserConfigPath)

# If there's a BOTO_CONFIG variable set, we load ONLY
# that variable
if 'BOTO_CONFIG' in os.environ:
    FootmarkConfigLocations = [expanduser(os.environ['BOTO_CONFIG'])]

# If there's a BOTO_PATH variable set, we use anything there
# as the current configuration locations, split with os.pathsep.
elif 'BOTO_PATH' in os.environ:
    FootmarkConfigLocations = []
    for path in os.environ['BOTO_PATH'].split(os.pathsep):
        FootmarkConfigLocations.append(expanduser(path))


class Config(object):

    def __init__(self, path=None, fp=None, do_load=True):
        self._parser = ConfigParser({'working_dir': '/mnt/pyami',
                                     'debug': '0'})
        if do_load:
            if path:
                self.load_from_path(path)
            elif fp:
                self.readfp(fp)
            else:
                self.read(FootmarkConfigLocations)
            if "AWS_CREDENTIAL_FILE" in os.environ:
                full_path = expanduser(os.environ['AWS_CREDENTIAL_FILE'])
                try:
                    self.load_credential_file(full_path)
                except IOError:
                    warnings.warn('Unable to load AWS_CREDENTIAL_FILE (%s)' % full_path)

    def __setstate__(self, state):
        # There's test that verify that (transitively) a Config
        # object can be pickled.  Now that we're storing a _parser
        # attribute and relying on __getattr__ to proxy requests,
        # we need to implement setstate to ensure we don't get
        # into recursive loops when looking up _parser when
        # this object is unpickled.
        self._parser = state['_parser']

    def __getattr__(self, name):
        return getattr(self._parser, name)

    def has_option(self, *args, **kwargs):
        return self._parser.has_option(*args, **kwargs)

    def load_credential_file(self, path):
        """Load a credential file as is setup like the Java utilities"""
        c_data = StringIO()
        c_data.write("[Credentials]\n")
        for line in open(path, "r").readlines():
            c_data.write(line.replace("AWSAccessKeyId", "aws_access_key_id").replace("AWSSecretKey", "aws_secret_access_key"))
        c_data.seek(0)
        self.readfp(c_data)

    def load_from_path(self, path):
        file = open(path)
        for line in file.readlines():
            match = re.match("^#import[\s\t]*([^\s^\t]*)[\s\t]*$", line)
            if match:
                extended_file = match.group(1)
                (dir, file) = os.path.split(path)
                self.load_from_path(os.path.join(dir, extended_file))
        self.read(path)

    def save_option(self, path, section, option, value):
        """
        Write the specified Section.Option to the config file specified by path.
        Replace any previous value.  If the path doesn't exist, create it.
        Also add the option the the in-memory config.
        """
        config = ConfigParser()
        config.read(path)
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, option, value)
        fp = open(path, 'w')
        config.write(fp)
        fp.close()
        if not self.has_section(section):
            self.add_section(section)
        self.set(section, option, value)

    def save_user_option(self, section, option, value):
        self.save_option(UserConfigPath, section, option, value)

    def save_system_option(self, section, option, value):
        self.save_option(FootmarkConfigPath, section, option, value)

    # def get_instance(self, name, default=None):
    #     try:
    #         val = self.get('Instance', name)
    #     except (NoOptionError, NoSectionError):
    #         val = default
    #     return val
    #
    # def get_user(self, name, default=None):
    #     try:
    #         val = self.get('User', name)
    #     except (NoOptionError, NoSectionError):
    #         val = default
    #     return val
    #
    # def getint_user(self, name, default=0):
    #     try:
    #         val = self.getint('User', name)
    #     except (NoOptionError, NoSectionError):
    #         val = default
    #     return val
    #
    # def get_value(self, section, name, default=None):
    #     return self.get(section, name, default)
    #
    # def get(self, section, name, default=None):
    #     try:
    #         return self._parser.get(section, name)
    #     except (NoOptionError, NoSectionError):
    #         return default
    #
    # def getint(self, section, name, default=0):
    #     try:
    #         return self._parser.getint(section, name)
    #     except (NoOptionError, NoSectionError):
    #         return int(default)
    #
    # def getfloat(self, section, name, default=0.0):
    #     try:
    #         return self._parser.getfloat(section, name)
    #     except (NoOptionError, NoSectionError):
    #         return float(default)

    def getbool(self, section, name, default=False):
        if self.has_option(section, name):
            val = self.get(section, name)
            if val.lower() == 'true':
                val = True
            else:
                val = False
        else:
            val = default
        return val

    def setbool(self, section, name, value):
        if value:
            self.set(section, name, 'true')
        else:
            self.set(section, name, 'false')

    # def dump(self):
    #     s = StringIO()
    #     self.write(s)
    #     print(s.getvalue())
    #
    # def dump_safe(self, fp=None):
    #     if not fp:
    #         fp = StringIO()
    #     for section in self.sections():
    #         fp.write('[%s]\n' % section)
    #         for option in self.options(section):
    #             if option == 'aws_secret_access_key':
    #                 fp.write('%s = xxxxxxxxxxxxxxxxxx\n' % option)
    #             else:
    #                 fp.write('%s = %s\n' % (option, self.get(section, option)))
    #
    # def dump_to_sdb(self, domain_name, item_name):
    #     from footmark.compat import json
    #     sdb = footmark.connect_sdb()
    #     domain = sdb.lookup(domain_name)
    #     if not domain:
    #         domain = sdb.create_domain(domain_name)
    #     item = domain.new_item(item_name)
    #     item.active = False
    #     for section in self.sections():
    #         d = {}
    #         for option in self.options(section):
    #             d[option] = self.get(section, option)
    #         item[section] = json.dumps(d)
    #     item.save()
    #
    # def load_from_sdb(self, domain_name, item_name):
    #     from footmark.compat import json
    #     sdb = footmark.connect_sdb()
    #     domain = sdb.lookup(domain_name)
    #     item = domain.get_item(item_name)
    #     for section in item.keys():
    #         if not self.has_section(section):
    #             self.add_section(section)
    #         d = json.loads(item[section])
    #         for attr_name in d.keys():
    #             attr_value = d[attr_name]
    #             if attr_value is None:
    #                 attr_value = 'None'
    #             if isinstance(attr_value, bool):
    #                 self.setbool(section, attr_name, attr_value)
    #             else:
    #                 self.set(section, attr_name, attr_value)
