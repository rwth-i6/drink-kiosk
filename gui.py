
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
from db import Db


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
