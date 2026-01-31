"""
Checks
- git directories for uncommited files and unpushed commits.
- home directory for unwanted (e.g., un-backed-up) files

author: mbforbes
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from enum import Enum, auto
import json
import glob
import os
import sys

from smtplib import SMTP_SSL as SMTP
import subprocess as sp
from typing import Any, Optional, Sequence

from mbforbes_python_utils import read, display_args
from pydantic import BaseModel


class ConfigMeta(BaseModel):
    comment: str


class Config(BaseModel):
    home_nolook: list[str]
    home_look: dict[str, list[str]]
    verbose: bool


class ConfigFile(BaseModel):
    """Schema for configuration file (default: default.git-checker-config.json)"""

    meta: ConfigMeta
    config: Config


class ReportOption(Enum):
    """options of what we can do internally"""

    PRINT = auto()
    EMAIL = auto()


REPORT_TRANSLATION = {
    "print": {ReportOption.PRINT},
    "email": {ReportOption.EMAIL},
    "both": {ReportOption.PRINT, ReportOption.EMAIL},
}
"""map from externally-specified actions to set of things to do internally"""


class GitStatus(BaseModel):
    dirty: bool
    unpushed_branches: list[str]


# Thanks to Brant Faircloth (https://gist.github.com/brantfaircloth/1443543)
# for some of these nice argparse utils.


def full_path(raw_path: str) -> str:
    """Returns the full path of raw_path, expanding user- and relative-paths."""
    return os.path.abspath(os.path.expanduser(raw_path))


class FullPath(argparse.Action):
    """Expand user- and relative-paths"""

    def __call__(
        self,
        _parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Optional[str | Sequence[Any]],
        _option_string: Optional[str] = None,
    ):
        if not isinstance(values, str):
            print(f"ERROR in FullPath: {values} ({type(values)}) is not a str")
            return
        setattr(namespace, self.dest, full_path(values))


def ensure_dir(path: str) -> str:
    """Ensures a path is a directory; returns the path unmodified on success.

    Raises ArgumentTypeError if the validation fails.
    """
    if not os.path.isdir(full_path(path)):
        raise argparse.ArgumentTypeError("{0} is not a directory".format(path))
    return path


def home_checker(config: Config) -> tuple[str, int, int]:
    """The home part of the checking. Returns (home_report, n_top, n_below)."""
    report: list[str] = []
    cleanup_list: list[str] = []
    n_top = 0
    n_below = 0

    # check top level
    tops = glob.glob(full_path("~/*"))
    ok_tops = set(config.home_nolook + list(config.home_look.keys()))
    for top in tops:
        short_top = os.path.basename(top)
        if short_top not in ok_tops:
            report.append('- ~/ has unwanted top-level contents "{}"'.format(top))
            cleanup_list.append(top)
            n_top += 1

    # for ones where we want to look, make sure they're empty
    for dirname, allowed in config.home_look.items():
        contents = glob.glob(full_path(os.path.join("~", dirname, "*")))
        for c in contents:
            short_c = os.path.basename(c)
            if short_c not in allowed:
                report.append(
                    '- ~/{} has unwanted contents "{}"'.format(dirname, short_c)
                )
                cleanup_list.append(c)
                n_below += 1

    # prepend home checker report summary
    clean = len(report) == 0
    report.insert(0, "[home-checker]")
    if clean:
        report.append("Home checker passed. Home directory clean!")
    else:
        report.insert(1, "Home checker found {} problems:".format(len(report)))

    # Deprecated: auto-cleanup. Nowadays I never want this. I want to look at the files.
    # if not clean and prompt:
    #     print("\n".join(report))
    #     report = []
    #     print("I can automatically remove the following files:")
    #     for c in cleanup_list:
    #         print(" - {}".format(c))
    #     choice = input("Would you like me to do this? (y/n) ")
    #     if choice.lower() == "y":
    #         for c in cleanup_list:
    #             if os.path.isfile(c):
    #                 report.append('- Removing file "{}"'.format(c))
    #                 os.remove(c)
    #             elif os.path.isdir(c):
    #                 report.append('- Removing directory "{}"'.format(c))
    #                 shutil.rmtree(c)
    #             else:
    #                 report.append(
    #                     '- WARNING: Could not remove unknown file type of "{}"'.format(
    #                         c
    #                     )
    #                 )
    #         report.append(
    #             "Home auto-cleaner finished. Fix any warnings and re-run to confirm."
    #         )

    return "\n".join(report), n_top, n_below


def is_dirty_fresh(gd: str) -> tuple[bool, bool]:
    """
    returns whether git directory `gd` (is dirty, has no commits)
    """
    p = sp.Popen(["git", "status"], stdout=sp.PIPE, universal_newlines=True, cwd=gd)
    res, _ = p.communicate()
    lines = res.splitlines()
    return not status_clean(lines), status_no_commits(lines)


def get_unpushed_branches(gd: str) -> list[str]:
    """
    Returns list of `gd`'s unpushed branches. "master"/"main" listed as `gd` itself
    """
    # Retrieve all branches with a configured remote
    branches_with_remote = ["git", "config", "--get-regexp", "^branch\\..*\\.remote$"]
    p = sp.Popen(branches_with_remote, stdout=sp.PIPE, universal_newlines=True, cwd=gd)
    stdout, _ = p.communicate()
    branches_with_remotes = [
        (r.split(".")[1], r.split(" ")[1]) for r in stdout.splitlines()
    ]

    # Check each branch with a remote which is not pushed
    res: list[str] = []
    for branch, remote in branches_with_remotes:
        # Check which commits are on branch, but not on remote/branch
        query = f"{remote}/{branch}..{branch}"
        p = sp.Popen(
            ["git", "log", query], stdout=sp.PIPE, universal_newlines=True, cwd=gd
        )
        stdout, _ = p.communicate()
        # Find what's important.
        if stdout != "":
            # Changes unpushed
            if branch in ["master", "main"]:
                res.append(gd)
            else:
                res.append(f"{gd}, branch {branch}")
    return res


def exclude_path_from_git(
    path: str, ignore_list: set[str] = {"venv", ".cargo", ".pyenv"}
) -> bool:
    """Returns whether path should be excluded because any part of it appears in
    the ignore_list.
    """
    for piece in os.path.normpath(path).split(os.sep):
        if piece in ignore_list:
            return True
    return False


def status_clean(status: list[str]) -> bool:
    """
    Returns whether a status string indicates that a working directory is clean.

    Args:
        status: Output of `git status`
    """
    last_line = status[-1]
    for clean_end in {
        "working directory clean",
        "working tree clean",
        "nothing to commit",
    }:
        if clean_end in last_line:
            return True
    return False


def status_no_commits(status: list[str]) -> bool:
    """
    Returns whether a status string indicates that a working directory has no commits.

    Args:
        status: Output of `git status`
    """
    return len(status) >= 3 and status[2] == "No commits yet"


def check_git_dir(git_dir: str) -> GitStatus:
    """Does GitChecking on git_dir"""
    dirty, no_commits = is_dirty_fresh(git_dir)
    unpushed_branches = [] if no_commits else get_unpushed_branches(git_dir)
    return GitStatus(dirty=dirty, unpushed_branches=unpushed_branches)


def git_checker(
    check_dir: str, report_choices: set[ReportOption]
) -> tuple[str, int, int]:
    """The git part of the checking. Returns (git_report, n_dirty, n_unpushed)."""
    # Save original path (gets messed up and unreachable after changing
    # directories a bunch and reading files, I guess...)
    # NOTE: I guess not?? Never used.
    # script_dir = os.path.dirname(os.path.realpath(__file__))

    # Write checked dir before expanding.
    report = '- Checked at and below "{}"\n'.format(check_dir)

    # Get the void.
    dn = open(os.devnull, "w")

    # Check.
    if ReportOption.PRINT in report_choices:
        print(
            '[git-checker]\nFinding all git directories at/below "{}"...'.format(
                check_dir
            )
        )
    p = sp.Popen(
        ["fd", "-t", "d", "^\\.git$", "-H", check_dir],
        stdout=sp.PIPE,  # catch output
        stderr=sp.PIPE,
        universal_newlines=True,  # so we get a str out instead of bytes
    )
    # todo: fall back to find if fd not installed. note the'll end with git not git/
    # p = sp.Popen(
    #     [
    #         "find",  # command
    #         check_dir,  # directory to look in (default: home)
    #         "-name",  # search by name
    #         ".git",
    #         "-type",  # specify type
    #         "d",
    #     ],  # the name we want
    #     stdout=sp.PIPE,  # catch output
    #     stderr=dn,  # send errors to the void!
    #     universal_newlines=True,  # so we get a str out instead of bytes
    # )
    stdout, _stderr = p.communicate()

    # close the void
    dn.close()

    # Filter out crap and peel off .git endings.
    all_git_dirs = [
        ".git".join(r.split(".git")[:-1])
        for r in stdout.splitlines()
        if r.endswith(".git/")
    ]
    git_dirs = [d for d in all_git_dirs if not exclude_path_from_git(d)]
    report += "- Found {} git {}.\n".format(
        len(git_dirs), ("repository" if len(git_dirs) == 1 else "repositories")
    )

    if ReportOption.PRINT in report_choices:
        print("Checking status of all {} directories...".format(len(git_dirs)))

    # Check for dirty working directories and unpushed branches.
    dirty_dirs: list[str] = []
    unpushed_branches: list[str] = []
    with ThreadPoolExecutor() as executor:
        for i, status in enumerate(executor.map(check_git_dir, git_dirs)):
            if status.dirty:
                dirty_dirs.append(git_dirs[i])
            unpushed_branches.extend(status.unpushed_branches)

    # Alphabetize for nice reporting.
    dirty_dirs.sort()
    unpushed_branches.sort()

    # Make a space in the message body.
    report += "\n"

    # Append any dirty directories.
    if len(dirty_dirs) > 0:
        report += "The following directories ({}) have dirty WDs:\n{}".format(
            len(dirty_dirs), reportify(dirty_dirs)
        )
    if len(dirty_dirs) > 0 and len(unpushed_branches) > 0:
        report += "\n\n"
    if len(unpushed_branches) > 0:
        report += (
            "The following directories (+branches) ({}) need to be pushed:\n{}".format(
                len(unpushed_branches), reportify(unpushed_branches)
            )
        )
    if len(dirty_dirs) == 0 and len(unpushed_branches) == 0:
        # Alternate message if everything good (printed only).
        report += "All git repositories checked were clean.\n"

    return report, len(dirty_dirs), len(unpushed_branches)


def checker(
    git_check_dir: str,
    report_choices: set[ReportOption],
    check_git: bool,
    check_home: bool,
    config: Config,
) -> int:
    """Top-level git & home checker. Maybe prints/emails report, returns status code.

    Configure with:
    - `report_choices`: email, print to stdout, both, neither.
    - `check_git`: Check git directories for uncommited files and unpushed branches
        under `git_check_dir`.
    - `check_home`: Check home & subdirectories for unwanted files. Configured with
      `config`.

    Returns status bit flag:
        - 0 = clean
        - 4 = dirty git
        - 8 = unwanted files
        - 12 = both
    """
    report = ""

    git_flag = 0
    if check_git:
        git_report, n_dirty, n_unpushed = git_checker(git_check_dir, report_choices)
        git_flag = 4 if n_dirty > 0 or n_unpushed > 0 else 0

        # NOTE: Currently the email report is git-only. May be useful to extend based on
        # home_checker returning a value also.
        if ReportOption.EMAIL in report_choices and (n_dirty > 0 or n_unpushed > 0):
            # For an email report, we only send if something's dirty or unpushed to
            # avoid spam.
            email_report(git_report, n_dirty, n_unpushed)

        report += git_report

    home_flag = 0
    if check_home:
        home_report, n_top, n_below = home_checker(config)
        home_flag = 8 if n_top > 0 or n_below > 0 else 0
        report += "\n" + home_report

    if ReportOption.PRINT in report_choices:
        print(report)

    return git_flag | home_flag


def reportify(paths: list[str]) -> str:
    """Makes a nice string for a list of paths."""
    return "\n".join(["\t - {}".format(p) for p in paths]) + "\n"


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
    with open("recipient") as recipient:
        user_email = recipient.read().strip()

    # Account from which to send the email.
    with open("sender") as sender:
        sender_uname, sender_psswd = sender.read().strip().split("\n")

    # Convert format.
    msg = MIMEText(report)

    # Set email fields.
    receiver = user_email
    msg["Subject"] = "git-checker report: {} dirty, {} unpushed".format(
        n_dirty, n_unpushed
    )
    msg["From"] = sender_uname
    msg["To"] = receiver

    # Login and send email.
    conn = SMTP("smtp.gmail.com")
    conn.login(sender_uname, sender_psswd)
    try:
        conn.sendmail(sender_uname, receiver, msg.as_string())
    finally:
        conn.close()


def main() -> int:
    """Returns status bit flag: 0 = clean, 4 = dirty git, 8 = extra files, 12 = both"""
    parser = argparse.ArgumentParser(
        description=(
            "Your friendly neighborhood git repository & home directory checker. "
            "(1) Finds dirty / unpushed repositories. "
            "(2) Finds unwanted (or un-backed-up) files in your home directory."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--git-check-dir",
        action=FullPath,
        type=ensure_dir,
        default=full_path("~"),
        help="Directory beneath which to check recursively for git repositories",
    )
    parser.add_argument(
        "--report-choice",
        type=str,
        default="print",
        choices=REPORT_TRANSLATION.keys(),
        help="Whether to print report to stdout, email a report, or both",
    )
    parser.add_argument(
        "--no-check-git",
        action="store_true",
        help="Don't run git repository check",
    )
    parser.add_argument(
        "--no-check-home",
        action="store_true",
        help="Don't run home directory cleanliness checker",
    )
    parser.add_argument(
        "--config",
        action=FullPath,
        type=str,
        default=full_path(
            os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "default.git-checker-config.json",
            )
        ),
        help="path to config file (currently home checker config only)",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Print to stdout contents of config file used.",
    )
    args = parser.parse_args()
    display_args(args)

    config = ConfigFile.model_validate_json(read(args.config))
    if args.print_config:
        print("Configuration:")
        print(json.dumps(config.model_dump(), indent=3))
        print()

    check_git = not args.no_check_git
    check_home = not args.no_check_home

    return checker(
        args.git_check_dir,
        REPORT_TRANSLATION[args.report_choice],
        check_git,
        check_home,
        config.config,
    )


if __name__ == "__main__":
    sys.exit(main())
