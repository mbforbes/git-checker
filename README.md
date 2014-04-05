# git-checker
Check to see if there are uncommitted or unpushed changes locally in any git repos.

This is useful if, like me, most of your code lives and is backed up on GitHub, and you want to make sure things are up-to-date and pushed in case of a hard drive failure.

## Running
By default, the checker checks under your home directory (`~`) and all subdirectories, then prints a report for you in the console.

### Console
```bash
python checker.py
```

### As a chron job
TODO this is how I want it to run

### Advanced: Check some other directory, print _and_ email result
```bash
python checker.py /Some/path/to/check --both
```


## Setup for email reports
You need to create two additional files before you can run with email repots enabled.

0. `recipient` : one line: the email address of who should receive the report
0. `sender` : two lines: (1) the username (2) the password of the gmail account for sending the report

Then, just run
```bash
python checker.py --email
```

## Help
To get a list of all command line options, just run with `-h` or `--help`.

```bash
python checker.py -h
```

## TODO
- add chron job instructions
