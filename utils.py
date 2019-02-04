
import os
import socket
import subprocess


def better_repr(obj):
    """
    Replacement for `repr`, which is deterministic (e.g. sorted key order of dict),
    and behaves also nicer for diffs, or visual representation.

    :param object obj:
    :rtype: str
    """
    if isinstance(obj, dict):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "{\n%s}" % "".join(
                ["%s: %s,\n" % (better_repr(key), better_repr(value)) for (key, value) in sorted(obj.items())])
        return "{%s}" % ", ".join(
            ["%s: %s" % (better_repr(key), better_repr(value)) for (key, value) in sorted(obj.items())])
    if isinstance(obj, set):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "{\n%s}" % "".join(["%s,\n" % better_repr(value) for value in sorted(obj)])
        return "{%s}" % ", ".join([better_repr(value) for value in sorted(obj)])
    if isinstance(obj, list):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "[\n%s]" % "".join(["%s,\n" % better_repr(value) for value in obj])
        return "[%s]" % ", ".join([better_repr(value) for value in obj])
    if isinstance(obj, tuple):
        if len(obj) >= 5:  # multi-line?
            # Also always end items with "," such that diff is nicer.
            return "(\n%s)" % "".join(["%s,\n" % better_repr(value) for value in obj])
        if len(obj) == 1:
            return "(%s,)" % better_repr(obj[0])
        return "(%s)" % ", ".join([better_repr(value) for value in obj])
    # Generic fallback.
    return repr(obj)


def init_ipython_kernel(user_ns, debug_connection_filename=False):
    """
    You can remotely connect to this IPython kernel. See the output on stdout.

    :param dict[str] user_ns:
    :param bool debug_connection_filename:
    """
    connection_filename = "kernel.json"
    if debug_connection_filename:
        fn, ext = os.path.splitext(connection_filename)
        connection_filename = "%s-%s%s" % (fn, socket.gethostname(), ext)

    import background_zmq_ipython
    background_zmq_ipython.init_ipython_kernel(
        connection_filename=connection_filename,
        connection_fn_with_pid=debug_connection_filename,
        banner="Hello from i6 drink kiosk!\nAvailable variables:\n\n%s" % "".join(
            ["  %s = %r\n" % item for item in sorted(user_ns.items())]),
        user_ns=user_ns)


def is_git_dir(path):
    """
    :param str path:
    :rtype: bool
    """
    assert os.path.isdir(path)
    try:
        subprocess.check_call(["git", "status"], cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False
