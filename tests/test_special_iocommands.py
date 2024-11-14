import os
import tempfile

import pytest

import litecli.packages.special


def test_once_command():
    with pytest.raises(TypeError):
        litecli.packages.special.execute(None, ".once")

    with pytest.raises(OSError):
        litecli.packages.special.execute(None, ".once /proc/access-denied")

    litecli.packages.special.write_once("hello world")  # write without file set
    # keep Windows from locking the file with delete=False
    with tempfile.NamedTemporaryFile(delete=False) as f:
        litecli.packages.special.execute(None, ".once " + f.name)
        litecli.packages.special.write_once("hello world")
        if os.name == "nt":
            assert f.read() == b"hello world\r\n"
        else:
            assert f.read() == b"hello world\n"

        litecli.packages.special.execute(None, ".once -o " + f.name)
        litecli.packages.special.write_once("hello world line 1")
        litecli.packages.special.write_once("hello world line 2")
        f.seek(0)
        if os.name == "nt":
            assert f.read() == b"hello world line 1\r\nhello world line 2\r\n"
        else:
            assert f.read() == b"hello world line 1\nhello world line 2\n"
    # delete=False means we should try to clean up
    try:
        if os.path.exists(f.name):
            os.remove(f.name)
    except Exception as e:
        print(f"An error occurred while attempting to delete the file: {e}")


def test_pipe_once_command():
    with pytest.raises(IOError):
        litecli.packages.special.execute(None, "\\pipe_once")

    with pytest.raises(OSError):
        litecli.packages.special.execute(None, "\\pipe_once /proc/access-denied")

    if os.name == "nt":
        litecli.packages.special.execute(None, '\\pipe_once python -c "import sys; print(len(sys.stdin.read().strip()))"')
        litecli.packages.special.write_pipe_once("hello world")
        litecli.packages.special.unset_pipe_once_if_written()
    else:
        with tempfile.NamedTemporaryFile() as f:
            litecli.packages.special.execute(None, "\\pipe_once tee " + f.name)
            litecli.packages.special.write_pipe_once("hello world")
            litecli.packages.special.unset_pipe_once_if_written()
            f.seek(0)
            assert f.read() == b"hello world\n"
