from typing import List
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QRect
from PySide6.QtWidgets import QWidget, QStackedWidget, QGridLayout, QVBoxLayout, QLabel, QSizePolicy
from modules.utils.i18n import tr, i18n

class LoadingOverlay(QWidget):
    def __init__(self, text=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        self.label = QLabel("", self)
        self.label.setStyleSheet("font-size:18px; background: rgba(0,0,0,0.4); color: white; padding:8px; border-radius:8px;")
        layout.addWidget(self.label)
        i18n.language_changed.connect(self._on_language_changed)
        self._apply_translations(text)
        self.hide()

    def _on_language_changed(self, _lang: str) -> None:
        self._apply_translations()

    def _apply_translations(self, explicit=None):
        self.label.setText(explicit if explicit is not None else tr("Loading..."))

class ViewContainer(QWidget):
    """Container fuer eine einzelne Ansicht mit Overlay"""
    def __init__(self, widget: QWidget, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(widget)
        self.overlay = LoadingOverlay(parent=self)
        self.overlay.raise_()

    def resizeEvent(self, ev):
        self.overlay.setGeometry(self.rect())
        super().resizeEvent(ev)

    def show_loading(self, on: bool):
        self.overlay.setVisible(on)

class ViewsHost(QWidget):
    """Haelt Einzelansicht per StackedWidget und Viereransicht per Grid"""
    def __init__(self, view_widgets: List[QWidget], parent=None):
        super().__init__(parent)
        self._build_ui(view_widgets)

    def _build_ui(self, view_widgets: List[QWidget]):
        self.stack = QStackedWidget(self)
        self.single_containers: List[ViewContainer] = []
        for w in view_widgets:
            c = ViewContainer(w, self)
            self.single_containers.append(c)
            self.stack.addWidget(c)

        self.grid = QWidget(self)
        gl = QGridLayout(self.grid)
        gl.setContentsMargins(0,0,0,0)
        gl.setSpacing(0)
        for i, w in enumerate(view_widgets):
            c = ViewContainer(w, self)
            # Hinweis: fuer Quad nutzen wir neue Container mit denselben Widgets, aber Widgets koennen nur einen Parent haben.
            # Daher erstellen wir im MainWindow eigenstaendige Widgets fuer Quad. Dort bauen wir beide Varianten.
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.stack)

    def set_single_index(self, idx: int):
        self.stack.setCurrentIndex(idx)
