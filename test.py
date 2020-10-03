import re

se = re.search( '.*\_(\d*)\_(\d*)\_(\d*).mp3$', 'http://rendezvousavecmrx.free.fr/audio/mr_x_2013_04_27.mp3', re.IGNORECASE)
if se:
    print(se.group(1))
