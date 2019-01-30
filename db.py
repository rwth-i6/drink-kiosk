
import typing
import os
from decimal import Decimal
import subprocess
from pprint import pprint


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


class BuyItem:
    def __init__(self, intern_name, shown_name, price):
        """
        :param str intern_name:
        :param str shown_name:
        :param Decimal|str|float|int price:
        """
        self.intern_name = intern_name
        self.shown_name = shown_name
        self.price = Decimal(price)


class Drinker:
    def __init__(self, name, credit_balance=0, buy_item_counts=None):
        """
        :param str name:
        :param Decimal credit_balance:
        :param dict[str,int] buy_item_counts:
        """
        self.name = name
        self.credit_balance = credit_balance
        self.buy_item_counts = buy_item_counts or {}  # type: typing.Dict[str,int]

    def __repr__(self):
        attribs = ["name", "credit_balance", "buy_item_counts"]
        return "%s(\n%s)" % (
            self.__class__.__name__,
            ",\n".join(["%s=%s" % (attr, better_repr(getattr(self, attr))) for attr in attribs]))


class Db:
    def __init__(self, path):
        """
        :param str path:
        """
        assert os.path.isdir(path)
        assert os.path.exists("%s/.git" % path), "not a Git dir?"
        self.path = path
        self.drinkers_list_fn = "%s/drinkers/list.txt" % path
        self.drinker_names = open(self.drinkers_list_fn).read().splitlines()
        self.currency = "€"
        self.buy_items = self._load_buy_items()

    def _load_buy_items(self):
        """
        :rtype: list[BuyItem]
        """
        # Could be loaded from file...
        return [
            BuyItem("Wasser", "Wasser", "0.55"),
            BuyItem("Cola", "Cola|Malz", "0.60"),
            BuyItem("Mate", "Club Mate", "0.95"),
            BuyItem("Kaffee", "Kaffee|etc", "0.24")]

    def get_drinker_names(self):
        """
        :rtype: list[str]
        """
        return self.drinker_names

    def get_buy_items(self):
        return self.buy_items

    def get_buy_items_by_intern_name(self):
        """
        :rtype: dict[str,BuyItem]
        """
        return {item.intern_name: item for item in self.get_buy_items()}

    def _drinker_fn(self, drinker_name):
        """
        :param str drinker_name:
        :rtype: str
        """
        return "%s/drinkers/state/%s.txt" % (self.path, drinker_name)

    def get_drinker(self, name):
        """
        :param str name:
        :rtype: Drinker
        """
        drinker_fn = self._drinker_fn(name)
        if os.path.exists(drinker_fn):
            s = open(drinker_fn).read()
            drinker = eval(s)
            assert isinstance(drinker, Drinker)
            assert drinker.name == name
        else:
            drinker = Drinker(name=name)
        return drinker

    def save_drinker(self, drinker):
        """
        :param Drinker drinker:
        """
        drinker_fn = self._drinker_fn(drinker.name)
        with open(drinker_fn, "f") as f:
            f.write("%r\n" % drinker)

    def update_drinkers_list(self, verbose=False):
        """
        This has to run where LDAP is correctly configured.

        :param bool verbose:
        """
        ldap_cmd_fn = "%s/config/ldap-opts.txt" % self.path  # example: ldapsearch -x -h <host>
        ldap_cmd = open(ldap_cmd_fn).read().strip().split(" ")
        out = subprocess.check_output(ldap_cmd)
        lines = out.splitlines()
        drinkers_exclude_list_fn = "%s/drinkers/exclude_list.txt" % self.path
        exclude_users = set(open(drinkers_exclude_list_fn).read().splitlines())
        cur_entry = None  # type: typing.Optional[typing.Dict[str,typing.Union[str,typing.List[str]]]] # key -> value(s)
        multi_values = {"cn", "objectClass", "memberUid", "memberUid:"}
        drinkers_list = []  # type: typing.List[str]
        last_key = None
        count = 0
        for line in lines:
            assert isinstance(line, bytes)
            if line.startswith(b'#'):
                continue
            if not line:
                if cur_entry:
                    # Finished one entry.
                    # Either there is a "dn" entry, or this is the final search result info (last output).
                    assert "dn" in cur_entry or set(cur_entry.keys()) == {"search", "result"}
                    if "uid" in cur_entry:
                        drinker_name = cur_entry["uid"]
                        if not int(cur_entry.get("shadowExpire", "0")) and drinker_name not in exclude_users:
                            if verbose:
                                pprint(cur_entry)
                            drinkers_list.append(drinker_name)
                            count += 1
                cur_entry = None
                last_key = None
                continue
            line = line.decode("utf8")
            if line.startswith(' '):
                assert cur_entry and last_key
                assert last_key not in multi_values  # just not implemented...
                assert last_key in cur_entry
                cur_entry[last_key] += line[1:]
                continue
            if cur_entry is None:
                cur_entry = {}
            key, value = line.split(": ", 1)
            last_key = key
            if key in multi_values:
                cur_entry.setdefault(key, []).append(value)
            else:
                assert key not in cur_entry, "line: %r" % line
                cur_entry[key] = value
        print("Found %i users (potential drinkers)." % count)
        with open(self.drinkers_list_fn, "w") as f:
            for name in drinkers_list:
                assert "\n" not in name
                f.write("%s\n" % name)
        self.drinker_names = drinkers_list
