'''
Check git directories for uncommited files and unpushed commits. Then
send an email report to the user.

See the following for python email code:
http://docs.python.org/2/library/email-examples.html
'''

__author__ = 'mbforbes'


#
# IMPORTS
#

# builtins
import subprocess as sp
import os
import smtplib
import sys
from email.mime.text import MIMEText
from smtplib import SMTP_SSL as SMTP

#
# CONSTANTS
#
CMDLINE_HELP = ['-h', '--h']
CMDLINE_REPORT = ['--email', '--print', '--both']
#
# CLASSES
#

#
# FUNCTIONS
#

        
def main(checkdir='~', report='--both'):
    '''Check git directories for uncommited files and unpushed commits. Then
    send an email report to the user.'''
    # Settings.
    check_dir = os.path.expanduser(checkdir)
    print 'Checking', check_dir, '...'

    # Get the void.
    dn = open(os.devnull, 'w')

    # Check.
    p = sp.Popen(['find', # command
        check_dir, # directory to look in (home)
        '-name', # search by name
        '.git'], # the name we want
        stdout=sp.PIPE, # catch output
    #    stderr=dn # send errors to the void!
        ) 
    res, err = p.communicate()

    # close the void
    dn.close()

    # Filter out crap and peel off .git endings.
    gitdirs = []
    for r in res.splitlines():
        if r.endswith('.git'):
            gitdirs += [r.split('.git')[0]]

    # Now run git status in each
    dirtydirs = []
    unpusheddirs = []
    for gd in gitdirs:
        os.chdir(gd)
        p = sp.Popen(['git', 'status'], stdout=sp.PIPE)
        res, ess = p.communicate()
        # Find what's important.
        lines = res.splitlines()
        if not lines[-1].endswith('working directory clean'):
            # WD dirty
            dirtydirs += [gd]
        if len(lines) >= 2 and lines[1].startswith('# Your branch is ahead'):
            # Changes unpushed
            unpusheddirs += [gd]

    # If nothing to report, then done!
    if len(dirtydirs) == 0 and len(unpusheddirs) == 0:
        return

    # Create the msg body (empty at first)
    msgstr = ''

    # append any dirty directories
    if len(dirtydirs) > 0:
        msgstr += 'The following directories have dirty WDs:\n' + \
            '\n'.join(['\t - ' + x for x in dirtydirs])
    if len(dirtydirs) > 0 and len(unpusheddirs) > 0:
        msgstr += '\n'
    if len(unpusheddirs) > 0:
        msgstr += 'The following directories need to be pushed:\n' + \
        '\n'.join(['\t - ' + x for x in unpusheddirs])

    # It's not useful unless you tell someone about it!
    if report == '--print' or report == '--both':
        print_report(msgstr)
    if report == '--email' or report == '--both':
        email_report(msgstr)

def print_report(msgstr):
    '''Print report to console.'''
    print msgstr

def email_report(msgstr):
    '''Send email report.'''
    # Who to send report to.
    with open('recipient') as recipient:
        user_email = recipient.read().strip()

    # Account with which to send the email from
    with open('sender') as sender:
        sender_uname, sender_psswd = sender.read().strip().split('\n')

    # Convert format.
    msg = MIMEText(msgstr)

    # Set email fields.
    receiver = user_email
    msg['Subject'] = 'git-checker report'
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
    '''Tell how to use this program.'''
    print 'git-checker : Your friendly neighborhood git repository checker.'
    print '              Finds dirty / unpushed repositories and tells you.'
    print
    print 'Usage: python checker.py [option] [report_option]'
    print
    print '[option] is one of:'
    print ', '.join(CMDLINE_HELP), '        Display this help message and exit.'
    print '</some/path>    Attempt to use the string as a path for checking.'
    print '                Whitespace sensitive (use quotes), defaults to ~.'
    print
    print '[report_option] is one of:'
    print '--print         Prints report to console (not printer).'
    print '--email         Emails report using sender and recipient files.'
    print '--both          Default. Print and email.'
    print

if __name__ == '__main__':
    # Defaults!
    checkdir = '~'
    report = '--both'

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
    main(checkdir, report)



