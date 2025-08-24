# -*- coding: utf-8
from __future__ import annotations


import os


def list_path(root_dir: str) -> list[str]:
    """List directory if exists.

    :param dir: str
    :return: list

    """
    res: list[str] = []
    if os.path.isdir(root_dir):
        for name in os.listdir(root_dir):
            res.append(name)
    return res


def complete_path(curr_dir: str, last_dir: str) -> str | None:
    """Return the path to complete that matches the last entered component.

    If the last entered component is ~, expanded path would not
    match, so return all of the available paths.

    :param curr_dir: str
    :param last_dir: str
    :return: str

    """
    if not last_dir or curr_dir.startswith(last_dir):
        return curr_dir
    elif last_dir == "~":
        return os.path.join(last_dir, curr_dir)
    return None


def parse_path(root_dir: str) -> tuple[str, str, int]:
    """Split path into head and last component for the completer.

    Also return position where last component starts.

    :param root_dir: str path
    :return: tuple of (string, string, int)

    """
    base_dir, last_dir, position = "", "", 0
    if root_dir:
        base_dir, last_dir = os.path.split(root_dir)
        position = -len(last_dir) if last_dir else 0
    return base_dir, last_dir, position


def suggest_path(root_dir: str) -> list[str]:
    """List all files and subdirectories in a directory.

    If the directory is not specified, suggest root directory,
    user directory, current and parent directory.

    :param root_dir: string: directory to list
    :return: list

    """
    if not root_dir:
        return [str(x) for x in [os.path.abspath(os.sep), "~", os.curdir, os.pardir]]

    if "~" in root_dir:
        root_dir = str(os.path.expanduser(root_dir))

    if not os.path.exists(root_dir):
        root_dir, _ = os.path.split(root_dir)

    return list_path(root_dir)


def dir_path_exists(path: str) -> bool:
    """Check if the directory path exists for a given file.

    For example, for a file /home/user/.cache/litecli/log, check if
    /home/user/.cache/litecli exists.

    :param str path: The file path.
    :return: Whether or not the directory path exists.

    """
    return os.path.exists(os.path.dirname(path))
