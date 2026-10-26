"""Native GTK3 + WebKitGTK shell for Tyrion; reuses system libraries."""
import gi
gi.require_version("Gtk","3.0")
gi.require_version("WebKit2","4.1")
from gi.repository import Gtk, GdkPixbuf, WebKit2
from . import core

URL="http://127.0.0.1:17877/"
class Desktop(Gtk.Window):
    def __init__(self):
        super().__init__(title="Tyrion — The Hand")
        self.set_default_size(1370,880)
        self.set_size_request(850,620)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("destroy",Gtk.main_quit)
        try:
            pixbuf=GdkPixbuf.Pixbuf.new_from_file_at_scale(str(core.ROOT/"static"/"seal.svg"),128,128,True)
            self.set_icon(pixbuf)
        except Exception:pass
        self.web=WebKit2.WebView()
        settings=self.web.get_settings()
        settings.set_property("enable-developer-extras",False)
        settings.set_property("enable-webgl",False)
        self.web.connect("decide-policy",self.decide)
        self.add(self.web)
        self.web.load_uri(URL)
        self.show_all()

    def decide(self,web,decision,kind):
        if kind==WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            uri=decision.get_navigation_action().get_request().get_uri()
            if not uri.startswith(URL):
                decision.ignore()
                return True
        return False

def main():
    Desktop()
    Gtk.main()

if __name__=="__main__":main()
