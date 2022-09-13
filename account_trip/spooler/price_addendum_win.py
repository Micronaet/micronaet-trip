#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
import pdb
import sys
import pickle
import shutil
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, join
import ConfigParser

# -----------
# Parameters:
# -----------
cfg_file = 'openerp_s.cfg'  # same directory
config = ConfigParser.ConfigParser()
config.read(cfg_file)

# mexal_user = config.get('mexal', 'user')

pdb.set_trace()
mexal_server = r'\\192.168.21.246\edi'
edi_server = r'S:\script'

partic_filename = os.path.join(mexal_server, 'cella', 'csv', 'PARTIC.GFD')

check_file = [
    os.path.join(mexal_server, 'whoami.mexal'),
    os.path.join(edi_server, 'whoami.edi'),
    partic_filename,
    ]

loop = {
    [os.path.join(edi_server, 'price', 'fabbro.csv'), '06.02923'],  # 8
    [os.path.join(edi_server, 'price', 'hospes.csv'), '06.02901'],  # 10 as ELI
}

# Check files:
error = ''
for filename in check_file:
    if os.path.isfile(filename):
        continue
    error += 'Error mounting resource, file: %s' % filename

if error:
    print(error)
    # Raise error in Telegram
    sys.exit()

for out_filename, customer_code in loop:
    command = 'type %s | findstr %s > %s' % (
        partic_filename,
        customer_code,
        out_filename
    )
    print('Executing %s...' % command)
    # os.system(command)
