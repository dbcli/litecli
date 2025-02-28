# Development Guide

This is a guide for developers who would like to contribute to this project. It is recommended to use Python 3.10 and above for development.

If you're interested in contributing to litecli, thank you. We'd love your help!
You'll always get credit for your work.

## GitHub Workflow

1. [Fork the repository](https://github.com/dbcli/litecli) on GitHub.

2. Clone your fork locally:
    ```bash
    $ git clone <url-for-your-fork>
    ```

3. Add the official repository (`upstream`) as a remote repository:
    ```bash
    $ git remote add upstream git@github.com:dbcli/litecli.git
    ```

4. Set up a [virtual environment](http://docs.python-guide.org/en/latest/dev/virtualenvs)
   for development:

    ```bash
    $ cd litecli
    $ python -m venv .venv
    ```

    We've just created a virtual environment that we'll use to install all the dependencies
    and tools we need to work on litecli. Whenever you want to work on litecli, you
    need to activate the virtual environment:

    ```bash
    $ source .venv/bin/activate
    ```

    When you're done working, you can deactivate the virtual environment:

    ```bash
    $ deactivate
    ```

5. Install the dependencies and development tools:

    ```bash
    $ pip install --editable ".[dev]"
    ```

6. Create a branch for your bugfix or feature based off the `main` branch:

    ```bash
    $ git checkout -b <name-of-bugfix-or-feature>
    ```

7. While you work on your bugfix or feature, be sure to pull the latest changes from `upstream`. This ensures that your local codebase is up-to-date:

    ```bash
    $ git pull upstream main
    ```

8. When your work is ready for the litecli team to review it, push your branch to your fork:

    ```bash
    $ git push origin <name-of-bugfix-or-feature>
    ```

9. [Create a pull request](https://help.github.com/articles/creating-a-pull-request-from-a-fork/) on GitHub.


## Running the Tests

While you work on litecli, it's important to run the tests to make sure your code
hasn't broken any existing functionality. To run the tests, just type in:

```bash
$ tox
```

### CLI Tests

Some CLI tests expect the program `ex` to be a symbolic link to `vim`.

In some systems (e.g. Arch Linux) `ex` is a symbolic link to `vi`, which will
change the output and therefore make some tests fail.

You can check this by running:
```bash
$ readlink -f $(which ex)
```


## Coding Style

Litecli uses [ruff](https://docs.astral.sh/ruff/) to format the source code.

To check the style and fix any violations, run:

```bash
$ tox -e style
```

Be sure to commit and push any stylistic fixes.
