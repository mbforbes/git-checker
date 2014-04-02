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
from email.mime.text import MIMEText
from smtplib import SMTP_SSL as SMTP

#
# CONSTANTS
#

#
# CLASSES
#


#
# FUNCTIONS
#

        
#
# MAIN
#

def main():
    '''Check git directories for uncommited files and unpushed commits. Then
    send an email report to the user.'''
    # Settings.
    check_dir = '/Users/max'
    # Who to send report to.
    with open('recipient') as recipient:
        user_email = recipient.read().strip()

    # Account with which to send the email from
    with open('sender') as sender:
        sender_uname, sender_psswd = sender.read().strip().split('\n')

    # Get the void.
    dn = open(os.devnull, 'w')

    # Check.
    p = sp.Popen(['find', # command
        check_dir, # directory to look in (home)
        '-name', # search by name
        '.git'], # the name we want
        stdout=sp.PIPE, # catch output
        stderr=dn) # send errors to the void!
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
            '\n'.join(['\t - ' + x for x in dirtydirs]) + '\n\n'
    if len(unpusheddirs) > 0:
        msgstr += 'The following directories need to be pushed:\n' + \
        '\n'.join(['\t - ' + x for x in unpusheddirs])
    msg = MIMEText(msgstr)

    # debug
    #print msgstr

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


if __name__ == '__main__':
    main()
