## 1.19.0 - 2026-01-30

### Features

- Make LLM support optional and installable via `litecli[ai]`.

### Bug Fixes

- Avoid completion refresh crashes when no database is connected.

### Internal

- Clean up ty type-checking for optional sqlean/llm imports.

## 1.18.0

### Internal

- Switch mypy to ty for type checking. [(#242)](https://github.com/dbcli/litecli/pull/242/files)
- Add sqlean-stubs for type checking. [(#243)(https://github.com/dbcli/litecli/pull/243/files)]

## 1.17.0 - 2025-09-28

### Features

* Add support for opening 'file:' URIs with parameters. [(#234)](https://github.com/dbcli/litecli/pull/234)

### Bug Fixes

* Avoid Click 8.1.* to prevent messing up the pager when the PAGER env var has a string with spaces.

### Internal

- Add type checking using mypy.

## 1.16.0 - 2025-08-16

### Features

* Use [sqlean](https://antonz.org/sqlean/) when available. It's a drop-in replacement for sqlite3.
* Add support for `.output` to write the results to a file.
* The 'llm' library is now a default dependency not installed on demand.
* The `\llm` command now has three modes. Succinct, Regular and Verbose.

  Succinct = `\llm-` - This will return just the sql query. No explanation.
  Regular = `\llm` - This will return just the sql query and the explanation.
  Verbose = `\llm+` - This will print the prompt sent to the LLM and the sql query and the explanation.

### Bug Fixes

* Fix missing sqlite extensions using sqlean. Note. support only limited set of extensions. [(#119)](https://github.com/dbcli/litecli/issues/119)


## 1.15.0 - 2025-03-15

### Features
* Add logs while invoking `\llm`and `\\m+` command. [(#215)](https://github.com/dbcli/litecli/pull/215)
* Support `--help` in the `\llm`and `\llm+` command. ([#214](https://github.com/dbcli/litecli/pull/214))
* Make the history file location configurable. ([#206](https://github.com/dbcli/litecli/issues/206))
* Add dot command to list views.

### Bug Fixes

* Fix a bug where the `\llm` command on alternate invocations weren't detected correctly. (#211)
* Do not escape upper table or column name. [(#185)](https://github.com/dbcli/litecli/issues/185)
* Return indices when `.schema` command is run. Also update the output to contain the `sql` for the `indexes` command. [(#149)](https://github.com/dbcli/litecli/issues/149)

### Internal

* Fix typo `pormpt`to `prompt` in `special/llm.py`.
* Update pip install to work in both bash and zsh.


## 1.14.4 - 2025-01-31

### Bug Fixes

* Fix the usage instructions in the `\llm` command.

## 1.14.3 - 2025-01-29

### Bug Fixes

* Fix [misleading "0 rows affected" status for CTEs](https://github.com/dbcli/litecli/issues/203)
  by never displaying rows affected when the connector tells us -1
* Show an error message when `\llm "question"` is invoked without a database connection.

## 1.14.2 - 2025-01-26

### Bug Fixes

* Catch errors surfaced by `llm` cli and surface them as runtime errors.

## 1.14.1 - 2025-01-25

### Bug Fixes

* Capture stderr in addition to stdout when capturing output from `llm` cli.

## 1.14.0 - 2025-01-22

### Features

* Add LLM feature to ask an LLM to create a SQL query.
    - This adds a new `\llm` special command
    - eg: `\llm "Who is the largest customer based on revenue?"`

### Bug Fixes

* Fix the [windows path](https://github.com/dbcli/litecli/issues/187) shown in prompt to remove escaping.
* Fix a bug where if column name was same as table name it was [crashing](https://github.com/dbcli/litecli/issues/155) the autocompletion.

### Internal

* Change min required python version to 3.9+

## 1.13.2 - 2024-11-24

### Internal

* Read the version from the git tag using setuptools-scm

## 1.13.0 - 2024-11-23

### Features

* Add `\pipe_once` / `\|` commands for sending output to a command

## 1.12.4 - 2024-11-11

### Bug Fixes

* Fix the syntax error when `\d tbl` is used.

## 1.12.3  - 2024-09-10

### Bug Fixes

* Specify build system in `pyproject.toml`
* Don't install tests

## 1.12.2  - 2024-09-07

### Bug Fixes

* Fix the missing packages due to invalid pyproject.toml config

## 1.12.1  - 2024-09-07 (Yanked)

### Internal Changes

* Modernize the project with following changes:
  * pyproject.toml instead of setup.py
  * Use ruff for linting and formatting
  * Update GH actions to use uv and tox
  * Use GH actions to release a new version

## 1.11.1 - 2024-07-04

### Bug Fixes

* Fix the escape sequence warning.

## 1.11.0 - 2024-05-03

### Improvements

* When an empty `\d` is invoked the list of tables are returned instead of an error.
* Show SQLite version at startup.

### Bug Fixes

* Support a single item in the startup commands in the config. (bug #176)

## 1.10.1 - 2024-3-23

### Bug Fixes

* Do not crash at start up if ~/.config/litecli is not writeable. [#172](https://github.com/dbcli/litecli/issues/172)

## 1.10.0 - 2022-11-19

### Features

* Adding support for startup commands being set in liteclirc and executed on startup. Limited to commands already implemented in litecli. ([[#56](https://github.com/dbcli/litecli/issues/56)])

### Bug Fixes

* Fix [[#146](https://github.com/dbcli/litecli/issues/146)], making sure `.once`
  can be used more than once in a session.
* Fixed setting `successful = True` only when query is executed without exceptions so
  failing queries get `successful = False` in `query_history`.
* Changed `master` to `main` in CONTRIBUTING.md to reflect GitHubs new default branch
  naming.
* Fixed `.once -o <file>` by opening the output file once per statement instead
  of for every line of output ([#148](https://github.com/dbcli/litecli/issues/148)).
* Use the sqlite3 API to cancel a running query on interrupt
  ([#164](https://github.com/dbcli/litecli/issues/164)).
* Skip internal indexes in the .schema output
  ([#170](https://github.com/dbcli/litecli/issues/170)).

## 1.9.0 - 2022-06-06

### Features

* Add support for ANSI escape sequences for coloring the prompt.
* Add support for `.indexes` command.
* Add an option to turn off the auto-completion menu. Completion menu can be
  triggered by pressed the `<tab>` key when this option is set to False. Fixes
  [#105](https://github.com/dbcli/litecli/issues/105).

### Bug Fixes

* Fix [#120](https://github.com/dbcli/litecli/issues/120). Make the `.read` command actually read and execute the commands from a file.
* Fix  [#96](https://github.com/dbcli/litecli/issues/96) the crash in VI mode when pressing `r`.

## 1.8.0 - 2022-03-29

### Features

* Update compatible Python versions. (Thanks: [blazewicz])
* Add support for Python 3.10. (Thanks: [blazewicz])
* Drop support for Python 3.6. (Thanks: [blazewicz])

### Bug Fixes

* Upgrade cli_helpers to workaround Pygments regression.
* Use get_terminal_size from shutil instead of click.

## 1.7.0 - 2022-01-11

### Features

* Add config option show_bottom_toolbar.

### Bug Fixes

* Pin pygments version to prevent breaking change.

## 1.6.0 - 2021-03-15

### Features

* Add verbose feature to `favorite_query` command. (Thanks: [Zhaolong Zhu])
  * `\f query` does not show the full SQL.
  * `\f+ query` shows the full SQL.
* Add prompt format of file's basename. (Thanks: [elig0n])

### Bug Fixes

* Fix compatibility with sqlparse >= 0.4.0. (Thanks: [chocolateboy])
* Fix invalid utf-8 exception. (Thanks: [Amjith])

## 1.4.1 - 2020-07-27

### Bug Fixes

* Fix setup.py to set `long_description_content_type` as markdown.

## 1.4.0 - 2020-07-27

### Features

* Add NULLS FIRST and NULLS LAST to keywords. (Thanks: [Amjith])

## 1.3.2 - 2020-03-11

* Fix the completion engine to work with newer sqlparse.

## 1.3.1 - 2020-03-11

* Remove the version pinning of sqlparse package.

## 1.3.0 - 2020-02-11

### Features

* Added `.import` command for importing data from file into table. (Thanks: [Zhaolong Zhu])
* Upgraded to prompt-toolkit 3.x.

## 1.2.0 - 2019-10-26

### Features

* Enhance the `describe` command. (Thanks: [Amjith])
* Autocomplete table names for special commands. (Thanks: [Amjith])

## 1.1.0 - 2019-07-14

### Features

* Added `.read` command for reading scripts.
* Added `.load` command for loading extension libraries. (Thanks: [Zhiming Wang])
* Add support for using `?` as a placeholder in the favorite queries. (Thanks: [Amjith])
* Added shift-tab to select the previous entry in the completion menu. [Amjith]
* Added `describe` and `desc` keywords.

### Bug Fixes

* Clear error message when directory does not exist. (Thanks: [Irina Truong])

## 1.0.0 - 2019-01-04

* To new beginnings. :tada:

[Amjith]: https://blog.amjith.com
[chocolateboy]: https://github.com/chocolateboy
[Irina Truong]: https://github.com/j-bennet
[Zhaolong Zhu]: https://github.com/zzl0
[Zhiming Wang]: https://github.com/zmwangx
