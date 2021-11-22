#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import os
import ConfigParser
from os.path import isfile, join
from datetime import datetime, timedelta

# -----------------------------------------------------------------------------
#                                   Parameters:
# -----------------------------------------------------------------------------
# Config file:
cfg_file = './openerp.cfg'  # same directory
config = ConfigParser.ConfigParser()
config.read(cfg_file)

# Constant:
DATETIME_FORMAT = "%Y%m%d_%H%M%S"
DATETIME_FORMAT_LOG = "%Y/%m/%d %H:%M:%S"

# file to log:
log_file = config.get('log', 'ddt')
input_folder = config.get('path', 'ddt')
history_folder = config.get('path', 'history')
output_folder = config.get('path', 'ftp')
start_filename = config.get('path', 'start')

# -----------------------------------------------------------------------------
#                                  Utility:
# -----------------------------------------------------------------------------
log_file = open(log_file, 'w')


def log_event(comment, log_type='info'):
    """ Log on file the operations
    """
    log_file.write("[%s] %s >> %s\n" % (
        log_type,
        datetime.now().strftime(DATETIME_FORMAT_LOG),
        comment,
    ))
    return True


# -----------------------------------------------------------------------------
#                                  Start procedure:
# -----------------------------------------------------------------------------
now = datetime.now()
for root, folders, files in os.walk(input_folder):
    for input_file in files:
        log_event('Start splitting on file: %s' % input_file)

        try:
            in_file = open(input_file, 'r')
            i = 0
            for line in in_file:
                # Jump empty lines:
                if not line:
                    log_event("Empty line [%s] (jumped)" % i, 'warning')
                    continue

                # Check if need new file:
                if line.startswith('TM'):
                    try:
                        out_f.close()  # Close previous if present
                    except:
                        pass

                    output_filename = '%s_%s.csv' % (
                        start_filename,
                        now.strftime(DATETIME_FORMAT),
                    )
                    log_event('Output on file: %s' % output_filename)

                    now += timedelta(seconds=1)  # For new file
                    output_file = os.path.join(output_folder, output_filename)
                    out_f = open(output_file, 'w')
                    i = 0

                    # Read invoice number:
                i += 1
                # todo check old code:
                out_f.write(line)

            # Close file:
            if out_f:
                out_f.close()
            in_file.close()

            # History:
            history_filename = join(
                history_folder,
                datetime.now().strftime(DATETIME_FORMAT),
            )

            os.rename(input_file, history_filename)
            log_event('Historized file: %s' % history_filename)

            # Log:
            log_event("End splitting\n")
            log_file.close()
        except:
            log_event('Error splitting: %s\n' % (sys.exc_info(), ), 'error')
            sys.exit()

        break  # Only first folder read
