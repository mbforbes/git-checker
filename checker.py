'''
Check git directories for uncommited files and unpushed commits.

Author: mbforbes
'''

#
# IMPORTS
#

# builtins
from email.mime.text import MIMEText
import os
from smtplib import SMTP_SSL as SMTP
import subprocess as sp
import sys


#
# CONSTANTS
#

CMDLINE_HELP = ['-h', '--help']
CMDLINE_REPORT = ['--email', '--print', '--both']

CLEAN_PHRASES = ['working directory clean']
AHEAD_PHRASES = ['branch is ahead of']

BLACKLIST_DIRS = ['venv']


#
# FUNCTIONS
#
def checker(checkdir='~', report='--print'):
    '''
    Check git directories for uncommited files and unpushed commits. Report
    status to user either via stdout or email.

    Args:
        checkdir (str, default '~') Root of directories to check
        preport (str, default '--print') Whether to print ('--print'), email
            ('--email'), or do both ('--both')
    '''
    # Save original path (gets messed up and unreachable after changing
    # directories a bunch and reading files, I guess...)
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # Write checked dir before expanding.
    msgstr = '- Checked at and below: ' + checkdir + '\n'
    check_dir = os.path.expanduser(checkdir)

    # Get the void.
    dn = open(os.devnull, 'w')

    # Check.
    p = sp.Popen([
        'find',          # command
        check_dir,       # directory to look in (default: home)
        '-name',         # search by name
        '.git'],         # the name we want
        stdout=sp.PIPE,  # catch output
        stderr=dn        # send errors to the void!
    )
    res, err = p.communicate()

    # close the void
    dn.close()

    # Filter out crap and peel off .git endings.
    allgitdirs = []
    for r in res.splitlines():
        if r.endswith('.git'):
            allgitdirs += [r.split('.git')[0]]

    # ignore blacklist dirs
    gitdirs = []
    for d in allgitdirs:
        # TODO: make OS-agnostic
        remove = False
        for piece in d.split('/')[:-1]:
            if piece in BLACKLIST_DIRS:
                remove = True
        if not remove:
            gitdirs.append(d)

    msgstr += '- Found ' + str(len(gitdirs)) + ' git repositories.\n'

    # Now run git status in each
    dirtydirs = []
    unpusheddirs = []
    for gd in gitdirs:
        os.chdir(gd)
        p = sp.Popen(['git', 'status'], stdout=sp.PIPE)
        res, ess = p.communicate()
        # Find what's important.
        lines = res.splitlines()
        if not check_clean(lines):
            # WD dirty
            dirtydirs += [gd]
        if check_unpushed(lines):
            # Changes unpushed
            unpusheddirs += [gd]

    # Get back to original script directory (for emailing).
    os.chdir(script_dir)

    # Make a space in the message body.
    msgstr += '\n'

    # Append any dirty directories.
    ndirtystr = str(len(dirtydirs))
    nunpushedstr = str(len(unpusheddirs))
    if len(dirtydirs) > 0:
        msgstr += 'The following ' + ndirtystr + ' directories have dirty ' + \
            'WDs:\n' + '\n'.join(['\t - ' + x for x in dirtydirs])
    if len(dirtydirs) > 0 and len(unpusheddirs) > 0:
        msgstr += '\n\n'
    if len(unpusheddirs) > 0:
        msgstr += 'The following ' + nunpushedstr + ' directories need to ' + \
            'be pushed:\n' + '\n'.join(['\t - ' + x for x in unpusheddirs])
    if len(dirtydirs) == 0 and len(unpusheddirs) == 0:
        # Alternate message if everything good (printed only).
        msgstr += 'All git repositories checked were clean.\n'

    # It's not useful unless you tell someone about it!
    if report == '--print' or report == '--both':
        # For a printed report, we spit out even if nothing dirty.
        print_report(msgstr)
    if (report == '--email' or report == '--both') and \
            (len(dirtydirs) > 0 or len(unpusheddirs) > 0):
        # For an email report, we only send if something's dirty or unpushed to
        # avoid spam.
        email_report(msgstr, ndirtystr, nunpushedstr)


def check_clean(status_lines):
    '''
    Returns whether a status string indicates that a working directory is
    clean.

    Args:
        status_lines ([str]) Output of `git status`
    '''
    last_line = status_lines[-1]
    for clean_end in CLEAN_PHRASES:
        if clean_end in last_line:
            return True
    return False


def check_unpushed(status_lines):
    '''
    Return whether a status string indicates that a working directory has
    commits ahead of a remote branch.

    Args:
        status_lines ([str]) Output of `git status`
    '''
    if len(status_lines) >= 2:
        for ahead_start in AHEAD_PHRASES:
            if ahead_start in status_lines[1]:
                return True
    return False


def print_report(msgstr):
    '''
    Print report to console.

    Args:
        msgstr (str) What to print
    '''
    print msgstr


def email_report(msgstr, ndirtystr, nunpushedstr):
    '''
    Send email report to address in the "recipient" file using the userame and
    password in the "sender" file.

    Args:
        msgstr (str) The report
        ndirtystr (str) The number of dirty directories, as a string
        nunpushedstr (str) The number of unpushed directories, as a string
    '''
    # Who to send report to.
    with open('recipient') as recipient:
        user_email = recipient.read().strip()

    # Account from which to send the email.
    with open('sender') as sender:
        sender_uname, sender_psswd = sender.read().strip().split('\n')

    # Convert format.
    msg = MIMEText(msgstr)

    # Set email fields.
    receiver = user_email
    msg['Subject'] = 'git-checker report: ' + ndirtystr + ' dirty, ' + \
        nunpushedstr + ' unpushed'
    msg['From'] = sender_uname
    msg['To'] = receiver

    # Login and send email.
    conn = SMTP('smtp.gmail.com')
    conn.login(sender_uname, sender_psswd)
    try:
        conn.sendmail(sender_uname, receiver, msg.as_string())
    finally:
        conn.close()


def usage():
    '''Tells you how to use this program.'''
    print 'git-checker : Your friendly neighborhood git repository checker.'
    print '              Finds dirty / unpushed repositories and tells you.'
    print
    print 'Usage: python checker.py [option] [report_option]'
    print
    print '[option] is one of:'
    print ', '.join(CMDLINE_HELP), '     Display this help message and exit.'
    print '</some/path>    Attempt to use the string as a path for checking.'
    print '                Whitespace sensitive (use quotes), defaults to ~.'
    print
    print '[report_option] is one of:'
    print '--print         Prints report to console (not printer). Default.'
    print '--email         Emails report using sender and recipient files.'
    print '--both          Print and email.'
    print


def main():
    '''Program entry starts here.'''
    checkdir = '~'
    report = '--print'

    # At least one option!
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        # Could be help
        if arg1 in CMDLINE_HELP:
            usage()
            exit(0)
        # Could be cmdline report option.
        elif arg1 in CMDLINE_REPORT:
            report = arg1
        # Otherwise, assume it's a path.
        else:
            checkdir = arg1

    # At least two options!
    if len(sys.argv) > 2:
        arg2 = sys.argv[2]
        # There's no reason this should be the path (or help), so check only
        # report.
        if arg2 in CMDLINE_REPORT:
            report = arg2

    # Actually do things!
    checker(checkdir, report)


# Entry point for command line usage.
if __name__ == '__main__':
    main()
