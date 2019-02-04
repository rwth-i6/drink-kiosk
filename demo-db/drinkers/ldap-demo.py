#!/usr/bin/env python3

"""
This emulates `ldapsearch -x -h <host>` output.
"""

import os
import better_exchook

better_exchook.install()
my_dir = os.path.dirname(os.path.abspath(__file__))

print("""# extended LDIF
#
# LDAPv3
#
""")

count = 0

for ln in open("%s/list.txt" % my_dir).read().splitlines():
    ln = ln.strip()
    if not ln or ln.startswith("#"):
        continue
    username = ln
    print("# %s, users" % username)
    print("dn: cn=%s,ou=users" % username)
    print("cn: %s" % username)
    print("uid: %s" % username)
    print("")
    count += 1

print("""# search result
search: 2
result: 0 Success

# numResponses: %i
# numEntries: %i""" % (count + 1, count))
