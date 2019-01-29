#!/usr/bin/env python3

import better_exchook
import argparse
import os
import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window


class Db:
    def __init__(self, path):
        """
        :param str path:
        """
        assert os.path.isdir(path)
        assert os.path.exists("%s/.git" % path), "not a Git dir?"
        self.path = path
        drinkers_list_fn = "%s/drinkers/list.txt" % path
        self.drinkers = open(drinkers_list_fn).read().splitlines()


class DrinkerWidget(BoxLayout):
    def __init__(self, name, **kwargs):
        """
        :param str name:
        """
        super(DrinkerWidget, self).__init__(spacing=10, orientation="horizontal", **kwargs)
        self.add_widget(Label(text=name))
        self.add_widget(Button(text="+", width=50, size_hint_x=None))
        self.add_widget(Button(text="-", width=50, size_hint_x=None))


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
        layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        layout.bind(minimum_height=layout.setter('height'))
        for i in range(20):
            layout.add_widget(DrinkerWidget(name="drinker %i" % i, size_hint_y=None, height=40))
        self.add_widget(layout)


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
    args = arg_parser.parse_args()
    db = Db(path=args.db)
    app = KioskApp(db=db)
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    kivy.require("1.10.0")
    main()
