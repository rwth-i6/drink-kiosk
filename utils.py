

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
