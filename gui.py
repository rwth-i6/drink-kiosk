
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
from kivy.uix.popup import Popup
from threading import Thread
from db import Db, BuyItem


class Setter:
    def __init__(self, obj, attrib):
        self.obj = obj
        self.attrib = attrib

    def __call__(self, instance, value):
        setattr(self.obj, self.attrib, value)


class DrinkerWidget(BoxLayout):
    def __init__(self, db, name, **kwargs):
        """
        :param Db db:
        :param str name:
        """
        super(DrinkerWidget, self).__init__(spacing=4, orientation="horizontal", **kwargs)
        self.db = db
        self.name = name
        # White background
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.add_widget(Label(text=name, color=(0, 0, 0, 1)))
        self.credit_balance_label = Label(text="... %s" % self.db.currency, color=(0, 0, 0, 1))
        self.add_widget(self.credit_balance_label)
        self.drink_buttons = {}  # type: typing.Dict[str,Button]  # by drink intern name
        for drink in self.db.get_buy_items():
            # Add width=40, size_hint_x=None if fixed width.
            button = Button(text="%s ..." % drink.shown_name)
            button.bind(
                on_release=lambda btn, _drink=drink: self._on_drink_button_click(_drink, btn))
            self.add_widget(button)
            self.drink_buttons[drink.intern_name] = button
        self.bind(size=Setter(self.rect, "size"), pos=Setter(self.rect, "pos"))
        # in background? Thread(target=self._load, daemon=True).start()
        self._load()

    def _on_drink_button_click(self, drink, button):
        """
        :param BuyItem drink:
        :param Button button:
        """
        popup = Popup(
            title='Confirm: %s: Buy %s?' % (self.name, drink.shown_name),
            content=Button(text='%s wants to drink %s for %s %s.' % (
                self.name, drink.shown_name, drink.price, self.db.currency)),
            size_hint=(0.7, 0.3))

        def confirmed(*args):
            popup.dismiss()
            updated_drinker = self.db.drinker_buy_item(drinker_name=self.name, item_name=drink.intern_name)
            self._load(updated_drinker)

        popup.content.bind(on_press=confirmed)
        popup.open()

    def _load(self, drinker=None):
        """
        :param Drinker drinker:
        """
        if not drinker:
            drinker = self.db.get_drinker(self.name)
        self.credit_balance_label.text = "%s %s" % (drinker.credit_balance, self.db.currency)
        drinks = self.db.get_buy_items_by_intern_name()
        for intern_drink_name, button in self.drink_buttons.items():
            drink = drinks[intern_drink_name]
            count = drinker.buy_item_counts.get(intern_drink_name, 0)
            button.text = "%s (%s %s): %i" % (drink.shown_name, drink.price, self.db.currency, count)

    def update(self):
        self._load()


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
        self.update_all()

    def update_all(self):
        self.layout.clear_widgets()
        for drinker_name in sorted(self.db.get_drinker_names()):
            self.layout.add_widget(DrinkerWidget(db=self.db, name=drinker_name, size_hint_y=None, height=30))

    def update_drinker(self, drinker_name):
        """
        :param str drinker_name:
        """
        for widget in self.layout.children:
            assert isinstance(widget, DrinkerWidget)
            if widget.name == drinker_name:
                widget.update()
                return
        raise Exception("Unknown drinker: %r" % (drinker_name,))


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

    def reload(self, drinker_name=None):
        """
        :param str|None drinker_name:
        """
        widget = self.root
        assert isinstance(widget, DrinkersListWidget)
        if drinker_name:
            widget.update_drinker(drinker_name=drinker_name)
        else:
            widget.update_all()
