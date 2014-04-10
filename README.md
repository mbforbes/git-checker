# git-checker
Check to see if there are uncommitted or unpushed changes locally in any git repos.

```bash
$ python checker.py
- Checked at and below: ~
- Found 23 git repositories.

The following 2 directories have dirty WDs:
	 - /Users/max/repos/py_git-checker/
	 - /Users/max/repos/py_beautyplot/

The following 1 directories need to be pushed:
	 - /Users/max/repos/py_git-checker/
$ 
```

This is useful if, like me, most of your code lives and is backed up on GitHub, and you want to make sure things are up-to-date and pushed in case of a hard drive failure.

## Basic usage
By default, the checker checks under your home directory (`~`) and all subdirectories, then prints a report for you in the console.

```bash
$ python checker.py
```

## Setup email reports
You need to create two additional files before you can run with email reports enabled.

0. `recipient` : one line: the email address of who should receive the report
0. `sender` : two lines: (1) the username (2) the password of the Gmail account for sending the report

Then, just run
```bash
$ python checker.py --email
```

## Advanced usage
### Cron job, emailed reports
_The examples below run the git checker daily at 9pm (0 minutes, 21 hours), look at and below your home directory (`~`), and email you the result._

If you already have a crontabs file, add this line to it:  
`0 21 * * * python </Path/to/checker.py> --email`

If you don't, run the following command in this repo (the same directory as `checker.py`), and it will set up a `crontab.txt` file in `~/crontab.txt`.
```bash
$ echo 0 21 '* * *' python `pwd`/checker.py --email > ~/crontab.txt; crontab ~/crontab.txt
```

### Check specified directory tree, print _and_ email result
```bash
$ python checker.py /Path/to/check/below --both
```

## Help
To get a list of all command line options, just run with `-h` or `--help`.

```bash
$ python checker.py -h
```

## Feature Ideas
* Add computer info to summary, if running on multiple computers.