"""
Checks git directories for uncommited files and unpushed commits.

author: mbforbes
"""

#
# imports
#

# builtins
import argparse
import code
from email.mime.text import MIMEText
from enum import Enum, auto
import os
from smtplib import SMTP_SSL as SMTP
import subprocess as sp
import sys
from typing import List, Set

# 3rd party
from tqdm import tqdm

#
# constants and utils
#

# options of what we can do internally
class ReportOption(Enum):
    PRINT = auto()
    EMAIL = auto()

# map from externally-specified actions to set of things to do internally
REPORT_TRANSLATION = {
    'print': {ReportOption.PRINT},
    'email': {ReportOption.EMAIL},
    'both': {ReportOption.PRINT, ReportOption.EMAIL},
}

# cmd line defaults
DEFAULT_CHECK_DIR = '~'
DEFAULT_REPORT_CHOICE = 'print'

# how we actually check --- look for output strings! Lol.
CLEAN_PHRASES = {'working directory clean', 'working tree clean'}
AHEAD_PHRASES = {'branch is ahead of'}

# dirs to never check
BLACKLIST_DIRS = {'venv'}


# Thanks to Brant Faircloth (https://gist.github.com/brantfaircloth/1443543)
# for some of these nice argparse utils.

def full_path(raw_path: str) -> str:
    """Returns the full path of raw_path, expanding user- and relative-paths."""
    return os.path.abspath(os.path.expanduser(raw_path))


class FullPath(argparse.Action):
    """Expand user- and relative-paths"""
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, full_path(values))


def ensure_dir(path: str) -> str:
    """Ensures a path is a directory; returns the path unmodified on success.

    Raises ArgumentTypeError if the validation fails.
    """
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError('{0} is not a directory'.format(path))
    return path


#
# functions
#

def checker(check_dir: str, report_choices: Set[ReportOption]) -> None:
    """
    Check git directories for uncommited files and unpushed commits. Report
    status to user either via stdout or email.

    Args:
        check_dir: Root of directories to check
        report_choices: What types of reporting to do
    """
    # Save original path (gets messed up and unreachable after changing
    # directories a bunch and reading files, I guess...)
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Write checked dir before expanding.
    report = '- Checked at and below "{}"\n'.format(check_dir)

    # Get the void.
    dn = open(os.devnull, 'w')

    # Check.
    if ReportOption.PRINT in report_choices:
        print('Finding all git directories at/below "{}"...'.format(check_dir))
    p = sp.Popen([
        'find',          # command
        check_dir,       # directory to look in (default: home)
        '-name',         # search by name
        '.git'],         # the name we want
        stdout=sp.PIPE,  # catch output
        stderr=dn,       # send errors to the void!
        universal_newlines=True  # so we get a str out instead of bytes
    )
    res, err = p.communicate()

    # close the void
    dn.close()

    # Filter out crap and peel off .git endings.
    all_git_dirs = [r.split('.git')[0] for r in res.splitlines() if r.endswith('git')]
    git_dirs = [d for d in all_git_dirs if not exclude(d)]
    report += '- Found {} git {}.\n'.format(
        len(git_dirs), ('repository' if len(git_dirs) == 1 else 'repositories'))

    # Use progress bar only if printing
    itr = git_dirs
    if ReportOption.PRINT in report_choices:
        print('Checking status of all {} directories...'.format(len(git_dirs)))
        itr = tqdm(git_dirs)

    # Now run git status in each
    dirty_dirs: List[str] = []
    unpushed_dirs: List[str] = []
    for gd in itr:
        os.chdir(gd)
        p = sp.Popen(['git', 'status'], stdout=sp.PIPE, universal_newlines=True)
        res, ess = p.communicate()
        # Find what's important.
        lines = res.splitlines()
        if not check_clean(lines):
            # WD dirty
            dirty_dirs += [gd]
        if check_unpushed(lines):
            # Changes unpushed
            unpushed_dirs += [gd]

    # Get back to original script directory (for emailing).
    os.chdir(script_dir)

    # Make a space in the message body.
    report += '\n'

    # Append any dirty directories.
    if len(dirty_dirs) > 0:
        report += 'The following directories ({}) have dirty WDs:\n{}'.format(
            len(dirty_dirs), reportify(dirty_dirs))
    if len(dirty_dirs) > 0 and len(unpushed_dirs) > 0:
        report += '\n\n'
    if len(unpushed_dirs) > 0:
        report += 'The following directories ({}) need to be pushed:\n{}'.format(
            len(unpushed_dirs), reportify(unpushed_dirs))
    if len(dirty_dirs) == 0 and len(unpushed_dirs) == 0:
        # Alternate message if everything good (printed only).
        report += 'All git repositories checked were clean.\n'

    # It's not useful unless you tell someone about it!
    if ReportOption.PRINT in report_choices:
        # For a printed report, we spit out even if nothing dirty.
        print(report)
    if ReportOption.EMAIL in report_choices and (
            len(dirty_dirs) > 0 or len(unpushed_dirs) > 0):
        # For an email report, we only send if something's dirty or unpushed to
        # avoid spam.
        email_report(report, len(dirty_dirs), len(unpushed_dirs))


def exclude(path: str, blacklist: Set[str] = BLACKLIST_DIRS) -> bool:
    """Returns whether path should be excluded because any part of it apepars in
    the blacklist.
    """
    for piece in os.path.normpath(path).split(os.sep):
        if piece in blacklist:
            return True
    return False


def reportify(paths: List[str]) -> str:
    """Makes a nice string for a list of paths."""
    return '\n'.join(['\t - {}'.format(p) for p in paths])


def check_clean(status: List[str]) -> bool:
    """
    Returns whether a status string indicates that a working directory is clean.

    Args:
        status: Output of `git status`
    """
    last_line = status[-1]
    for clean_end in CLEAN_PHRASES:
        if clean_end in last_line:
            return True
    return False


def check_unpushed(status: List[str]) -> bool:
    """
    Return whether a status string indicates that a working directory has
    commits ahead of a remote branch.

    Args:
        status: Output of `git status`
    """
    if len(status) >= 2:
        for ahead_start in AHEAD_PHRASES:
            if ahead_start in status[1]:
                return True
    return False


def email_report(report: str, n_dirty: int, n_unpushed: int) -> None:
    """
    Send email report to address in the "recipient" file using the userame and
    password in the "sender" file.

    Args:
        report (str) The report
        n_dirty (int) The number of dirty directories
        n_unpushed (int) The number of unpushed directories
    """
    # Who to send report to.
    with open('recipient') as recipient:
        user_email = recipient.read().strip()

    # Account from which to send the email.
    with open('sender') as sender:
        sender_uname, sender_psswd = sender.read().strip().split('\n')

    # Convert format.
    msg = MIMEText(report)

    # Set email fields.
    receiver = user_email
    msg['Subject'] = 'git-checker report: {} dirty, {} unpushed'.format(
        n_dirty, n_unpushed)
    msg['From'] = sender_uname
    msg['To'] = receiver

    # Login and send email.
    conn = SMTP('smtp.gmail.com')
    conn.login(sender_uname, sender_psswd)
    try:
        conn.sendmail(sender_uname, receiver, msg.as_string())
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=('Your friendly neighborhood git repository checker. '
            'Finds dirty / unpushed repositories and tells you about them.'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--check-dir',
        action=FullPath,
        type=ensure_dir,
        default=full_path(DEFAULT_CHECK_DIR),
        help='directory to check recursively for git repositories beneath')
    parser.add_argument(
        '--report-choice',
        type=str,
        default=DEFAULT_REPORT_CHOICE,
        choices=REPORT_TRANSLATION.keys(),
        help='Whether to print report to stdout, email a report, or both')
    args = parser.parse_args()

    checker(args.check_dir, REPORT_TRANSLATION[args.report_choice])


if __name__ == '__main__':
    main()
