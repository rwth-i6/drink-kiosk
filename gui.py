
import sys
from threading import Thread
import time
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
import threading
from threading import Condition
from db import Db, BuyItem
from kivy.clock import Clock
from concurrent.futures import Future


# noinspection PyPep8Naming
class run_in_mainthread_blocking:
    def __init__(self):
        pass

    def __call__(self, func):
        def wrapped_func(*args, **kwargs):
            if threading.current_thread() is threading.main_thread():
                return func(*args, **kwargs)

            cond = Condition()
            future = Future()

            def callback_func(dt):
                try:
                    res = func(*args, **kwargs)
                    with cond:
                        future.set_result(res)
                        cond.notify()
                except Exception as exc:
                    with cond:
                        future.set_exception(exc)
                        cond.notify()
                finally:
                    with cond:
                        if not future.done():
                            future.cancel()
                            cond.notify()

            with cond:
                Clock.schedule_once(callback_func, 0)
                cond.wait()
                assert future.done()
                if future.cancelled():
                    raise Exception("did not execute func %s" % func)
                if future.exception():
                    raise future.exception()
                return future.result()

        return wrapped_func


class Setter:
    def __init__(self, obj, attrib):
        self.obj = obj
        self.attrib = attrib

    def __call__(self, instance, value):
        setattr(self.obj, self.attrib, value)


def kill_at_night(night_hours_range=(3, 4), min_runtime_hours=12):
    """
    :param (int|float,int|float) night_hours_range: start/end. 0 <= start < end <= 24.
        E.g. (3,4) means it will get killed only between 3AM and 4AM.
    :param int|float min_runtime_hours: it will not get killed if current runtime is less
    """
    def do_kill_me_now_at_night(dt):
        print("It's late, good night.")
        sys.exit()

    assert len(night_hours_range) == 2 and 0 <= night_hours_range[0] < night_hours_range[1] <= 24
    min_runtime_seconds = min_runtime_hours * 60 * 60

    class KillAtNightTimerThread(Thread):
        def __init__(self):
            super(KillAtNightTimerThread, self).__init__(name=self.__class__.__name__, daemon=True)
            self.start()

        def run(self):
            cur_runtime = 0.0
            sleep_time = 10.0  # this is enough resolution
            while True:
                time.sleep(sleep_time)
                cur_runtime += sleep_time
                if cur_runtime > min_runtime_seconds:
                    cur_time = time.localtime()
                    cur_time_hours = cur_time.tm_hour + cur_time.tm_min / 60. + cur_time.tm_sec / 60. / 60.
                    if night_hours_range[0] <= cur_time_hours <= night_hours_range[1]:
                        Clock.schedule_once(do_kill_me_now_at_night, 0)

    KillAtNightTimerThread()


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
            button = Button(text="%s ..." % drink.shown_name, font_size="12sp")
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
        print("GUI: %s asks to drink %s." % (self.name, drink.intern_name))
        popup = Popup(
            title='Confirm: %s: Buy %s?' % (self.name, drink.shown_name),
            content=Button(
                text='[size=35]%s[/size]\nwants to drink [b]%s[/b] for %s %s.' % (
                    self.name, drink.shown_name, drink.price, self.db.currency),
                markup=True, halign="center"),
            size_hint=(0.7, 0.3))

        class Handlers:
            confirmed = False

        def on_confirmed(*args):
            # It could be that the GUI was hanging, and the user clicked multiple times on it,
            # and this gets executed multiple times.
            if not Handlers.confirmed:
                Handlers.confirmed = True
                updated_drinker = self.db.drinker_buy_item(drinker_name=self.name, item_name=drink.intern_name)
                self._load(updated_drinker)
            popup.dismiss()

        def on_dismissed(sself, *args):
            if not Handlers.confirmed:
                print("GUI: cancelled: %s asks to drink %s." % (self.name, drink.intern_name))

        popup.content.bind(on_press=on_confirmed)
        popup.bind(on_dismiss=on_dismissed)
        popup.open()

    @run_in_mainthread_blocking()
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

    @run_in_mainthread_blocking()
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

    @run_in_mainthread_blocking()
    def update_all(self):
        self.layout.clear_widgets()
        for drinker_name in sorted(self.db.get_drinker_names()):
            self.layout.add_widget(DrinkerWidget(db=self.db, name=drinker_name, size_hint_y=None, height=30))

    @run_in_mainthread_blocking()
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

    @run_in_mainthread_blocking()
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
