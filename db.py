
import typing
import sys
import os
from decimal import Decimal
import subprocess
from pprint import pprint
from threading import RLock, Thread, Condition
from utils import better_repr, is_git_dir, time_stamp
import better_exchook
import time


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
    def __init__(self, name, credit_balance=0, buy_item_counts=None, total_buy_item_counts=None):
        """
        :param str name:
        :param Decimal|str|int credit_balance:
        :param dict[str,int] buy_item_counts:
        :param dict[str,int] total_buy_item_counts:
        """
        self.name = name
        self.credit_balance = Decimal(credit_balance)
        self.buy_item_counts = buy_item_counts or {}  # type: typing.Dict[str,int]
        self.total_buy_item_counts = total_buy_item_counts or {}  # type: typing.Dict[str,int]
        if self.buy_item_counts and not self.total_buy_item_counts:
            self.total_buy_item_counts = self.buy_item_counts.copy()

    def __repr__(self):
        attribs = ["name", "credit_balance", "buy_item_counts", "total_buy_item_counts"]
        return "%s(\n%s)" % (
            self.__class__.__name__,
            ",\n".join(["%s=%s" % (attr, better_repr(getattr(self, attr))) for attr in attribs]))


class AdminCashPosition:
    DbFilePath = "admin-cash-position.txt"

    def __init__(self, cash_position=0, purchases=None):
        """
        :param Decimal|str|int cash_position:
        :param list[(str,str,Decimal)] purchases:
        """
        self.cash_position = Decimal(cash_position)
        if purchases is None:
            purchases = []
        self.purchases = purchases

    def pay_purchase(self, user_name, item_name, money_amount):
        """
        :param str user_name:
        :param str item_name:
        :param Decimal money_amount:
        """
        assert isinstance(user_name, str) and isinstance(item_name, str)
        money_amount = Decimal(money_amount)
        self.purchases.append((user_name, item_name, money_amount))
        self.cash_position -= money_amount

    def __repr__(self):
        attribs = ["cash_position", "purchases"]
        return "%s(\n%s)" % (
            self.__class__.__name__,
            ",\n".join(["%s=%s" % (attr, better_repr(getattr(self, attr))) for attr in attribs]))

    def format(self):
        """
        :return: shortened, formatted, suitable for stdout
        :rtype: str
        """
        purchases_str = []
        if len(self.purchases) > 5:
            purchases_str.append("...")
        purchases_str.extend([", ".join(map(str, purchase)) for purchase in self.purchases])
        return "".join(
            ["purchases:\n"] +
            ["  %s\n" % s for s in purchases_str] +
            ["cash position: %s\n" % self.cash_position])


class _Task(Thread):
    def __init__(self, db, wait_time=None, **kwargs):
        """
        :param Db db:
        :param float|None wait_time:
        """
        super(_Task, self).__init__(name=self.__class__.__name__, **kwargs)
        self.creation_time = time.time()
        self.db = db
        self.wait_time = wait_time
        self.condition = Condition()

    def run(self):
        with self.condition:
            if self.wait_time:
                self.condition.wait(self.wait_time)
        with self.db.lock:
            # noinspection PyBroadException
            try:
                self.do_task()
            except Exception:
                better_exchook.better_exchook(*sys.exc_info())
            finally:
                self.db.tasks.remove(self)

    def skip_wait_time(self):
        with self.condition:
            self.wait_time = None
            self.condition.notify_all()

    def do_task(self):
        raise NotImplementedError

    @property
    def delayed_time(self):
        if getattr(self, "creation_time", None):
            return time.time() - self.creation_time
        return None

    def verbose_existing(self):
        return self.wait_time and self.delayed_time and self.delayed_time >= 0.5

    def __repr__(self):
        return "<%s, wait time %.1f, delayed time %.1f>" % (
            self.__class__.__name__, self.wait_time or 0, self.delayed_time or -1)

    def __hash__(self):
        return hash(id(self))

    def __eq__(self, other):
        return isinstance(other, self.__class__)


class _GitCommitBaseTask(_Task):
    def __init__(self, commit_files, commit_msg, **kwargs):
        """
        :param list[str] commit_files:
        :param str commit_msg:
        """
        super(_GitCommitBaseTask, self).__init__(**kwargs)
        self.commit_files = commit_files
        self.commit_msg = commit_msg

    def do_task(self):
        try:
            cmd = ["git", "add"] + self.commit_files
            print("$ %s" % " ".join(cmd))
            subprocess.check_call(cmd, cwd=self.db.path)
        except subprocess.CalledProcessError as exc:
            print("Git add error:", exc)
        else:
            try:
                cmd = ["git", "commit"] + self.commit_files + ["-m", self.commit_msg]
                print("$ %s" % " ".join(cmd))
                subprocess.check_call(cmd, cwd=self.db.path)
            except subprocess.CalledProcessError as exc:
                print("Git commit error:", exc)


class _GitCommitDrinkersTask(_GitCommitBaseTask):
    def __init__(self, **kwargs):
        super(_GitCommitDrinkersTask, self).__init__(
            commit_files=["drinkers"], commit_msg="drink-kiosk: drinkers update",
            **kwargs)


class _GitCommitAdminCashTask(_GitCommitBaseTask):
    def __init__(self, **kwargs):
        super(_GitCommitAdminCashTask, self).__init__(
            commit_files=[AdminCashPosition.DbFilePath], commit_msg="drink-kiosk: admin-cash-position",
            **kwargs)


class Db:
    read_only = False

    def __init__(self, path):
        """
        :param str path:
        """
        self.path = path
        self.lock = RLock()
        self.drinkers_list_filename = "%s/drinkers/list.txt" % self.path
        self._check_valid_path()
        self.drinker_names = self._open(self.drinkers_list_filename).read().splitlines()
        self.currency = "€"
        self.default_git_commit_wait_time = 60 * 60  # 1h
        self.buy_items = self._load_buy_items()
        self.admin_cash_position = self._load_admin_cash_position()
        self.update_drinker_callbacks = []  # type: typing.List[typing.Callable[[str], None]]
        self.tasks = []  # type: typing.List[_Task]

    def _check_valid_path(self):
        assert os.path.isdir(self.path)
        assert is_git_dir(self.path), "not a Git dir?"

    def _open(self, fn, mode="r"):
        return open(fn, mode)

    def _load_buy_items(self):
        """
        :rtype: list[BuyItem]
        """
        fn = "%s/config/buy_items.txt" % self.path
        s = self._open(fn).read()
        buy_items = eval(s)
        assert isinstance(buy_items, list)
        assert all([isinstance(item, BuyItem) for item in buy_items])
        return buy_items

    def _update_buy_items(self):
        self.buy_items = self._load_buy_items()

    def _load_admin_cash_position(self):
        """
        :rtype: AdminCashPosition
        """
        fn = "%s/%s" % (self.path, AdminCashPosition.DbFilePath)
        if os.path.exists(fn):
            s = self._open(fn).read()
            obj = eval(s)
            assert isinstance(obj, AdminCashPosition)
            return obj
        return AdminCashPosition()

    def get_admin_state_formatted(self):
        """
        :return: admin cash position, shortened, formatted, suitable for stdout
        :rtype: str
        """
        return self.admin_cash_position.format()

    def admin_pay(self, drinker_name, purchase, amount):
        """
        :param str drinker_name:
        :param str purchase: can be any string, does not need to be a buy item from the Db
        :param Decimal amount: money paid (the drinker/user gets this money out from the admin cash)
        :return: new state, via get_admin_state_formatted
        :rtype: str
        """
        with self.lock:
            self.admin_cash_position.pay_purchase(user_name=drinker_name, item_name=purchase, money_amount=amount)
            self._save_admin_cash_position()
            return self.get_admin_state_formatted()

    def admin_set_cash_position(self, cash_position_amount):
        """
        :param Decimal cash_position_amount:
        :return: string describing change
        :rtype: str
        """
        cash_position_amount = Decimal(cash_position_amount)
        with self.lock:
            old = self.admin_cash_position.cash_position
            self.admin_cash_position.cash_position = cash_position_amount
            self._save_admin_cash_position()
            return "admin cash position: old %s -> new %s" % (old, self.admin_cash_position.cash_position)

    def _save_admin_cash_position(self):
        if self.read_only:
            return
        fn = "%s/%s" % (self.path, AdminCashPosition.DbFilePath)
        with self.lock:
            with self._open(fn, "w") as f:
                f.write("%r\n" % self.admin_cash_position)
            self._add_git_commit_admin_cash_task(wait_time=0)  # always save right now

    def _update_admin_cash_position(self):
        self.admin_cash_position = self._load_admin_cash_position()

    def get_drinker_names(self):
        """
        :return: current active drinkers (shown in GUI)
        :rtype: list[str]
        """
        return self.drinker_names

    def get_drinker_names_all_in_db(self):
        """
        :return: all drinkers in the database (not necessarily shown in GUI)
        :rtype: list[str]
        """
        import glob
        return sorted([os.path.basename(fn).rsplit(".", 1)[0] for fn in glob.glob(self._drinker_filename("*"))])

    def get_buy_items(self):
        """
        :rtype: list[BuyItem]
        """
        return self.buy_items

    def get_buy_items_by_intern_name(self):
        """
        :rtype: dict[str,BuyItem]
        """
        return {item.intern_name: item for item in self.get_buy_items()}

    def _get_buy_item_by_intern_name(self, name):
        """
        :param str name:
        :rtype: BuyItem
        """
        items = self.get_buy_items_by_intern_name()
        assert name in items, "Unknown drink/item name %r; known ones: %r" % (name, items)
        return items[name]

    def _drinker_filename(self, drinker_name):
        """
        :param str drinker_name:
        :rtype: str
        """
        return "%s/drinkers/state/%s.txt" % (self.path, drinker_name)

    def get_drinker(self, name, allow_non_existing=False):
        """
        :param str name:
        :param bool allow_non_existing:
        :rtype: Drinker
        """
        drinker_fn = self._drinker_filename(name)
        with self.lock:
            try:
                f = self._open(drinker_fn)
            except FileNotFoundError:
                if not allow_non_existing:
                    from difflib import get_close_matches
                    close_matches = get_close_matches(name, self.get_drinker_names())
                    raise Exception("drinker %r is unknown. close matches: %r" % (name, close_matches))
                drinker = Drinker(name=name)
            else:
                s = f.read()
                drinker = eval(s)
                assert isinstance(drinker, Drinker)
                assert drinker.name == name
        return drinker

    def _save_drinker(self, drinker):
        """
        :param Drinker drinker:
        """
        if self.read_only:
            return
        drinker_fn = self._drinker_filename(drinker.name)
        with self.lock:
            with self._open(drinker_fn, "w") as f:
                f.write("%r\n" % drinker)
            self._add_git_commit_drinkers_task()

    def get_drinkers_credit_balances_formatted(self):
        """
        :return: list of all drinkers credit balances formatted string (suitable for stdout)
        :rtype: str
        """
        out = []
        for drinker_name in sorted(self.get_drinker_names_all_in_db()):
            drinker = self.get_drinker(drinker_name)
            out.append("%s: %s\n" % (drinker_name, drinker.credit_balance))
        return "".join(out)

    def get_drinker_inactive_and_non_neg_balance_formatted(self):
        """
        :return: list of all inactive drinkers with non-negative credit balances formatted string
        :rtype: str
        """
        out = []
        for drinker_name in sorted(self.get_drinker_names_all_in_db()):
            if drinker_name in self.get_drinker_names():
                continue  # still active
            drinker = self.get_drinker(drinker_name)
            if drinker.credit_balance >= 0:
                out.append("%s: %s\n" % (drinker_name, drinker.credit_balance))
        return "".join(out)

    def drinker_buy_item(self, drinker_name, item_name, amount=1):
        """
        :param str drinker_name:
        :param str item_name: intern name
        :param int amount: can be negative, to undo drinks
        :return: updated Drinker
        :rtype: Drinker
        """
        print("%s: %s drinks %s (amount: %i)." % (time_stamp(), drinker_name, item_name, amount))
        assert isinstance(amount, int)
        with self.lock:
            drinker = self.get_drinker(drinker_name)
            item = self._get_buy_item_by_intern_name(item_name)
            drinker.buy_item_counts.setdefault(item_name, 0)
            drinker.buy_item_counts[item_name] += amount
            drinker.total_buy_item_counts.setdefault(item_name, 0)
            drinker.total_buy_item_counts[item_name] += amount
            drinker.credit_balance -= item.price * amount
            self._save_drinker(drinker)
            if amount != 1:
                # We want to have a Git commit right after (after the lock release), so enforce this now.
                self._add_git_commit_drinkers_task(wait_time=0)
        for cb in self.update_drinker_callbacks:
            cb(drinker_name)
        return drinker

    def drinker_pay(self, drinker_name, amount):
        """
        Drinker ``drinker_name`` pays some amount ``amount``.
        This function would be called via RPC somehow.

        :param str drinker_name:
        :param Decimal|int|str amount:
        :return: updated Drinker
        :rtype: Drinker
        """
        amount = Decimal(amount)
        print("%s: %s pays %s %s." % (time_stamp(), drinker_name, amount, self.currency))
        with self.lock:
            drinker = self.get_drinker(drinker_name)
            drinker.credit_balance += amount
            if drinker.credit_balance >= 0:
                # Reset counts in this case.
                drinker.buy_item_counts.clear()
            self._save_drinker(drinker)
            # We want to have a Git commit right after (after the lock release), so enforce this now.
            self._add_git_commit_drinkers_task(wait_time=0)
            self.admin_cash_position.cash_position += amount
            self._save_admin_cash_position()
        for cb in self.update_drinker_callbacks:
            cb(drinker_name)
        return drinker

    def drinkers_delete(self, drinkers):
        """
        Delete the list of inactive drinkers. Only allowed when their credit balance is non-negative.
        (If you would want to delete other drinkers as well, just do that manually in the DB files.)

        :param list[str] drinkers:
        """
        if not drinkers:
            return
        with self.lock:
            self._add_git_commit_drinkers_task(wait_time=0)
            for drinker_name in drinkers:
                if drinker_name in self.get_drinker_names():
                    raise Exception("drinker %r is still active" % drinker_name)
                drinker = self.get_drinker(drinker_name)
                if drinker.credit_balance < 0:
                    raise Exception(
                        "drinker %r has negative credit balance %s" % (drinker_name, drinker.credit_balance))
                os.remove(self._drinker_filename(drinker_name))

    def _save_all_drinkers(self):
        with self.lock:
            # First add Git commit task, such that wait time is 0.
            self._add_git_commit_drinkers_task(wait_time=0)
            for name in self.get_drinker_names():
                drinker = self.get_drinker(name, allow_non_existing=True)
                self._save_drinker(drinker)

    def update_drinkers_list(self, verbose=False):
        """
        Updates drinker list.
        This has to run where LDAP is correctly configured.

        :param bool verbose:
        """
        from pprint import pformat
        ldap_cmd_fn = "%s/config/ldap-opts.txt" % self.path  # example: ldapsearch -x -h <host>
        ldap_cmd = (
            " ".
            join([ln for ln in self._open(ldap_cmd_fn).read().splitlines() if not ln.startswith("#")]).
            strip().split(" "))
        out = subprocess.check_output(ldap_cmd)
        lines = out.splitlines()
        drinkers_exclude_list_fn = "%s/drinkers/exclude_list.txt" % self.path
        exclude_users = set(self._open(drinkers_exclude_list_fn).read().splitlines())
        cur_entry = None  # type: typing.Optional[typing.Dict[str,typing.Union[str,typing.List[str]]]] # key -> value(s)
        multi_values = {"cn", "objectClass", "memberUid", "memberUid:", "description"}
        drinkers_list = []  # type: typing.List[str]
        last_key = None
        cur_line_is_comment, last_line_was_comment = False, False
        count = 0
        for line_num, line in enumerate(lines):
            last_line_was_comment = cur_line_is_comment
            assert isinstance(line, bytes)
            if line.startswith(b'#'):
                cur_line_is_comment = True
                continue
            cur_line_is_comment = False
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
                if last_line_was_comment:
                    cur_line_is_comment = True
                    continue
                assert cur_entry and last_key, "line %i: %s" % (line_num + 1, line)
                assert last_key in cur_entry
                if last_key in multi_values:
                    cur_entry[last_key][-1] += line[1:]
                else:
                    cur_entry[last_key] += line[1:]
                continue
            if cur_entry is None:
                cur_entry = {}
            key, value = line.split(": ", 1)
            last_key = key
            if key in multi_values:
                cur_entry.setdefault(key, []).append(value)
            else:
                assert key not in cur_entry, (
                    "line: %r, key: %r, entry\n%s,\ncmd: %s" % (line, key, pformat(cur_entry), " ".join(ldap_cmd)))
                cur_entry[key] = value
        print("Found %i users (potential drinkers)." % count)
        self.drinker_names = drinkers_list
        with self.lock:
            with self._open(self.drinkers_list_filename, "w") as f:
                for name in drinkers_list:
                    assert "\n" not in name
                    f.write("%s\n" % name)
            self._save_all_drinkers()

    def get_total_buy_item_counts(self):
        """
        :rtype: dict[str,int]
        """
        total_buy_item_counts = {}
        for drinker_name in self.get_drinker_names():
            drinker = self.get_drinker(drinker_name, allow_non_existing=True)
            for key, value in drinker.total_buy_item_counts.items():
                total_buy_item_counts.setdefault(key, 0)
                total_buy_item_counts[key] += value
        return total_buy_item_counts

    def reload(self):
        """
        Reload drinkers, buy items, etc.
        """
        self.update_drinkers_list()
        self._update_buy_items()
        self._update_admin_cash_position()

    def _add_task(self, task):
        """
        :param _Task task:
        """
        with self.lock:
            if task in self.tasks:
                idx = self.tasks.index(task)
                existing_task = self.tasks[idx]
                if existing_task.verbose_existing():  # keep silent if there is no wait time on it
                    print("_Task already exists:", existing_task)
                if existing_task.wait_time and not task.wait_time:
                    print("Requested to skip wait time of task:", existing_task)
                    existing_task.skip_wait_time()
                return
            self.tasks.append(task)
            task.start()

    def _add_git_commit_drinkers_task(self, wait_time=None):
        """
        :param float|None wait_time:
        """
        if self.read_only:
            return
        if wait_time is None:
            wait_time = self.default_git_commit_wait_time
        self._add_task(_GitCommitDrinkersTask(db=self, wait_time=wait_time))

    def _add_git_commit_admin_cash_task(self, wait_time=None):
        """
        :param float|None wait_time:
        """
        if self.read_only:
            return
        if wait_time is None:
            wait_time = self.default_git_commit_wait_time
        self._add_task(_GitCommitAdminCashTask(db=self, wait_time=wait_time))

    def at_exit(self):
        """
        At-exit handler for the DB.
        """
        print("DB at exit handler.")
        while True:
            with self.lock:
                if not self.tasks:
                    break
                task = self.tasks[0]
                print("DB at exit handler: skip task:", task)
                task.skip_wait_time()
            # Outside the lock:
            task.join()


class HistoricDb(Db):
    read_only = True

    def __init__(self, path, git_revision):
        """
        :param str path:
        :param str git_revision:
        """
        try:
            # https://gitpython.readthedocs.io/en/stable/tutorial.html
            import git
        except ImportError:
            print("pip3 install --user GitPython")
            raise
        self.git_mod = git
        self.git_repo = git.Repo(path)
        self.git_commit = self.git_repo.commit(git_revision)
        assert isinstance(self.git_commit, git.Commit)
        self.git_tree = self.git_commit.tree
        assert isinstance(self.git_tree, git.Tree)
        super(HistoricDb, self).__init__(path="")

    def _check_valid_path(self):
        self._open(self.drinkers_list_filename).read()

    def _open(self, fn, mode="r"):
        """
        :param str fn:
        :param str mode:
        """
        assert mode == "r", "only read support for custom file %r" % (fn,)
        assert self.path == "" and fn.startswith("/")  # fn starts with "<path>/"
        fn = fn[1:]
        blob = self.git_tree.join(fn)
        assert isinstance(blob, self.git_mod.Blob)
        from io import TextIOWrapper, BytesIO
        raw_stream = BytesIO(blob.data_stream.read())
        return TextIOWrapper(raw_stream)


def main():
    import better_exchook
    better_exchook.install()
    from argparse import ArgumentParser
    from pprint import pprint
    import time
    arg_parser = ArgumentParser()
    arg_parser.add_argument("--path", required=True, help="path of db")
    arg_parser.add_argument("--rev")
    args = arg_parser.parse_args()
    cur_db = Db(path=args.path)
    old_db = HistoricDb(path=args.path, git_revision=args.rev)
    print(
        "Old DB commit:",
        old_db.git_commit.hexsha[:8], ",",
        time.asctime(time.localtime(old_db.git_commit.authored_date)), ",",
        old_db.git_commit.message.strip())
    cur_drinkers = set(cur_db.get_drinker_names())
    old_drinkers = set(old_db.get_drinker_names())
    print("New drinkers:", cur_drinkers.difference(old_drinkers))
    print("Removed drinkers:", old_drinkers.difference(cur_drinkers))
    cur_total_buy_item_counts = cur_db.get_total_buy_item_counts()
    old_total_buy_item_counts = old_db.get_total_buy_item_counts()
    print("Current DB total buy items counts:")
    pprint(cur_total_buy_item_counts)
    print("Old DB total buy items counts:")
    pprint(old_total_buy_item_counts)
    keys = set(cur_total_buy_item_counts.keys()).union(set(old_total_buy_item_counts.keys()))
    diff_total_buy_item_counts = {
        key: cur_total_buy_item_counts.get(key, 0) - old_total_buy_item_counts.get(key, 0) for key in keys}
    print("Diff total buy items counts:")
    pprint(diff_total_buy_item_counts)


if __name__ == "__main__":
    main()
