
import os
import pwd
from subprocess import Popen, PIPE
from pprint import pprint


print("Remote-admin drinker-pay post-hook")
print("Available variables:")
vs = vars().copy()
vs.pop("__builtins__", None)  # clean up a bit for stdout
vs.pop("background_zmq_ipython", None)
pprint(vs)


admin_username = pwd.getpwuid(os.getuid())[0]


p = Popen([
    "mail",
    "-c", admin_username,
    "-s", "Coffeepay Confirmation over %s Euro" % amount,
    "%s@i6.informatik.rwth-aachen.de" % name],
    stdin=PIPE)
p.communicate(("Thank you!\nYour current state:\n" + state_str).encode("utf8"))
assert p.returncode == 0, "Error running `mail`"

