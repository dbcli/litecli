# litecli

[![GitHub Actions](https://github.com/dbcli/litecli/actions/workflows/ci.yml/badge.svg)](https://github.com/dbcli/litecli/actions/workflows/ci.yml "GitHub Actions")

[Docs](https://litecli.com)

A command-line client for SQLite databases that has auto-completion and syntax highlighting.

![Completion](https://raw.githubusercontent.com/dbcli/litecli/refs/heads/main/screenshots/litecli.png)
![CompletionGif](https://raw.githubusercontent.com/dbcli/litecli/refs/heads/main/screenshots/litecli.gif)

## Installation

If you already know how to install python packages, then you can install it via pip:

You might need sudo on linux.

```
$ pip install -U litecli[sqlean]
```

For MacOS users, you can also use Homebrew to install it:

```
$ brew install litecli
```

## Usage

```
$ litecli --help

Usage: litecli [OPTIONS] [DATABASE]

Examples:
  - litecli sqlite_db_name
```

A config file is automatically created at `~/.config/litecli/config` at first launch. For Windows machines a config file is created at `~\AppData\Local\dbcli\litecli\config` at first launch. See the file itself for a description of all available options.

## Docs

Visit: [litecli.com/features](https://litecli.com/features)
