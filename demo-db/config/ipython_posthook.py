
from pprint import pprint

print("IPython kernel post hook")
print("Available variables:")
vs = vars().copy()
vs.pop("__builtins__", None)  # clean up a bit for stdout
vs.pop("background_zmq_ipython", None)
pprint(vs)
