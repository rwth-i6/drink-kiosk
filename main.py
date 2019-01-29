#!/usr/bin/env python3

import kivy
from kivy.app import App
from kivy.uix.widget import Widget
import better_exchook
import argparse


class KioskWidget(Widget):
    pass


class KioskApp(App):
    def build(self):
        return KioskWidget()


def main():
    arg_parser = argparse.ArgumentParser()
    args = arg_parser.parse_args()

    app = KioskApp()
    app.run()


if __name__ == '__main__':
    better_exchook.install()
    main()
