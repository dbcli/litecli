## Unreleased - TBD

### Features

### Bug Fixes


## 1.6.0 - 2021-03-15

### Features

- Add verbose feature to `favorite_query` command. (Thanks: [Zhaolong Zhu])
  - `\f query` does not show the full SQL.
  - `\f+ query` shows the full SQL.
- Add prompt format of file's basename. (Thanks: [elig0n])

### Bug Fixes

- Fix compatibility with sqlparse >= 0.4.0. (Thanks: [chocolateboy])
- Fix invalid utf-8 exception. (Thanks: [Amjith])

## 1.4.1 - 2020-07-27

### Bug Fixes

- Fix setup.py to set `long_description_content_type` as markdown.

## 1.4.0 - 2020-07-27

### Features

- Add NULLS FIRST and NULLS LAST to keywords. (Thanks: [Amjith])

## 1.3.2 - 2020-03-11

- Fix the completion engine to work with newer sqlparse.

## 1.3.1 - 2020-03-11

- Remove the version pinning of sqlparse package.

## 1.3.0 - 2020-02-11

### Features

- Added `.import` command for importing data from file into table. (Thanks: [Zhaolong Zhu])
- Upgraded to prompt-toolkit 3.x.

## 1.2.0 - 2019-10-26

### Features

- Enhance the `describe` command. (Thanks: [Amjith])
- Autocomplete table names for special commands. (Thanks: [Amjith])

## 1.1.0 - 2019-07-14

### Features

- Added `.read` command for reading scripts.
- Added `.load` command for loading extension libraries. (Thanks: [Zhiming Wang])
- Add support for using `?` as a placeholder in the favorite queries. (Thanks: [Amjith])
- Added shift-tab to select the previous entry in the completion menu. [Amjith]
- Added `describe` and `desc` keywords.

### Bug Fixes

- Clear error message when directory does not exist. (Thanks: [Irina Truong])

## 1.0.0 - 2019-01-04

- To new beginnings. :tada:

[Amjith]: https://blog.amjith.com
[chocolateboy]: https://github.com/chocolateboy
[Irina Truong]: https://github.com/j-bennet
[Shawn Chapla]: https://github.com/shwnchpl
[Zhaolong Zhu]: https://github.com/zzl0
[Zhiming Wang]: https://github.com/zmwangx
