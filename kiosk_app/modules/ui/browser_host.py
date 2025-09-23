from typing import Optional

from modules.qt import Qt, QtGui, QtWidgets, QtWebEngineWidgets

QMovie = QtGui.QMovie
QWidget = QtWidgets.QWidget
QStackedLayout = QtWidgets.QStackedLayout
QLabel = QtWidgets.QLabel
QWebEngineView = QtWebEngineWidgets.QWebEngineView

from modules.utils.i18n import tr, i18n


class BrowserHostWidget(QWidget):
    """Container fuer Browser mit Platzhalter. Index 0 = Placeholder, 1 = WebView."""
    def __init__(self, placeholder_enabled: bool = False, gif_path: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._placeholder_enabled = placeholder_enabled
        self._gif_path = gif_path
        self._view: Optional[QWebEngineView] = None

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(0)

        self.placeholder = QLabel("", self)
        self.placeholder.setAlignment(Qt.AlignCenter)

        self.movie: Optional[QMovie] = None
        if gif_path:
            try:
                self.movie = QMovie(gif_path)
                if self.movie.isValid():
                    self.placeholder.setMovie(self.movie)
                    self.movie.start()
            except Exception:
                self.movie = None

        self.stack.addWidget(self.placeholder)
        dummy = QWidget(self)  # wird spaeter ersetzt
        self.stack.addWidget(dummy)
        self.stack.setCurrentIndex(0 if self._placeholder_enabled else 1)

        i18n.language_changed.connect(self._on_language_changed)
        self._apply_translations()

    def set_view(self, view: QWebEngineView):
        self._view = view
        self.stack.removeWidget(self.stack.widget(1))
        self.stack.insertWidget(1, view)
        if not self._placeholder_enabled:
            self.stack.setCurrentIndex(1)

    def show_placeholder(self):
        if self._placeholder_enabled:
            self.stack.setCurrentIndex(0)

    def show_view(self):
        self.stack.setCurrentIndex(1)

    def set_placeholder_enabled(self, enabled: bool):
        self._placeholder_enabled = enabled
        if not enabled:
            self.stack.setCurrentIndex(1)

    def set_placeholder_gif(self, path: str):
        self._gif_path = path
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        if path:
            try:
                self.movie = QMovie(path)
                if self.movie.isValid():
                    self.placeholder.setMovie(self.movie)
                    self.movie.start()
                else:
                    self.placeholder.setText(tr("Loading..."))
            except Exception:
                self.placeholder.setText(tr("Loading..."))

    def _on_language_changed(self, _lang: str) -> None:
        self._apply_translations()

    def _apply_translations(self):
        if not self.movie:
            self.placeholder.setText(tr("Loading..."))
