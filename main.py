#!/usr/bin/env python3

import better_exchook
import argparse
import sys
from db import Db
from utils import init_ipython_kernel, enable_debug_threads
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    import gui


app = None  # type: Optional[gui.KioskApp]
db = None  # type: Optional[Db]


def reload():
    """
    Full reload of the DB, and then also the GUI.
    """
    db.reload()
    app.reload()


def exit_async():
    import _thread

    _thread.interrupt_main()


def main():
    global app, db
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--db", required=True, help="path to database")
    arg_parser.add_argument("--update-drinkers-list", action="store_true")
    arg_parser.add_argument("--debug", action="store_true")
    arg_parser.add_argument("--readonly", action="store_true", help="do not write to DB")
    arg_parser.add_argument('kivy_args', nargs='*', help="use -- to separate the Kivy args")
    args = arg_parser.parse_args()

    if args.debug:
        enable_debug_threads()

    db = Db(path=args.db)

    if args.readonly:
        db.read_only = True

    if args.update_drinkers_list:
        print("Update drinkers list.")
        db.update_drinkers_list(verbose=True)
        print("Quit.")
        return

    # Always update.
    db.update_drinkers_list()

    # Kivy always parses sys.argv.
    sys.argv = sys.argv[:1] + args.kivy_args
    # Do not globally import, as it has side effects.
    import kivy
    kivy.require("1.10.0")
    from gui import KioskApp, kill_at_night
    kill_at_night()  # maybe make configurable...
    app = KioskApp(db=db)
    db.update_drinker_callbacks.append(app.reload)
    init_ipython_kernel(
        user_ns={"db": db, "app": app, "reload": reload, "exit_": exit_async},
        config_path="%s/config" % db.path,
        debug_connection_filename=args.debug)
    try:
        app.run()
    except KeyboardInterrupt:
        print("KeyboardInterrupt")
    finally:
        db.at_exit()
    print("Kiosk quit.")


if __name__ == '__main__':
    better_exchook.install()
    main()
