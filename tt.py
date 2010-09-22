#!/usr/bin/env python

""" 
Simple-stupid time tracker script
=================================

Timetrack
opyright (C) 2010, Branko Vukelic <studio@brankovukelic.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import sys
import getopt
import os
import re
import sqlite3

HOME_DIR = os.path.expanduser('~')
DEFAULT_FILE = os.path.join(HOME_DIR, 'timesheet.db')
PID_RE = re.compile(r'^[A-Za-z]{3}$')

def optpair(opts):
    """ Pair option switches and their own arguments """
    optdict = {}
    for sw, a in opts:
        optdict[sw] = a
    return optdict

def check_pid(pname):
    """ Check project name, return true if it is correct """
    if PID_RE.match(pname):
        return True
    return False

def generate_timestamp():
    from datetime import datetime
    timenow = datetime.now()
    return (datetime.strftime(timenow, '%Y-%m-%d %H:%M:%S'), timenow)

def getduration(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    seconds = seconds - hours * 3600
    minutes = seconds // 60
    seconds = seconds - minutes * 60
    return (hours, minutes, seconds)

def get_pids(connection):
    """ Get unique PIDs from database """
    pids = []
    c = connection.cursor()
    c.execute("SELECT DISTINCT pid FROM timesheet ORDER BY pid ASC;")
    for pid in c:
        pids.append(pid[0])
    c.close()
    return pids

def get_times(connection, pidfilter):
    """ Return a dictionary of PIDs with [job, time] pairs """
    if pidfilter:
        pids = [pidfilter]
    else:
        pids = get_pids(connection)
    pid_times = {}
    for pid in pids:
        c = connection.cursor()
        c.execute("SELECT desc, TOTAL(dur) FROM timesheet WHERE pid = ? GROUP BY desc;", (pid,))
        results = []
        for result in c:
            results.append(result)
            pid_times[pid] = results
        c.close()
    return pid_times

def read_stats(connection, pidfilter):
    pid_times = get_times(connection, pidfilter)

    if not pid_times:
        print "No data in database. Exiting."
        return True

    for k in pid_times.keys():
        print ""
        print "=========================="
        print "PID: %s" % k
        print "=========================="
        print ""
        for j in pid_times[k]:
            print "Job: %s" % j[0]
            print "Total duration: %02d:%02d:%02d" % getduration(j[1])
            print ""
        print "=========================="
        print ""

def export_tsv(connection, filename, pidfilter):
    pid_times = get_times(connection, pidfilter)

    if not pid_times:
        print "No data in database. Exiting."
        return True
    
    f = open(filename, 'w')
    # Write header
    f.write('PID\tJob\tTime\n')
    for k in pid_times.keys():
        for j in pid_times[k]:
            f.write('%s\t%s\t%s\n' % (k, j[0], j[1]))
    f.close()

def clean_string(s):
    """ Escapes characters in a string for SQL """
    return s.replace(';', '\\;').replace('\'', '\\\'')

def add_data(connection, pidfilter):
    """ Gives user a prompt and writes data to the fhandle file """
    import readline
    
    print "Press Ctrl+C to exit."
    try:
        while True:
            pid = pidfilter
            while not check_pid(pid):
                pid = raw_input("PID: ")
                if not check_pid(pid):
                    print "'%s' is not a valid pid, please use a 3 letter sequence" % pid
            print "Project ID is %s" % pid
            desc = raw_input("Job: ")
            desc = clean_string(desc)
            if pid and desc:
                timestamp, starttime = generate_timestamp()
            print "Timer started at %s" % timestamp
            raw_input("Press Enter to stop the timer")
            endtimestamp, endtime = generate_timestamp()
            print "Timer stopped at %s" % endtimestamp
            delta = endtime - starttime
            dsecs = delta.seconds
            print "Total duration was %s seconds" % dsecs
            args = (timestamp, pid, desc, dsecs)
            c = connection.cursor()
            try:
                c.execute("INSERT INTO timesheet (timestamp, pid, desc, dur) VALUES (?, ?, ?, ?)", args)
            except:
                connection.rollback()
                print "DB error: Data was not written"
                raise
            else:
                connection.commit()
            c.close()
            print "\n"
            
    except KeyboardInterrupt:
        connection.rollback()

def usage():
    print """Timetrack
Copyright (c) 2010, Branko Vukelic
Released under GNU/GPL v3, see LICENSE file for details.

Usage: tt.py [-a] [-r] [-t FILE] [-p PID] 
             [--add] [--read] [--tsv FILE] [--pid PID] [dbfile]

-r --read  : Display the stats.
-a --add   : Start timer session (default action).
-t --tsv   : Export into a tab-separated table (TSV). FILE is the filename to
             use for exporting.
-p --pid   : With argument 'PID' (3 letters, no numbers or non-alphanumeric
             characters. Limits all operations to a single PID.
dbfile     : Use this file as database, instead of default file. If the
             specified file does not exist, it will be creadted.

More information at:

    http://github.com/foxbunny/timetrack

"""

def main(argv):
    try:
        opts, args = getopt.getopt(argv, 'rat:p:', ['read', 'add', 'tsv=', 'pid='])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    optdict = optpair(opts)
    statsfile = len(args) and args[0] or DEFAULT_FILE

    print "Using stats file '%s'" % statsfile

    pidfilter = optdict.get('-p', '') or optdict.get('--pid', '')
    if pidfilter:
        if check_pid(pidfilter):
            print "Using project ID filter '%s'" % pidfilter
        else:
            print "Project ID filter '%s' is invalid and will be ignored." % pidfilter
    print "Opening connection to database."
    try:
        connection = sqlite3.connect(statsfile)
    except:
        print "Database error. Exiting."
        sys.exit(2)

    print "Initialize table if none exists"

    c = connection.cursor()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS timesheet (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT (datetime('now')),
            pid VARCHAR(3) NOT NULL,
            desc VARCHAR(255) NOT NULL,
            dur INTEGER NOT NULL);""")
    except:
        connection.rollback()
        raise
    else:
        connection.commit()
    c.close()

    if ('-r' in optdict.keys()) or ('--read' in optdict.keys()):
        read_stats(connection, pidfilter)
    elif ('-t' in optdict.keys()) or ('--tsv' in optdict.keys()):
        filename = optdict.get('-t', None) or optdict.get('--tsv')
        export_tsv(connection, filename, pidfilter)
    else:
        add_data(connection, pidfilter)
    
    print "Closing connection to database"
    connection.close()
    sys.exit(1)

if __name__ == '__main__':
    main(sys.argv[1:])
