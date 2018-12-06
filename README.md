# litecli

[![Build Status](https://travis-ci.org/dbcli/litecli.svg?branch=master)](https://travis-ci.org/dbcli/litecli)

A command-line client for SQLite databases that has auto-completion and syntax highlighting.

![Completion](screenshots/litecli.png)
![CompletionGif](screenshots/litecli.gif)

## Installation

If you already know how to install python packages, then you can install it via pip:

You might need sudo on linux.

```
$ pip install -U litecli
```

For MacOS users, you can also use Homebrew to install it:

```
$ brew tap dbcli/tap
$ brew install litecli
```

## Usage

    $ litecli --help
    
    Usage: litecli [OPTIONS] [DATABASE]

    Examples:
      - litecli sqlite_db_name

A config file is automatically created at `~/.config/litecli/config` at first launch. See the file itself for a description of all available options.
