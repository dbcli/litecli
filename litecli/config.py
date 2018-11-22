import errno
import shutil
import os
import platform
from os.path import expanduser, exists, dirname
from configobj import ConfigObj


def config_location():
    if "XDG_CONFIG_HOME" in os.environ:
        return "%s/litecli/" % expanduser(os.environ["XDG_CONFIG_HOME"])
    elif platform.system() == "Windows":
        return os.getenv("USERPROFILE") + "\\AppData\\Local\\dbcli\\litecli\\"
    else:
        return expanduser("~/.config/litecli/")


def load_config(usr_cfg, def_cfg=None):
    cfg = ConfigObj()
    cfg.merge(ConfigObj(def_cfg, interpolation=False))
    cfg.merge(ConfigObj(expanduser(usr_cfg), interpolation=False, encoding="utf-8"))
    cfg.filename = expanduser(usr_cfg)

    return cfg


def ensure_dir_exists(path):
    parent_dir = expanduser(dirname(path))
    try:
        os.makedirs(parent_dir)
    except OSError as exc:
        # ignore existing destination (py2 has no exist_ok arg to makedirs)
        if exc.errno != errno.EEXIST:
            raise


def write_default_config(source, destination, overwrite=False):
    destination = expanduser(destination)
    if not overwrite and exists(destination):
        return

    ensure_dir_exists(destination)

    shutil.copyfile(source, destination)


def upgrade_config(config, def_config):
    cfg = load_config(config, def_config)
    cfg.write()


def get_config(liteclirc_file=None):
    from litecli import __file__ as package_root

    package_root = os.path.dirname(package_root)

    liteclirc_file = liteclirc_file or "%sconfig" % config_location()

    default_config = os.path.join(package_root, "liteclirc")
    write_default_config(default_config, liteclirc_file)

    return load_config(liteclirc_file, default_config)
