#!/usr/bin/env python3

import better_exchook
import argparse
import os
from decimal import Decimal
from pprint import pprint
import subprocess
import typing
import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
# noinspection PyUnresolvedReferences
from kivy.graphics import Color, Rectangle
from kivy.uix.scrollview import ScrollView


class BuyItem:
    def __init__(self, name, price):
        """
        :param str name:
        :param Decimal|str|float|int price:
        """
        self.name = name
        self.price = Decimal(price)


class Drinker:
    def __init__(self, name, credit_balance, buy_item_counts):
        """
        :param str name:
        :param Decimal credit_balance:
        :param dict[str,int] buy_item_counts:
        """
        self.name = name
        self.credit_balance = credit_balance
        self.buy_item_counts = buy_item_counts


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
        self.buy_items = {
            item.name: item
            for item in [
                BuyItem("Wasser", 1),
                BuyItem("Cola|Malz", 1),
                BuyItem("...", 1),
                BuyItem("Kaffee|...", "0.24")]}

    def get_drinker_names(self):
        """
        :rtype: list[str]
        """
        return self.drinker_names

    def get_buy_items(self):
        """
        :rtype: dict[str,BuyItem]
        """
        return self.buy_items

    def update_drinkers_list(self):
        """
        This has to run where LDAP is correctly configured.
        """
        ldap_cmd_fn = "%s/config/ldap-opts.txt" % self.path
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
        print("Found %i users." % count)
        with open(self.drinkers_list_fn, "w") as f:
            for name in drinkers_list:
                assert "\n" not in name
                f.write("%s\n" % name)
        self.drinker_names = drinkers_list


class Setter:
    def __init__(self, obj, attrib):
        self.obj = obj
        self.attrib = attrib

    def __call__(self, instance, value):
        setattr(self.obj, self.attrib, value)


class DrinkerWidget(BoxLayout):
    def __init__(self, name, **kwargs):
        """
        :param str name:
        """
        super(DrinkerWidget, self).__init__(spacing=4, orientation="horizontal", **kwargs)
        # White background
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.add_widget(Label(text=name, color=(0, 0, 0, 1)))
        self.add_widget(Button(text="+", width=40, size_hint_x=None))
        self.add_widget(Button(text="-", width=40, size_hint_x=None))
        self.bind(size=Setter(self.rect, "size"), pos=Setter(self.rect, "pos"))


class DrinkersListWidget(ScrollView):
    def __init__(self, db, **kwargs):
        """
        :param Db db:
        """
        # https://kivy.org/doc/stable/api-kivy.uix.scrollview.html
        # Window resize recursion error while using ScrollView? https://github.com/kivy/kivy/issues/5638
        # size_hint=(1, None) correct? size_hint=(1, 1) is default.
        # self.parent.bind(size=self.setter("size")), once the parent assigned?
        super(DrinkersListWidget, self).__init__(**kwargs)
        self.db = db
        self.layout = GridLayout(cols=1, spacing=2, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        self.layout.bind(minimum_height=self.layout.setter('height'))
        self.add_widget(self.layout)
        self.update()

    def update(self):
        self.layout.clear_widgets()
        for drinker_name in sorted(self.db.get_drinker_names()):
            self.layout.add_widget(DrinkerWidget(name=drinker_name, size_hint_y=None, height=30))


class KioskApp(App):
    def __init__(self, db):
        """
        :param Db db:
        """
        self.db = db
        super(KioskApp, self).__init__()

    def build(self):
        return DrinkersListWidget(db=self.db)

    def on_start(self):
        pass


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--db", required=True, help="path to database")
    arg_parser.add_argument("--update-drinkers-list", action="store_true")
    args = arg_parser.parse_args()
    db = Db(path=args.db)
    if args.update_drinkers_list:
        print("Update drinkers list.")
        db.update_drinkers_list()
        print("Quit.")
        return

    kivy.require("1.10.0")
    app = KioskApp(db=db)
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    main()
