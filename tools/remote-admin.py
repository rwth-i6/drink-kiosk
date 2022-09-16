#!/usr/bin/env python3

import os
import sys
import argparse
import readline
import ast
import typing
from typing import Dict
from decimal import Decimal
from subprocess import Popen, PIPE, CalledProcessError


main_dir = os.path.dirname(os.path.dirname(os.path.abspath(os.path.realpath(__file__))))


def main_func():
    arg_parser = argparse.ArgumentParser(description="Attach remotely to main app, and run admin commands.")
    arg_parser.add_argument("--kernel", default="kernel.json", help="IPython/Jupyter kernel.json from main app")
    args = arg_parser.parse_args()
    main = Main(kernel_fn=args.kernel)
    main.run()


class Main:
    def __init__(self, kernel_fn):
        """
        :param str kernel_fn: "kernel.json"
        """
        if not kernel_fn.startswith("/"):
            kernel_fn = os.path.normpath("%s/%s" % (main_dir, kernel_fn))
        assert os.path.exists(kernel_fn), "kernel.json not found: %s" % (kernel_fn,)
        self.kernel_fn = kernel_fn

        # Get DB-path, mostly as a check.
        db_path = self._remote_exec("db.path")
        db_path = ast.literal_eval(db_path)
        assert isinstance(db_path, str)
        if not db_path.startswith("/"):
            db_path = os.path.normpath("%s/%s" % (main_dir, db_path))
        assert os.path.exists(db_path)
        self.db_path = db_path

        drinkers_credit_balances_str = self._remote_exec("db.get_drinkers_credit_balances_formatted()")
        drinkers_credit_balances_str = ast.literal_eval(drinkers_credit_balances_str)
        assert isinstance(drinkers_credit_balances_str, str)
        print("Drinkers credit balances:")
        print(drinkers_credit_balances_str)
        self.drinker_names_all_in_db = sorted(_parse_drinkers_with_credit_balance(drinkers_credit_balances_str).keys())

        # those in GUI, active user
        self.drinker_names_active = ast.literal_eval(self._remote_exec("db.get_drinker_names()"))
        assert isinstance(self.drinker_names_active, list)
        if not set(self.drinker_names_active).issubset(set(self.drinker_names_all_in_db)):
            err_msg = ["Active drinkers not in DB:"]
            for drinker_name in self.drinker_names_active:
                if drinker_name not in self.drinker_names_all_in_db:
                    err_msg.append("  %s" % drinker_name)
            raise Exception("\n".join(err_msg))

        buy_items_str = self._remote_exec("sorted(db.get_buy_items_by_intern_name().keys())")
        buy_items = ast.literal_eval(buy_items_str)
        assert isinstance(buy_items, list) and buy_items and isinstance(buy_items[0], str)
        self.buy_items = buy_items  # type: typing.List[str]

        self._cmd_arg_drinker = CmdArg("<name>", self._parse_drinker_name, self.drinker_names_all_in_db)
        self._cmd_arg_money_amount = CmdArg("<money-amount>", self._parse_money_amount)
        self._cmd_arg_purchase = CmdArg("<purchase>", self._parse_purchase)
        self._cmd_arg_item_amount = CmdArg("<item-amount>", self._parse_item_amount)
        self._cmd_arg_item = CmdArg("<item>", self._parse_item, self.buy_items)
        self.available_cmds = {
            "drinker_pay": Cmd(
                [self._cmd_arg_drinker, self._cmd_arg_money_amount], self.drinker_pay,
                "drinker pays money to the admin"),
            "drinker_buy_item": Cmd(
                [self._cmd_arg_drinker, self._cmd_arg_item, self._cmd_arg_item_amount], self.drinker_buy_item,
                "drinker can buy some drink (or undo that, by giving negative amount)"),
            "drinker_state": Cmd([self._cmd_arg_drinker], self.drinker_state),
            "admin_pay": Cmd(
                [self._cmd_arg_drinker, self._cmd_arg_purchase, self._cmd_arg_money_amount], self.admin_pay,
                "admin will give money <amount> to the user (because the user bought sth)"),
            "admin_set_cash_position": Cmd(
                [self._cmd_arg_money_amount], self.admin_set_cash_position, "overwrite after manual counting"),
            "admin_state": Cmd([], self.admin_state),
            "drinker_delete_inactive_non_neg_balance": Cmd(
                [], self.drinker_delete_inactive_non_neg_balance,
                "Delete inactive users with non-negative balance. Shows list first and asks for confirmation."),
            "help": Cmd([], self.help),
            "exit": Cmd([], self.exit)}
        self.readline_completer = ReadlineCompleter(main=self, prompt="Command: ")

        # readline can be implemented using GNU readline or libedit
        # which have different configuration syntax
        if 'libedit' in readline.__doc__:
            readline.parse_and_bind('bind ^I rl_complete')
        else:
            readline.parse_and_bind('tab: complete')

    def _parse_drinker_name(self, arg):
        """
        :param str arg:
        :rtype: str
        """
        if arg not in self.drinker_names_all_in_db:
            raise Exception("invalid user name %r" % arg)
        return arg

    def _parse_money_amount(self, arg):
        """
        :param str arg:
        :rtype: Decimal
        """
        try:
            amount = Decimal(arg)
        except Exception as exc:
            raise Exception("invalid money amount %r: %s" % (arg, exc))
        return amount

    def _parse_purchase(self, arg):
        """
        :param str arg: any text description
        :rtype: str
        """
        arg = arg.strip()
        assert arg, "provide some text for the purchase"
        return arg

    def _parse_item(self, arg):
        """
        :param str arg:
        :rtype: str
        """
        arg = arg.strip()
        assert arg in self.buy_items, (
            "invalid drink buy item name %r. valid names: %r" % (arg, self.buy_items))
        return arg

    def _parse_item_amount(self, arg):
        """
        :param str arg:
        :rtype: int
        """
        try:
            amount = int(arg)
        except Exception as exc:
            raise Exception("invalid item amount %r: %s" % (arg, exc))
        return amount

    def _remote_exec(self, cmd_str):
        """
        :param str cmd_str: Python code
        :return: output (Python repr)
        :rtype: str
        """
        try:
            return sysexec_out("jupyter", "run", "--existing", self.kernel_fn, stdin=cmd_str)
        except CalledProcessError as exc:
            print("CalledProcessError:", exc)
            sys.exit(1)

    def drinker_pay(self, name, amount):
        """
        :param str name:
        :param Decimal amount:
        """
        assert name in self.drinker_names_all_in_db, "User %r does not seem to exist." % name

        state_str = self._remote_exec("db.drinker_pay(%r, %r)" % (name, str(amount)))
        print(state_str)

        run_posthook(
            "%s/config/remote_drinker_pay_posthook.py" % self.db_path,
            {"name": name, "amount": amount, "state_str": state_str})

    def drinker_buy_item(self, name, item_name, amount):
        """
        :param str name:
        :param str item_name:
        :param int amount:
        """
        assert name in self.drinker_names_all_in_db, "User %r does not seem to exist." % name

        state_str = self._remote_exec("db.drinker_buy_item(%r, %r, %r)" % (name, item_name, amount))
        print(state_str)

    def drinker_state(self, name):
        """
        :param str name:
        """
        assert name in self.drinker_names_all_in_db, "User %r does not seem to exist." % name
        state_str = self._remote_exec("db.get_drinker(%r)" % (name,))
        print(state_str)

    def admin_pay(self, name, purchase, amount):
        """
        :param str name:
        :param str purchase:
        :param Decimal amount:
        """
        assert name in self.drinker_names_all_in_db, "User %r does not seem to exist." % name
        state_str = self._remote_exec("db.admin_pay(%r, %r, %r)" % (name, purchase, str(amount)))
        state_str = ast.literal_eval(state_str)
        print(state_str)

    def admin_set_cash_position(self, amount):
        """
        :param Decimal amount:
        """
        state_str = self._remote_exec("db.admin_set_cash_position(%r)" % (str(amount),))
        state_str = ast.literal_eval(state_str)
        print(state_str)

    def admin_state(self):
        state_str = self._remote_exec("db.get_admin_state_formatted()")
        state_str = ast.literal_eval(state_str)
        print(state_str)

    def drinker_delete_inactive_non_neg_balance(self):
        s = self._remote_exec("db.get_drinker_inactive_and_non_neg_balance_formatted()")
        s = ast.literal_eval(s)
        print("Inactive users with non-negative balance:")
        print(s)
        drinkers = sorted(_parse_drinkers_with_credit_balance(s).keys())
        if not drinkers:
            print("(None)")
            return
        answer = input("Delete these users? (y/N)")
        if not answer or answer.lower() == "n":
            print("Not deleting.")
            return
        if answer.lower() != "y":
            print("Invalid answer %r. Not deleting." % answer)
            return
        self._remote_exec("db.drinkers_delete(%r)" % (drinkers,))
        print("Deleted.")

    def help(self):
        print("Available commands:")
        for cmd_name, cmd in self.available_cmds.items():
            print("  %s %s" % (cmd_name, cmd.full_help_str))

    # noinspection PyMethodMayBeStatic
    def exit(self):
        sys.exit(0)

    def run(self):
        self.help()
        while True:
            # Also see module `rlcompleter`.
            readline.set_completer(self.readline_completer.complete)
            readline.set_completion_display_matches_hook(self.readline_completer.match_display_hook)
            readline.set_completer_delims(' ')
            try:
                while True:
                    cmd_line = input(self.readline_completer.prompt)
                    if cmd_line:
                        break
            except KeyboardInterrupt:
                print("KeyboardInterrupt")
                sys.exit(0)
            except EOFError:
                print("EOFError")
                sys.exit(0)
            finally:
                readline.set_completer(None)
            args = cmd_line.split()
            if not cmd_line.strip() or not args:
                continue
            cmd_name, args = args[0], args[1:]
            if cmd_name not in self.available_cmds:
                print("Invalid command: %r" % cmd_name)
                continue
            cmd = self.available_cmds[cmd_name]
            if len(args) != len(cmd.args):
                print("%s: requires %i arguments (%s), got %i (%s)." % (
                    cmd_name, len(cmd.args), cmd.args_help, len(args), " ".join(args)))
                continue
            parsed_args = []
            for i in range(len(args)):
                arg = args[i]
                try:
                    parsed_args.append(cmd.args[i].parser(arg))
                except Exception as exc:
                    print("%s: invalid argument %i (%r): %s" % (cmd_name, i + 1, arg, exc))
                    break
            if len(parsed_args) != len(args):
                continue
            cmd.func(*parsed_args)
            print("-" * 40)


class ReadlineCompleter:
    def __init__(self, main, prompt):
        """
        :param Main main:
        :param str prompt:
        """
        self.prompt = prompt
        self.main = main
        self._matches = None

    def complete(self, text, state):
        """
        Return the next possible completion for 'text'.

        This is called successively with state == 0, 1, 2, ... until it
        returns None.  The completion should begin with 'text'.

        :param str text:
        :param int state: current item
        :rtype: str|None
        """
        cur_line = readline.get_line_buffer()

        if state == 0:
            self._matches = []  # first reset. might be set again below
            args = cur_line.split()
            if cur_line.endswith(" "):
                args.append("")
            if len(args) == 1:  # cmd itself, partial
                cmd_partial = args[0]
                matches = []
                for available_cmd in self.main.available_cmds:
                    if available_cmd.startswith(cmd_partial):
                        matches.append(available_cmd + " ")
                self._matches = matches
            elif len(args) >= 2:
                cmd_name, args = args[0], args[1:]
                cmd = self.main.available_cmds.get(cmd_name, None)
                if cmd and len(args) <= len(cmd.args):
                    assert len(args) >= 1
                    arg_idx = len(args) - 1
                    last_arg = args[-1]
                    matches = []
                    for arg_choice in cmd.args[arg_idx].choices:
                        if arg_choice.startswith(last_arg):
                            matches.append(arg_choice + " ")
                    self._matches = matches

        try:
            return self._matches[state]
        except IndexError:
            return None

    def match_display_hook(self, substitution, matches, longest_match_length):
        print()
        print("  Choose from: %s" % " ".join([m.strip() for m in matches]))
        print(self.prompt + readline.get_line_buffer(), end="")
        sys.stdout.flush()
        readline.redisplay()


class CmdArg:
    def __init__(self, help_name, parser, choices=()):
        """
        :param str help_name:
        :param (str)->object parser:
        :param typing.Iterable[str] choices:
        """
        self.help_name = help_name
        self.parser = parser
        self.choices = choices


class Cmd:
    def __init__(self, args, func, help_str=None):
        """
        :param list[CmdArg] args:
        :param function func:
        :param str|None help_str:
        """
        self.args = args
        self.func = func
        self.help_str = help_str

    @property
    def args_help(self):
        return " ".join([arg.help_name for arg in self.args])

    @property
    def full_help_str(self):
        if self.help_str:
            return "%s -- %s" % (self.args_help, self.help_str)
        return self.args_help


def sysexec_out(*args, **kwargs):
    """
    :param str args: for Popen
    :param kwargs: for Popen
    :return: stdout
    :rtype: str
    """
    if "stdin" in kwargs:
        stdin_bytes = kwargs.pop("stdin")
        if isinstance(stdin_bytes, str):
            stdin_bytes = stdin_bytes.encode("utf8")
    else:
        stdin_bytes = None
    p = Popen(args, shell=False, stdin=PIPE if stdin_bytes is not None else None, stdout=PIPE, **kwargs)
    out, _ = p.communicate(stdin_bytes)
    if p.returncode != 0:
        raise CalledProcessError(p.returncode, args)
    out = out.decode("utf-8")
    return out


def run_posthook(posthook_fn, user_ns):
    """
    :param str posthook_fn:
    :param dict[str] user_ns:
    """
    if os.path.exists(posthook_fn):
        co = compile(open(posthook_fn).read(), posthook_fn, "exec")
        eval(co, user_ns)


def _parse_drinkers_with_credit_balance(s: str) -> Dict[str, Decimal]:
    out = {}
    for line in s.splitlines():
        drinker_name, credit_balance_str = line.split(":", 2)
        credit_balance = Decimal(credit_balance_str)
        out[drinker_name] = credit_balance
    return out


if __name__ == '__main__':
    import better_exchook
    better_exchook.install()
    main_func()
