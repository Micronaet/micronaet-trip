""" Procedure for move file HOS present in ELI folder
"""

import os
import shutil
import pdb
from datetime import datetime

origin = r'S:\script\elior\in'
destination = r'S:\script\hospes\order\in'

operation = []
pdb.set_trace()
for root, folders, files in os.walk(origin):
    for filename in files:
        fullname = os.path.join(root, filename)
        order_file = open(fullname, 'r')
        line = order_file.readline()  # First line
        if line[1545:1551] == 'HOSPES':
            filename = 'HOS' + filename[3:]
            operation.append((
                fullname,
                os.path.join(destination, filename),
                ))
            print('Hospes order (moved) %s' % fullname)
        else:
            print('Elior order (not touch) %s' % fullname)
    break  # Only first folder
pdb.set_trace()
log_f = open(r'S:\script\hospes\order\move.log', 'a')
if operation:
    log_f.write('\n\nSpostamenti del %s:\n' % str(datetime.now()))
for from_file, to_file in operation:
    log_f.write('%s >> %s\n' % (
        from_file, to_file))
    shutil.move(from_file, to_file)


