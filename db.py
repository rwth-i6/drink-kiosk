
import typing
import os
from decimal import Decimal
import subprocess
from pprint import pprint
from threading import RLock
from utils import better_repr


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
        :param Decimal|str|int credit_balance:
        :param dict[str,int] buy_item_counts:
        """
        self.name = name
        self.credit_balance = Decimal(credit_balance)
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
        self.lock = RLock()
        self.drinkers_list_fn = "%s/drinkers/list.txt" % path
        self.drinker_names = open(self.drinkers_list_fn).read().splitlines()
        self.currency = "€"
        self.buy_items = self._load_buy_items()

    def _load_buy_items(self):
        """
        :rtype: list[BuyItem]
        """
        fn = "%s/config/buy_items.txt" % self.path
        s = open(fn).read()
        buy_items = eval(s)
        assert isinstance(buy_items, list)
        assert all([isinstance(item, BuyItem) for item in buy_items])
        return buy_items

    def update_buy_items(self):
        self.buy_items = self._load_buy_items()

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

    def get_buy_item_by_intern_name(self, name):
        """
        :param str name:
        :rtype: BuyItem
        """
        return self.get_buy_items_by_intern_name()[name]

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
        with self.lock:
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
        with self.lock:
            with open(drinker_fn, "w") as f:
                f.write("%r\n" % drinker)

    def drinker_buy_item(self, drinker_name, item_name):
        """
        :param str drinker_name:
        :param str item_name: intern name
        :return: updated Drinker
        :rtype: Drinker
        """
        print("%s drinks %s." % (drinker_name, item_name))
        with self.lock:
            drinker = self.get_drinker(drinker_name)
            item = self.get_buy_item_by_intern_name(item_name)
            drinker.buy_item_counts.setdefault(item_name, 0)
            drinker.buy_item_counts[item_name] += 1
            drinker.credit_balance -= item.price
            self.save_drinker(drinker)
            return drinker

    def drinker_pay(self, drinker_name, amount):
        """
        This function would be called via RPC somehow.

        :param str drinker_name:
        :param Decimal|int|str amount:
        :return: updated Drinker
        :rtype: Drinker
        """
        amount = Decimal(amount)
        print("%s pays %s %s." % (drinker_name, amount, self.currency))
        with self.lock:
            drinker = self.get_drinker(drinker_name)
            drinker.credit_balance += amount
            if drinker.credit_balance >= 0:
                # Reset counts in this case.
                drinker.buy_item_counts.clear()
            self.save_drinker(drinker)
            return drinker

    def save_all_drinkers(self):
        for name in self.get_drinker_names():
            drinker = self.get_drinker(name)
            self.save_drinker(drinker)

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
        with self.lock:
            with open(self.drinkers_list_fn, "w") as f:
                for name in drinkers_list:
                    assert "\n" not in name
                    f.write("%s\n" % name)
        self.drinker_names = drinkers_list

    def reload(self):
        self.update_drinkers_list()
        self.save_all_drinkers()
        self.update_buy_items()
