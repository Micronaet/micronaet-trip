#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
# Developer: Nicola Riolini @thebrush
#            https://it.linkedin.com/in/thebrush
#            https://linktr.ee/nicolariolini
###############################################################################

import os
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

partic_filename = '/home/openerp/mexal/cella/csv/PARTIC.GFD'

check_file = [
    '/home/openerp/mexal/whoami.mexal',
    '/home/openerp/etl/edi/whoami.edi',
    partic_filename,
    ]

loop = {
    ['/home/openerp/etl/edi/price/fabbro.csv', '06.02923'],  # 8
    ['/home/openerp/etl/edi/price/hospes.csv', '06.02901'],  # 10 (same as ELI)
}

# Check files:
for filename in check_file:
    if os.path.isfile(filename):
        continue
    # todo raise error, no mounted server for manage price

for out_filename, customer_code in loop:
    command = 'cat %s | grep %s > %s' % (
        partic_filename,
        customer_code,
        out_filename
    )
    print('Executing %s...' % command)
    os.system(command)
