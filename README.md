# git-checker

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](blob/master/LICENSE.txt)

Your friendly neighborhood git repository checker. Finds dirty / unpushed
repositories and tells you.

```bash
$ python checker.py --check-dir ~/repos/
Finding all git directories at/below "/Users/max/repos"...
Checking status of all 119 directories...
100%|████████████████████████| 119/119 [00:01<00:00, 90.15it/s]
- Checked at and below "/Users/max/repos"
- Found 119 git repositories.

The following directories (4) have dirty WDs:
	 - /Users/max/repos/text-metrics/
	 - /Users/max/repos/cs231n/
	 - /Users/max/repos/cls-graphics-prj3/
	 - /Users/max/repos/git-checker/
```

Fuel your OCD to have all of your git repositories clean at the end of a day.

## Installation

```bash
# install in a fresh virtualenv with python3.6+
$ pip install -r requirements.txt
```

## Basic usage

By default, the checker checks under your home directory (`~`) and all
subdirectories, then prints a report for you in the console.

```bash
$ python checker.py
```

## Usage

```
$ python checker.py --help
usage: checker.py [-h] [--check-dir CHECK_DIR]
                  [--report-choice {print,email,both}]

Your friendly neighborhood git repository checker. Finds dirty / unpushed
repositories and tells you about them.

optional arguments:
  -h, --help            show this help message and exit
  --check-dir CHECK_DIR
                        directory to check recursively for git repositories
                        beneath (default: /Users/max)
  --report-choice {print,email,both}
                        Whether to print report to stdout, email a report, or
                        both (default: print)
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

## TODO

-  [ ] Add computer info to summary (useful if running on multiple computers).
-  [x] argparse
-  [ ] tests?
-  [ ] maybe pypi?
-  [ ] GIFs are cool right?

### speedup

-  home dir (`~/`): 46s
-  repos dir (`~/repos`): 11s
-  pruning (`-prune`): 10s
-  switching to `fd`: 0.136s <-- yep wow, let's use that
   `fd -t d '^\.git$' -H ~/repos/`
