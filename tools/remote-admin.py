#!/usr/bin/env python3

import os
import sys
import argparse
import readline
import atexit
import ast
import typing
from decimal import Decimal


main_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    from subprocess import Popen, PIPE, CalledProcessError
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
        :param typing.Container[str] choices:
        """
        self.help_name = help_name
        self.parser = parser
        self.choices = choices


class Cmd:
    def __init__(self, args, func):
        """
        :param list[CmdArg] args:
        :param function func:
        """
        self.args = args
        self.func = func

    @property
    def args_help(self):
        return " ".join([arg.help_name for arg in self.args])


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
        db_path = sysexec_out("jupyter", "run", "--existing", kernel_fn, stdin="db.path")
        db_path = ast.literal_eval(db_path)
        assert isinstance(db_path, str)
        if not db_path.startswith("/"):
            db_path = os.path.normpath("%s/%s" % (main_dir, db_path))
        assert os.path.exists(db_path)
        self.db_path = db_path

        drinkers_credit_balances_str = sysexec_out(
            "jupyter", "run", "--existing", kernel_fn, stdin="db.get_drinkers_credit_balances_formatted()")
        drinkers_credit_balances_str = ast.literal_eval(drinkers_credit_balances_str)
        assert isinstance(drinkers_credit_balances_str, str)
        drinkers_credit_balances = {}  # type: typing.Dict[str,Decimal]
        print("Drinkers credit balances:")
        for line in drinkers_credit_balances_str.splitlines():
            print("  %s" % line)
            drinker_name, credit_balance_str = line.split(":", 2)
            credit_balance = Decimal(credit_balance_str)
            drinkers_credit_balances[drinker_name] = credit_balance
        self.drinker_names = sorted(drinkers_credit_balances.keys())
        self.drinkers_credit_balances = drinkers_credit_balances

        self._cmd_arg_drinker = CmdArg("<name>", self._parse_drinker_name, self.drinker_names)
        self._cmd_arg_amount = CmdArg("<amount>", self._parse_amount)
        self.available_cmds = {
            "drinker_pay": Cmd([self._cmd_arg_drinker, self._cmd_arg_amount], self.drinker_pay),
            "drinker_state": Cmd([self._cmd_arg_drinker], self.drinker_state),
            "exit": Cmd([], self.exit)}
        self.readline_completer = ReadlineCompleter(main=self, prompt="Command: ")

        # readline can be implemented using GNU readline or libedit
        # which have different configuration syntax
        if 'libedit' in readline.__doc__:
            readline.parse_and_bind('bind ^I rl_complete')
        else:
            readline.parse_and_bind('tab: complete')
        # Also see module `rlcompleter`.
        readline.set_completer(self.readline_completer.complete)
        readline.set_completion_display_matches_hook(self.readline_completer.match_display_hook)
        readline.set_completer_delims(' ')
        atexit.register(lambda: readline.set_completer(None))

    def _parse_drinker_name(self, arg):
        """
        :param str arg:
        :rtype: str
        """
        if arg not in self.drinker_names:
            raise Exception("invalid user name %r" % arg)
        return arg

    def _parse_amount(self, arg):
        """
        :param str arg:
        :rtype: Decimal
        """
        try:
            amount = Decimal(arg)
        except Exception as exc:
            raise Exception("invalid amount %r: %s" % (arg, exc))
        return amount

    def drinker_pay(self, name, amount):
        """
        :param str name:
        :param Decimal amount:
        """
        assert name in self.drinker_names, "User %r does not seem to exist." % name

        state_str = sysexec_out(
            "jupyter", "run", "--existing", self.kernel_fn, stdin="db.drinker_pay(%r, %r)" % (name, str(amount)))
        print(state_str)

        run_posthook(
            "%s/config/remote_drinker_pay_posthook.py" % self.db_path,
            {"name": name, "amount": amount, "state_str": state_str})

    def drinker_state(self, name):
        """
        :param str name:
        """
        assert name in self.drinker_names, "User %r does not seem to exist." % name
        state_str = sysexec_out(
            "jupyter", "run", "--existing", self.kernel_fn, stdin="db.get_drinker(%r)" % (name,))
        print(state_str)

    def exit(self):
        sys.exit(0)

    def run(self):
        while True:
            print("Available commands:")
            for cmd_name, cmd in self.available_cmds.items():
                print("  %s %s" % (cmd_name, cmd.args_help))
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


def main_func():
    arg_parser = argparse.ArgumentParser(description="Attach remotely to main app, and run admin commands.")
    arg_parser.add_argument("--kernel", default="kernel.json", help="IPython/Jupyter kernel.json from main app")
    args = arg_parser.parse_args()
    main = Main(kernel_fn=args.kernel)
    main.run()


if __name__ == '__main__':
    import better_exchook
    better_exchook.install()
    main_func()
