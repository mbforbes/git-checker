# git-checker
Check to see if there are uncommitted (+unpushed?) changes locally in any git repos under your home directory (`~`).

## Setup
You need to create two additional files before you can run with email repots enabled.

0. `recipient` : one line---the email address---of who should receive the report
0. `sender` : two lines---the username, then password---of the gmail account for sending the report

## Running

### Locally
```bash
python checker.py
```

### As a chron job
TODO this is how I want it to run
