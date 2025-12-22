from __future__ import annotations

import errno
import os
import platform
import shutil
from os.path import dirname, exists, expanduser

from configobj import ConfigObj


def config_location() -> str:
    if "XDG_CONFIG_HOME" in os.environ:
        return "%s/litecli/" % expanduser(os.environ["XDG_CONFIG_HOME"])
    elif platform.system() == "Windows":
        userprofile = os.getenv("USERPROFILE", "")
        return userprofile + "\\AppData\\Local\\dbcli\\litecli\\"
    else:
        return expanduser("~/.config/litecli/")


def load_config(usr_cfg: str, def_cfg: str | None = None) -> ConfigObj:
    cfg = ConfigObj()
    if def_cfg:
        cfg.merge(ConfigObj(def_cfg, interpolation=False))
    cfg.merge(ConfigObj(expanduser(usr_cfg), interpolation=False, encoding="utf-8"))
    cfg.filename = expanduser(usr_cfg)
    return cfg


def ensure_dir_exists(path: str) -> None:
    parent_dir = expanduser(dirname(path))
    try:
        os.makedirs(parent_dir)
    except OSError as exc:
        # ignore existing destination (py2 has no exist_ok arg to makedirs)
        if exc.errno != errno.EEXIST:
            raise


def write_default_config(source: str, destination: str, overwrite: bool = False) -> None:
    destination = expanduser(destination)
    if not overwrite and exists(destination):
        return
    ensure_dir_exists(destination)
    shutil.copyfile(source, destination)


def upgrade_config(config: str, def_config: str) -> None:
    cfg = load_config(config, def_config)
    cfg.write()


def get_config(liteclirc_file: str | None = None) -> ConfigObj:
    from litecli import __file__ as package_root

    package_root = os.path.dirname(str(package_root))

    liteclirc_file = liteclirc_file or f"{config_location()}config"

    default_config = os.path.join(package_root, "liteclirc")
    try:
        write_default_config(default_config, liteclirc_file)
    except OSError:
        # If we can't write to the config file, just use the default config
        return load_config(default_config)

    return load_config(liteclirc_file, default_config)
