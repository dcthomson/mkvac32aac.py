#!/usr/bin/env python

#Copyright (C) 2012  Drew Thomson
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see <http://www.gnu.org/licenses/>.

##############################################################################
### NZBGET POST-PROCESSING SCRIPT                                          ###

# Convert the AC3 audio in MKV files to AAC.
#
# mkvac32aac.py is a python script for linux, windows or os x which can be used
# for converting the AC3 in Matroska (MKV) files to AAC. It provides you with a
# set of options for controlling the resulting file.

##############################################################################
### OPTIONS                                                                ###

## These options take an argument.

# NZBGet destination directory
#destdir=

# Apply header compression to streams (See mkvmerge's --compression)
#compress=

# Custom AAC track title
#custom=

# Mark AAC track as default (True, False).
#default=False

# Leave AAC track out of file. Does not modify the original matroska file. This overrides '-n' and '-d' arguments (True, False).
#external=False

# Path of ffmpeg (if not in path)
#ffmpegpath=

# Force processing when AAC track is detected (True, False).
#force=False

# Keep external AC3 track (implies '-n') (True, False).
#keepac3=False

# check md5 of files before removing the original if destination directory is on a different device than the original file (True, False).
#mdfive=False

# Path of mkvextract, mkvinfo and mkvmerge (if not in path)
#mkvtoolnixpath=

# Do not copy over original. Create new adjacent file (True, False).
#new=False

# Do not retain the AC3 track (True, False).
#noac3=False

# Remove subtitles (True, False).
#no_subtitles=False

# Overwrite file if already there (True, False).
#overwrite=False

# Position of AAC track in file (initial = First track in file, last = Last track in file, afterac3 = After the AC3 track)
#position=last

# Make aac track stereo instead of 6 channel (True, False).
#stereo=False

# Specify alternate AC3 track. If it is not a AC3 track it will default to the first AC3 track found
#track=

# Process all the AC3 tracks (True, False).
#all_tracks=False

# Specify alternate temporary working directory
#wd=

# Create output in mp4 format (True, False).
#mpfour=False

### NZBGET POST-PROCESSING SCRIPT                                          ###
##############################################################################

import argparse
import os
import subprocess
import time
import glob
import re
import tempfile
import sys
import ConfigParser
import shutil
import hashlib
import textwrap
import errno

version = "1.1"

sab = False
nzbget = False

# create parser
parser = argparse.ArgumentParser(description='convert matroska (.mkv) video files audio portion from ac3 to aac')

# Check if called from NZBGet
if os.environ.has_key('NZBOP_SCRIPTDIR') and not os.environ['NZBOP_VERSION'][0:5] < '11.0':
    #Logger.info("MAIN: Script triggered from NZBGet (11.0 or later).")

    nzbget = True
    # NZBGet argv: all passed as environment variables.
    # Exit codes used by NZBGet
    POSTPROCESS_PARCHECK=92
    POSTPROCESS_SUCCESS=93
    POSTPROCESS_ERROR=94
    POSTPROCESS_NONE=95

    # Check nzbget.conf options
    status = 0

    if os.environ['NZBOP_UNPACK'] != 'yes':
        #Logger.error("Please enable option \"Unpack\" in nzbget configuration file, exiting")
        sys.exit(POSTPROCESS_ERROR)

    # Check par status
    if os.environ['NZBPP_PARSTATUS'] == '3':
        #Logger.warning("Par-check successful, but Par-repair disabled, exiting")
        sys.exit(POSTPROCESS_NONE)

    if os.environ['NZBPP_PARSTATUS'] == '1':
        #Logger.warning("Par-check failed, setting status \"failed\"")
        status = 1

    # Check unpack status
    if os.environ['NZBPP_UNPACKSTATUS'] == '1':
        #Logger.warning("Unpack failed, setting status \"failed\"")
        status = 1

    if os.environ['NZBPP_UNPACKSTATUS'] == '0' and os.environ['NZBPP_PARSTATUS'] != '2':
        # Unpack is disabled or was skipped due to nzb-file properties or due to errors during par-check

        for dirpath, dirnames, filenames in os.walk(os.environ['NZBPP_DIRECTORY']):
            for file in filenames:
                fileExtension = os.path.splitext(file)[1]

                if fileExtension in ['.rar', '.7z'] or os.path.splitext(fileExtension)[1] in ['.rar', '.7z']:
                    #Logger.warning("Post-Process: Archive files exist but unpack skipped, setting status \"failed\"")
                    status = 1
                    break

                if fileExtension in ['.par2']:
                    #Logger.warning("Post-Process: Unpack skipped and par-check skipped (although par2-files exist), setting status \"failed\"g")
                    status = 1
                    break

        if os.path.isfile(os.path.join(os.environ['NZBPP_DIRECTORY'], "_brokenlog.txt")) and not status == 1:
            #Logger.warning("Post-Process: _brokenlog.txt exists, download is probably damaged, exiting")
            status = 1

        #if not status == 1:
            #Logger.info("Neither archive- nor par2-files found, _brokenlog.txt doesn't exist, considering download successful")

    # Check if destination directory exists (important for reprocessing of history items)
    if not os.path.isdir(os.environ['NZBPP_DIRECTORY']):
        #Logger.error("Post-Process: Nothing to post-process: destination directory %s doesn't exist", os.environ['NZBPP_DIRECTORY'])
        status = 1

    args = parser.parse_args()
    
    args.fileordir = [os.environ['NZBPP_DIRECTORY']]
    
    if not 'NZBPO_DEFAULT' in os.environ:
        raise Exception("mkvac32aac.py settings not saved")
        sys.exit(POSTPROCESS_ERROR)
    
    args.compress = os.environ['NZBPO_COMPRESS']
    
    args.custom = os.environ['NZBPO_CUSTOM']
    
    if os.environ['NZBPO_DEFAULT'] == 'False':
        args.default = False
    else:
        args.default = True 
    
    args.destdir = os.environ['NZBPO_DESTDIR']
    
    if os.environ['NZBPO_EXTERNAL'] == 'False':
        args.external = False
    else:
        args.external = True
    
    args.ffmpegpath = os.environ['NZBPO_FFMPEGPATH']
    
    if os.environ['NZBPO_FORCE'] == 'False':
        args.force = False
    else:
        args.force = True

    if os.environ['NZBPO_KEEPAC3'] == 'False':
        args.keepac3 = False
    else:
        args.keepac3 = True

    if os.environ['NZBPO_MDFIVE'] == 'False':
        args.md5 = False
    else:
        args.md5 = True
        
    args.mkvtoolnixpath = os.environ['NZBPO_MKVTOOLNIXPATH']
    
    if os.environ['NZBPO_NEW'] == 'False':
        args.new = False
    else:
        args.new = True

    if os.environ['NZBPO_NOAC3'] == 'False':
        args.noac3 = False
    else:
        args.noac3 = True

    if os.environ['NZBPO_NO_SUBTITLES'] == 'False':
        args.no_subtitles = False
    else:
        args.no_subtitles = True

    if os.environ['NZBPO_OVERWRITE'] == 'False':
        args.overwrite = False
    else:
        args.overwrite = True

    args.position = os.environ['NZBPO_POSITION']

    args.sabdestdir = 'sab'
    
    if os.environ['NZBPO_STEREO'] == 'False':
        args.stereo = False
    else:
        args.stereo = True

    args.track = os.environ['NZBPO_TRACK']

    if os.environ['NZBPO_ALL_TRACKS'] == 'False':
        args.all_tracks = False
    else:
        args.all_tracks = True

    args.wd = os.environ['NZBPO_WD']
    
    if os.environ['NZBPO_MPFOUR'] == 'False':
        args.mp4 = False
    else:
        args.mp4 = True

    args.verbose = 3
    args.recursive = False
    args.test = False
    args.debug = False

# NZBGet config done

else:
    # Check if called form sabnzbd
    if len(sys.argv) == 8:
        nzbgroup = sys.argv[6]
        ppstatus = sys.argv[7]
        if ppstatus.isdigit():
            if int(ppstatus) >= 0 and int(ppstatus) <= 3 and "." in nzbgroup:
                sab = True

    # set config file arguments
    configFilename = os.path.join(os.path.dirname(sys.argv[0]), "mkvac32aac.cfg")

    if os.path.isfile(configFilename):
        config = ConfigParser.SafeConfigParser()
        config.read(configFilename)
        defaults = dict(config.items("mkvac32aac"))
        for key in defaults:
            if key == "verbose":
                defaults["verbose"] = int(defaults["verbose"])

        parser.set_defaults(**defaults)

    parser.add_argument('fileordir', metavar='FileOrDirectory', nargs='+', help='a file or directory (wildcards may be used)')

    parser.add_argument("-c", "--custom", metavar="TITLE", help="Custom AAC track title")
    parser.add_argument("-d", "--default", help="Mark AAC track as default", action="store_true")
    parser.add_argument("--destdir", metavar="DIRECTORY", help="Destination Directory")
    parser.add_argument("-e", "--external", action="store_true",
                        help="Leave AAC track out of file. Does not modify the original matroska file. This overrides '-n' and '-d' arguments")
    parser.add_argument("-f", "--force", help="Force processing when AAC track is detected", action="store_true")
    parser.add_argument("--ffmpegpath", metavar="DIRECTORY", help="Path of ffmpeg")
    parser.add_argument("-k", "--keepac3", help="Keep external AC3 track (implies '-n')", action="store_true")
    parser.add_argument("--md5", help="check md5 of files before removing the original if destination directory is on a different device than the original file", action="store_true")
    parser.add_argument("--mp4", help="create output in mp4 format", action="store_true")
    parser.add_argument("--mkvtoolnixpath", metavar="DIRECTORY", help="Path of mkvextract, mkvinfo and mkvmerge")
    parser.add_argument("-n", "--noac3", help="Do not retain the AC3 track", action="store_true")
    parser.add_argument("--new", help="Do not copy over original. Create new adjacent file", action="store_true")
    parser.add_argument("--no-subtitles", help="Remove subtitles", action="store_true")
    parser.add_argument("-o", "--overwrite", help="Overwrite file if already there. This only applies if destdir or sabdestdir is set", action="store_true")
    parser.add_argument("-p", "--position", choices=['initial', 'last', 'afterac3'], default="last", help="Set position of AAC track. 'initial' = First track in file, 'last' = Last track in file, 'afterac3' = After the AC3 track [default: last]")
    parser.add_argument("-r", "--recursive", help="Recursively descend into directories", action="store_true")
    parser.add_argument("-s", "--compress", metavar="MODE", help="Apply header compression to streams (See mkvmerge's --compression)", default='none')
    parser.add_argument("--sabdestdir", metavar="DIRECTORY", help="SABnzbd Destination Directory")
    parser.add_argument("--stereo", help="Make aac track stereo instead of 6 channel", action="store_true")
    parser.add_argument("-t", "--track", metavar="TRACKID", help="Specify alternate AC3 track. If it is not a AC3 track it will default to the first AC3 track found")
    parser.add_argument("--all-tracks", help="Convert all AC3 tracks", action="store_true");
    parser.add_argument("-w", "--wd", metavar="FOLDER", help="Specify alternate temporary working directory")
    parser.add_argument("-v", "--verbose", help="Turn on verbose output. Use more v's for more verbosity. -v will output what it is doing. -vv will also output the command that it is running. -vvv will also output the command output", action="count")
    parser.add_argument("-V", "--version", help="Print script version information", action='version', version='%(prog)s ' + version + ' by Drew Thomson')
    parser.add_argument("--test", help="Print commands only, execute nothing", action="store_true")
    parser.add_argument("--debug", help="Print commands and pause before executing each", action="store_true")

    args = parser.parse_args()

    if not args.verbose:
        args.verbose = 0

def winexe(program):
    if sys.platform == "win32" and not program.endswith(".exe"):
        program += ".exe"
    return program

# set ffmpeg and mkvtoolnix paths
if args.mkvtoolnixpath:
    mkvinfo = os.path.join(args.mkvtoolnixpath, "mkvinfo")
    mkvinfo = winexe(mkvinfo)
    mkvmerge = os.path.join(args.mkvtoolnixpath, "mkvmerge")
    mkvmerge = winexe(mkvmerge)
    mkvextract = os.path.join(args.mkvtoolnixpath, "mkvextract")
    mkvextract = winexe(mkvextract)
if not args.mkvtoolnixpath or not os.path.exists(mkvinfo):
    mkvinfo = "mkvinfo"
if not args.mkvtoolnixpath or not os.path.exists(mkvmerge):
    mkvmerge = "mkvmerge"
if not args.mkvtoolnixpath or not os.path.exists(mkvextract):
    mkvextract = "mkvextract"
   
if args.ffmpegpath:
    ffmpeg = os.path.join(args.ffmpegpath, "ffmpeg")
    ffmpeg = winexe(ffmpeg)
if not args.ffmpegpath or not os.path.exists(ffmpeg):
    ffmpeg = "ffmpeg"


# check paths
def which(program):
    if sys.platform == "win32" and not program.endswith(".exe"):
        program += ".exe"
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath = os.path.split(program)[0]
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

missingprereqs = False
missinglist = []
if not which(mkvextract):
    missingprereqs = True
    missinglist.append("mkvextract")
if not which(mkvinfo):
    missingprereqs = True
    missinglist.append("mkvinfo")
if not which(mkvmerge):
    missingprereqs = True
    missinglist.append("mkvmerge")
if not which(ffmpeg):
    missingprereqs = True
    missinglist.append("ffmpeg")
if missingprereqs:
    sys.stdout.write("You are missing the following prerequisite tools: ")
    for tool in missinglist:
        sys.stdout.write(tool + " ")
    if not args.mkvtoolnixpath and not args.ffmpegpath:
        print "\nYou can use --mkvtoolnixpath and --ffmpegpath to specify the path"
    else:
        print   
    sys.exit(1)

if not args.verbose:
    args.verbose = 0

if args.verbose < 2 and (args.test or args.debug):
    args.verbose = 2

if sab:
    args.fileordir = [args.fileordir[0]]
    args.verbose = 3

if args.debug and args.verbose == 0:
    args.verbose = 1

def doprint(mystr, v=0):
    if args.verbose >= v:
        sys.stdout.write(mystr)

def silentremove(filename):
    try:
        os.remove(filename)
    except OSError, e:
        if e.errno != errno.ENOENT: # errno.ENOENT = no such file or directory
            raise # re-raise exception if a different error occured

def elapsedstr(starttime):
    elapsed = (time.time() - starttime)
    minutes = int(elapsed / 60)
    mplural = 's'
    if minutes == 1:
        mplural = ''
    seconds = int(elapsed) % 60
    splural = 's'
    if seconds == 1:
        splural = ''
    return str(minutes) + " minute" + mplural + " " + str(seconds) + " second" + splural

def getduration(time):
    (hms, ms) = time.split('.')
    (h, m, s) = hms.split(':')
    totalms = int(ms) + (int(s) * 100) + (int(m) * 100 * 60) + (int(h) * 100 * 60 * 60)
    return totalms
   
def runcommand(title, cmdlist):
    if args.debug:
        raw_input("Press Enter to continue...")
    cmdstarttime = time.time()
    if args.verbose >= 1:
        sys.stdout.write(title)
        if args.verbose >= 2:
            cmdstr = ''
            for e in cmdlist:
                cmdstr += e + ' '
            print
            print "    Running command:"
            print textwrap.fill(cmdstr.rstrip(), initial_indent='      ', subsequent_indent='      ')
    if not args.test:
        if args.verbose >= 3:
            subprocess.call(cmdlist)
        elif args.verbose >= 1:
            if "ffmpeg" in cmdlist[0]:
                proc = subprocess.Popen(cmdlist, stderr=subprocess.PIPE)
                line = ''
                duration_regex = re.compile("  Duration: (\d+:\d\d:\d\d\.\d\d),")
                progress_regex = re.compile("size= +\d+.*time=(\d+:\d\d:\d\d\.\d\d) bitrate=")
                duration = False
                while True:
                    if not duration:
                        durationline = proc.stderr.readline()
                        match = duration_regex.match(durationline)
                        if match:
                            duration = getduration(match.group(1))
                    else:
                        out = proc.stderr.read(1)
                        if out == '' and proc.poll() != None:
                            break
                        if out != '\r':
                            line += out
                        else:
                            if 'size= ' in line:
                                match = progress_regex.search(line)
                                if match:
                                    percentage = int(float(getduration(match.group(1)) / float(duration)) * 100)
                                    if percentage > 100:
                                        percentage = 100
                                    sys.stdout.write("\r" + title + str(percentage) + '%')
                            line = ''
                        sys.stdout.flush()
                print "\r" + title + elapsedstr(cmdstarttime)
            else:
                proc = subprocess.Popen(cmdlist, stdout=subprocess.PIPE)
                line = ''
                progress_regex = re.compile("Progress: (\d+%)")
                while True:
                    out = proc.stdout.read(1)
                    if out == '' and proc.poll() != None:
                        break
                    if out != '\r':
                        line += out
                    else:
                        if 'Progress: ' in line:
                            match = progress_regex.search(line)
                            if match:
                                percentage = match.group(1)
                                sys.stdout.write("\r" + title + percentage)
                        line = ''
                    sys.stdout.flush()
                print "\r" + title + elapsedstr(cmdstarttime)
        else:
            subprocess.call(cmdlist, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def find_mount_point(path):
    path = os.path.abspath(path)
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path

def getmd5(fname, block_size=2**12):
    md5 = hashlib.md5()
    with open(fname, 'rb') as f:
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)
        doprint(fname + ": " + md5.hexdigest() + "\n", 3)
    return md5.hexdigest()

def check_md5tree(orig, dest):
    rt = True
    orig = os.path.abspath(orig)
    dest = os.path.abspath(dest)
    for ofile in os.listdir(orig):
        if rt == True:
            if os.path.isdir(os.path.join(orig, ofile)):
                doprint("dir: " + os.path.join(orig, ofile) + "\n", 3)
                odir = os.path.join(orig, ofile)
                ddir = os.path.join(dest, ofile)
                rt = check_md5tree(odir, ddir)
            else:
                doprint("file: " + os.path.join(orig, ofile) + "\n", 3)
                if getmd5(os.path.join(orig, ofile)) != getmd5(os.path.join(dest, ofile)):
                    rt = False
    return rt

def process(ford):
    if os.path.isdir(ford):
        doprint("    Processing dir:  " + ford + "\n", 3)
        if args.recursive:
            for f in os.listdir(ford):
                process(os.path.join(ford, f))
    else:
        doprint("    Processing file: " + ford + "\n", 3)
        # check if file is an mkv file
        child = subprocess.Popen([mkvmerge, "-i", ford], stdout=subprocess.PIPE)
        child.communicate()[0]
        if child.returncode == 0:
            starttime = time.time()
           
            # set up temp dir
            tempdir = False
            if args.wd:
                tempdir = args.wd
                if not os.path.exists(tempdir):
                    os.makedirs(tempdir)
            else:
                tempdir = tempfile.mkdtemp()
                tempdir = os.path.join(tempdir, "mkvac32aac")
               
            (dirName, fileName) = os.path.split(ford)
            fileBaseName = os.path.splitext(fileName)[0]
           
            doprint("filename: " + fileName + "\n", 1)

            newmkvfile = fileBaseName + '.mkv'
            tempnewmkvfile = os.path.join(tempdir, newmkvfile)
            adjacentmkvfile = os.path.join(dirName, fileBaseName + '.new.mkv')
            mp4file = os.path.join(dirName, fileBaseName + '.mp4')
            files = []
            if not args.external and not args.mp4:
                files.append(fileName)
           
            # get ac3 track id and video track id
            output = subprocess.check_output([mkvmerge, "-i", ford])
            lines = output.split("\n")
            altac3trackid = False
            videotrackid = False
            alreadygotaac = False
            audiotracks = []
            ac3tracks = []
            for line in lines:
                linelist = line.split(' ')
                trackid = False
                if len(linelist) > 2:
                    trackid = linelist[2]
                    linelist = trackid.split(':')
                    trackid = linelist[0]
                if ' audio (' in line:
                    audiotracks.append(trackid)
                if ' audio (A_AC3)' in line or ' audio (AC3' in line:
                    ac3tracks.append(trackid)
                elif ' video (' in line:
                    videotrackid = trackid
                elif ' audio (A_AAC)' in line or ' audio (AAC' in line:
                    alreadygotaac = True
                if args.track:
                    matchObj = re.match( r'Track ID ' + args.track + r': audio \(A?_?AC3', line)
                    if matchObj:
                        altac3trackid = args.track
            if altac3trackid:
                ac3tracks[:] = []
                ac3tracks.append(altac3trackid)
           
            if not ac3tracks:
                doprint("  No AC3 tracks found\n", 1)
            elif alreadygotaac and not args.force:
                doprint("  Already has AAC track\n", 1)
            else:
                if not args.all_tracks:
                    ac3tracks = ac3tracks[0:1]

                # 3 jobs per AC3 track (Extract AC3, Extract timecodes, Transcode)
                totaljobs = (3 * len(ac3tracks))
                # 1 Remux+ 1
                if not args.external:
                    totaljobs += 1
                if args.mp4:
                    # Convert mkv -> mp4
                    totaljobs += 1
                jobnum = 1

                ac3info = dict()
                for ac3trackid in ac3tracks:
                    ac3file = fileBaseName + ac3trackid + '.ac3'
                    tempac3file = os.path.join(tempdir, ac3file)
                    aacfile = fileBaseName + ac3trackid + '.aac'
                    tempaacfile = os.path.join(tempdir, aacfile)
                    tcfile = fileBaseName + ac3trackid + '.tc'
                    temptcfile = os.path.join(tempdir, tcfile)

                    # get ac3track info
                    output = subprocess.check_output([mkvinfo, "--ui-language", "en_US", ford])
                    lines = output.split("\n")
                    ac3trackinfo = []
                    startcount = 0
                    for line in lines:
                        match = re.search(r'^\|( *)\+', line)
                        linespaces = startcount
                        if match:
                            linespaces = len(match.group(1))
                        if startcount == 0:
                            if "track ID for mkvmerge & mkvextract:" in line:
                                if "track ID for mkvmerge & mkvextract: " + ac3trackid in line:
                                    startcount = linespaces
                            elif "+ Track number: " + ac3trackid in line:
                                startcount = linespaces
                        if linespaces < startcount:
                            break
                        if startcount != 0:
                            ac3trackinfo.append(line)
                   
                    # get ac3 language
                    ac3lang = "eng"
                    for line in ac3trackinfo:
                        if "Language" in line:
                            ac3lang = line.split()[-1]
                   
                    # get aac track name
                    aacname = False
                    if args.custom:
                        aacname = args.custom
                    else:
                        for line in ac3trackinfo:
                            if "+ Name: " in line:
                                aacname = line.split("+ Name: ")[-1]
                                aacname = aacname.replace("AC3", "AAC")
                                aacname = aacname.replace("ac3", "aac")
                                if args.stereo:
                                    aacname = aacname.replace("5.1", "Stereo")
                   
                    # extract timecodes
                    tctitle = "  Extracting Timecodes  [" + str(jobnum) + "/" + str(totaljobs) + "]..."
                    jobnum += 1
                    tccmd = [mkvextract, "timecodes_v2", ford, ac3trackid + ":" + temptcfile]
                    runcommand(tctitle, tccmd)

                    delay = False
                    if not args.test:
                        # get the delay if there is any
                        fp = open(temptcfile)
                        for i, line in enumerate(fp):
                            if i == 1:
                                delay = line
                                break
                        fp.close()

                    # extract ac3 track
                    extracttitle = "  Extracting AC3 track  [" + str(jobnum) + "/" + str(totaljobs) + "]..."
                    jobnum += 1
                    extractcmd = [mkvextract, "tracks", ford, ac3trackid + ':' + tempac3file]
                    runcommand(extracttitle, extractcmd)

                    # convert AC3 to AAC
                    converttitle = "  Converting AC3 to AAC [" + str(jobnum) + "/" + str(totaljobs) + "]..."
                    jobnum += 1
                    audiochannels = 6
                    if args.stereo:
                        audiochannels = 2
                    convertcmd = [ffmpeg, "-y", "-i", tempac3file, "-strict", "-2", "-acodec", "aac", "-ac", str(audiochannels), "-ab", "448k", tempaacfile]
                    runcommand(converttitle, convertcmd)
                   
                    # Save information about current AC3 track
                    ac3info[ac3trackid] = {
                      'ac3file': tempac3file,
                      'aacfile': tempaacfile,
                      'tcfile': temptcfile,
                      'lang': ac3lang,
                      'aacname': aacname,
                      'delay': delay
                    }

                    if args.external:
                        if not args.test:
                            trackIdentifier = ''
                            if args.all_tracks and len(ac3tracks) > 1:
                                trackIdentifier = '_' + ac3trackid
                            outputaacfile = fileBaseName + trackIdentifier + '.aac'
                            shutil.move(tempaacfile, os.path.join(dirName, outputaacfile))
                            files.append(outputaacfile)

                if not args.external:
                    # remux
                    remuxtitle = "  Remuxing AAC into MKV [" + str(jobnum) + "/" + str(totaljobs) + "]..."
                    jobnum += 1
                    # Start to "build" command
                    remux = [mkvmerge]

                    comp = 'none'
                    if args.compress:
                        comp = args.compress

                    # Remove subtitles
                    if args.no_subtitles:
                        remux.append("--no-subtitles")

                    # Change the default position of the tracks if requested
                    if args.position != 'last':
                        remux.append("--track-order")
                        tracklist = []
                        if args.position == "initial":
                            totaltracks = len(ac3tracks)
                            for trackid in range(1, int(totaltracks) + 1):
                                tracklist.append('%d:0' % trackid)
                        elif args.position == "afterac3":
                            currenttrack = 0
                            for ac3trackid in ac3tracks:
                                # Tracks up to the AC3 track
                                for trackid in range(currenttrack, int(ac3trackid)):
                                    tracklist.append('0:%d' % trackid)
                                # AC3 track
                                if not (args.noac3 or args.keepac3):
                                    tracklist.append('0:%d' % int(ac3trackid))
                                # AAC track
                                tracklist.append('1:0')
                                currenttrack = int(ac3trackid) + 1
                            # The remaining tracks
                            for trackid in range(currenttrack, len(audiotracks)):
                                tracklist.append('0:%d' % trackid)
                        remux.append(','.join(tracklist))

                    # If user doesn't want the original AC3 track drop it
                    if args.noac3 or args.keepac3:
                        audiotracks = [audiotrack for audiotrack in audiotracks if audiotrack not in ac3tracks]
                        if len(audiotracks) == 0:
                            remux.append("--no-audio")
                        else:
                            remux.append("--audio-tracks")
                            remux.append(",".join(audiotracks))
                            for tid in audiotracks:
                                remux.append("--compression")
                                remux.append(tid + ":" + comp)

                    # Add original MKV file, set header compression scheme
                    remux.append("--compression")
                    remux.append(videotrackid + ":" + comp)
                    remux.append(ford)

                    # If user wants new AAC as default then add appropriate arguments to command
                    if args.default:
                        remux.append("--default-track")
                        remux.append("0:1")

                    # Add parameters for each AC3 track processed
                    for ac3trackid in ac3tracks:

                        # Set the language
                        remux.append("--language")
                        remux.append("0:" + ac3info[ac3trackid]['lang'])

                        # If the name was set for the original AC3 track set it for the AAC
                        if aacname:
                            remux.append("--track-name")
                            remux.append("0:\"" + ac3info[ac3trackid]['aacname'].rstrip() + "\"")

                        # set delay if there is any
                        if delay:
                            remux.append("--sync")
                            remux.append("0:" + ac3info[ac3trackid]['delay'].rstrip())

                        # Set track compression scheme and append new AAC
                        remux.append("--compression")
                        remux.append("0:" + comp)
                        remux.append(ac3info[ac3trackid]['aacfile'])

                    # Declare output file
                    remux.append("-o")
                    remux.append(tempnewmkvfile)

                    runcommand(remuxtitle, remux)

                    if not args.test:
                        if args.mp4:
                            converttitle = "  Converting MKV to MP4 [" + str(jobnum) + "/" + str(totaljobs) + "]..."
                            convertcmd = [ffmpeg, "-i", tempnewmkvfile, "-map", "0", "-vcodec", "copy", "-acodec", "copy", "-c:s", "mov_text", mp4file]
                            runcommand(converttitle, convertcmd)
                            if not args.new:
                                silentremove(ford)
                            silentremove(tempnewmkvfile)
                            files.append(fileBaseName + '.mp4')
                        else:
                            #~ replace old mkv with new mkv
                            if args.new:
                                shutil.move(tempnewmkvfile, adjacentmkvfile)
                            else:
                                silentremove(ford)
                                shutil.move(tempnewmkvfile, ford)

                #~ clean up temp folder
                if not args.test:
                    if args.keepac3 and not args.external:
                        if len(ac3tracks) > 1:
                            for ac3trackid in ac3tracks:
                                outputac3file = fileBaseName + '_' + ac3trackid + '.ac3'
                                shutil.move(ac3info[ac3trackid]['ac3file'], os.path.join(dirName, outputac3file))
                                files.append(outputac3file)
                        else:
                            outputac3file = fileBaseName + ".ac3"
                            shutil.move(tempac3file, os.path.join(dirName, outputac3file))
                            files.append(outputac3file)
                    for ac3trackid in ac3tracks:
                        silentremove(ac3info[ac3trackid]['ac3file'])
                        silentremove(ac3info[ac3trackid]['aacfile'])
                        silentremove(ac3info[ac3trackid]['tcfile'])
                    if not os.listdir(tempdir):
                        os.rmdir(tempdir)

                #~ print out time taken
                elapsed = (time.time() - starttime)
                minutes = int(elapsed / 60)
                seconds = int(elapsed) % 60
                doprint("  " + fileName + " finished in: " + str(minutes) + " minutes " + str(seconds) + " seconds\n", 1)

            return files

totalstime = time.time()
for a in args.fileordir:
    for ford in glob.glob(a):
        files = []
        if os.path.isdir(ford):
            for f in os.listdir(ford):
                process(os.path.join(ford, f))
        else:
            files = process(ford)
        destdir = False
        if args.destdir:
            destdir = args.destdir
        if sab and args.sabdestdir:
            destdir = args.sabdestdir
        if destdir:
            if len(files):
                for fname in files:
                    (dirName, fileName) = os.path.split(ford)
                    destfile = os.path.join(destdir, fname)
                    origfile = os.path.join(dirName, fname)
                    if args.md5 and (find_mount_point(dirName) != find_mount_point(destdir)):
                        if os.path.exists(destfile):
                            if args.overwrite:
                                silentremove(destfile)
                                shutil.copyfile(origfile, destfile)
                                if getmd5(origfile) == getmd5(destfile):
                                    silentremove(origfile)
                                else:
                                    print "MD5's don't match."
                            else:
                                print "File " + destfile + " already exists"
                        else:
                            doprint("copying: " + origfile + " --> " + destfile + "\n", 3)
                            shutil.copyfile(origfile, destfile)
                            if getmd5(origfile) == getmd5(destfile):
                                silentremove(origfile)
                            else:
                                print "MD5's don't match."
                    else:
                        if os.path.exists(destfile):
                            if args.overwrite:
                                silentremove(destfile)
                                shutil.move(origfile, destfile)
                            else:
                                print "File " + destfile + " already exists"
                        else:
                            shutil.move(origfile, destfile)
            else:
                origpath = os.path.abspath(ford)
                destpath = os.path.join(destdir, os.path.basename(os.path.normpath(ford)))
                if args.md5 and (find_mount_point(origpath) != find_mount_point(destpath)):
                    if os.path.exists(destpath) and args.overwrite:
                        shutil.rmtree(destpath)
                    elif os.path.exists(destpath):   
                        print "Directory " + destpath + " already exists"
                    else:
                        shutil.copytree(origpath, destpath)
                        if check_md5tree(origpath, destpath):
                            shutil.rmtree(origpath)
                        else:
                            print "MD5's don't match."
                else:
                    shutil.move(origpath, destpath)
                   
if sab or nzbget:
    sys.stdout.write("mkv ac3 -> aac conversion: " + elapsedstr(totalstime))
else:
    doprint("Total Time: " + elapsedstr(totalstime) + "\n", 1)

if nzbget:
    sys.exit(POSTPROCESS_SUCCESS)
