#!/usr/bin/env python3

import better_exchook
import argparse
import sys
from db import Db
from utils import init_ipython_kernel


app = None
db = None  # type: Db


def reload():
    db.reload()
    app.reload()


def main():
    global app, db
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--db", required=True, help="path to database")
    arg_parser.add_argument("--update-drinkers-list", action="store_true")
    arg_parser.add_argument('kivy_args', nargs='*', help="use -- to separate the Kivy args")
    args = arg_parser.parse_args()
    db = Db(path=args.db)
    if args.update_drinkers_list:
        print("Update drinkers list.")
        db.update_drinkers_list(verbose=True)
        print("Quit.")
        return

    # TODO fix this...
    # init_ipython_kernel()

    # Always update.
    db.update_drinkers_list()
    db.save_all_drinkers()

    # Kivy always parses sys.argv.
    sys.argv = sys.argv[:1] + args.kivy_args
    # Do not globally import, as it has side effects.
    import kivy
    kivy.require("1.10.0")
    from gui import KioskApp
    app = KioskApp(db=db)
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    main()
