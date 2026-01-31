# git-checker

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](blob/master/LICENSE.txt)

Your friendly neighborhood git repository checker. Finds dirty / unpushed
repositories and tells you.

Also checks your home directory for unwanted files (configurable).

```bash
$ python checker.py

Arguments:
git_check_dir: /Users/max [str]
report_choice: print [str]
no_check_git : False [bool]
no_check_home: False [bool]
config       : /Users/max/repos/git-checker/default.git-checker-config.json [str]
print_config : False [bool]

[git-checker]
Finding all git directories at/below "/Users/max"...
Checking status of all 80 directories...
- Checked at and below "/Users/max"
- Found 80 git repositories.

The following directories (1) have dirty WDs:
	 - /Users/max/repos/website-3/

[home-checker]
Home checker passed. Home directory clean!
```

Fuel your OCD to have all of your git repositories clean at the end of a day, and files you care about living in backed-up directories.

## Installation

```bash
# python python3.6+, or use uv etc.
$ pip install -r requirements.txt
```

## Basic usage

By default, the checker checks under your home directory (`~`) and all
subdirectories, then prints a report for you in the console.

```bash
$ python checker.py
```

## Usage

```txt
$ python checker.py --help
usage: checker.py [-h] [--git-check-dir GIT_CHECK_DIR] [--report-choice {print,email,both}] [--no-check-git]
                  [--no-check-home] [--config CONFIG] [--print-config]

Your friendly neighborhood git repository & home directory checker. (1) Finds dirty / unpushed repositories. (2)
Finds unwanted (or un-backed-up) files in your home directory.

options:
  -h, --help            show this help message and exit
  --git-check-dir GIT_CHECK_DIR
                        Directory beneath which to check recursively for git repositories (default: /Users/max)
  --report-choice {print,email,both}
                        Whether to print report to stdout, email a report, or both (default: print)
  --no-check-git        Don't run git repository check (default: False)
  --no-check-home       Don't run home directory cleanliness checker (default: False)
  --config CONFIG       path to config file (currently home checker config only) (default: /Users/max/repos/git-
                        checker/default.git-checker-config.json)
  --print-config        Print to stdout contents of config file used. (default: False)
```

## Email reports

You need to create two additional files before you can run with email reports
enabled. These live in the root of the repository.

0. `recipient` : one line: the email address of who should receive the report
1. `sender` : two lines: (1) the username (2) the password of the Gmail account
   for sending the report

Then, just run

```bash
$ python checker.py --report-choice email
```

## Advanced usage

### Cron job, emailed reports

The line below can be added to your
[crontabs](https://en.wikipedia.org/wiki/Cron) file to run the git checker daily
at 9pm (0 minutes, 21 hours), where it will look at and below a directory called
`~/repos/` and email you the result.

```
0 21 * * * python /Path/to/checker.py --check-dir ~/repos/ --report-choice email
```

## Tests

Warning: these tests are AI-written. Better than nothing (right? right???).

```sh
python tests.py
```

## TODO

-  [ ] Flag to add computer info to summary (useful if running on multiple computers)
-  [x] argparse
-  [x] tests
-  [ ] maybe pypi?
-  [ ] fall back to `find` and print nice message if `fd` not available


## Notes

`fd` speedup vs `find`:

-  home dir (`~/`): 46s
-  repos dir (`~/repos`): 11s
-  pruning (`-prune`): 10s
-  switching to `fd`: 0.136s <-- yep wow, let's use that
   `fd -t d '^\.git$' -H ~/repos/`
