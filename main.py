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
from kivy.app import runTouchApp


class KioskWidget(Widget):
    pass


class KioskApp(App):
    def build(self):
        # https://kivy.org/doc/stable/api-kivy.uix.scrollview.html
        layout = GridLayout(cols=1, spacing=10, size_hint_y=None)
        # Make sure the height is such that there is something to scroll.
        layout.bind(minimum_height=layout.setter('height'))
        for i in range(100):
            btn = Button(text=str(i), size_hint_y=None, height=40)
            layout.add_widget(btn)
        root = ScrollView(size_hint=(1, None), size=(Window.width, Window.height))
        root.add_widget(layout)
        return root
        #return KioskWidget()


def main():
    arg_parser = argparse.ArgumentParser()
    args = arg_parser.parse_args()

    app = KioskApp()
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    main()
