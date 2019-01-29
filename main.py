#!/usr/bin/env python3

import better_exchook
import argparse
import kivy
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window


class KioskWidget(Widget):
    pass


class DrinkersListWidget(ScrollView):
    def __init__(self, **kwargs):
        # https://kivy.org/doc/stable/api-kivy.uix.scrollview.html
        # Window resize recursion error while using ScrollView? https://github.com/kivy/kivy/issues/5638
        # size_hint=(1, None) correct? size_hint=(1, 1) is default.
        # self.parent.bind(size=self.setter("size")), once the parent assigned?
        super(DrinkersListWidget, self).__init__(**kwargs)
        layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        layout.bind(minimum_height=layout.setter('height'))
        for i in range(20):
            btn = Button(text=str(i), size_hint_y=None, height=40)
            layout.add_widget(btn)
        self.add_widget(layout)


class KioskApp(App):
    def build(self):
        return DrinkersListWidget()

    def on_start(self):
        pass


def main():
    arg_parser = argparse.ArgumentParser()
    args = arg_parser.parse_args()

    app = KioskApp()
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    kivy.require("1.10.0")
    main()
