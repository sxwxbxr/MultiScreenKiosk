import sys
import types
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
base_str = str(BASE_DIR)
if base_str not in sys.path:
    sys.path.insert(0, base_str)


class _DummySignal:
    def __init__(self) -> None:
        self._handler = None

    def connect(self, handler):
        self._handler = handler

    def emit(self, *args, **kwargs):
        if self._handler:
            try:
                self._handler(*args, **kwargs)
            except Exception:
                pass


def _dummy_signal_factory(*_args, **_kwargs):  # type: ignore
    return _DummySignal()


class _Flag(int):
    def __new__(cls, value: int) -> "_Flag":
        return int.__new__(cls, value)  # type: ignore[arg-type]

    def __or__(self, other):
        return self.__class__(int(self) | int(other))

    def __and__(self, other):
        return self.__class__(int(self) & int(other))

    def __invert__(self):
        return self.__class__(~int(self))


def _flag_namespace(**values):
    ns = types.SimpleNamespace()
    for name, value in values.items():
        setattr(ns, name, _Flag(value))
    return ns


def _install_qtcore_stub():
    if "PyQt6.QtCore" in sys.modules:
        return sys.modules["PyQt6.QtCore"]

    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.__package__ = "PyQt6"

    class QObject:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QTimer:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            self.timeout = _dummy_signal_factory()
            self._interval = 0

        def setInterval(self, value):
            self._interval = value

        def start(self):
            pass

        def stop(self):
            pass

        @staticmethod
        def singleShot(_msec, func):
            try:
                func()
            except Exception:
                pass

    class QUrl:  # type: ignore
        def __init__(self, url: str = ""):
            self._url = url

        @staticmethod
        def fromLocalFile(path: str):
            return QUrl(path)

    class QPoint:  # type: ignore
        def __init__(self, x: int = 0, y: int = 0):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

        def toPoint(self):
            return self

    class QSize:  # type: ignore
        def __init__(self, w: int = 0, h: int = 0):
            self._w = w
            self._h = h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class QRect:  # type: ignore
        def __init__(self, x: int = 0, y: int = 0, w: int = 0, h: int = 0):
            self._x = x
            self._y = y
            self._w = w
            self._h = h

        def adjusted(self, *_args):
            return self

        def center(self):
            return QPoint()

        def topLeft(self):
            return QPoint()

    class QRectF(QRect):  # type: ignore
        pass

    class QTime:  # type: ignore
        def __init__(self, hour: int = 0, minute: int = 0):
            self.hour = hour
            self.minute = minute

    class QCoreApplication:  # type: ignore
        _instance = None

        def __init__(self, *_args, **_kwargs):
            QCoreApplication._instance = self

        @staticmethod
        def instance():
            return QCoreApplication._instance

        def exec(self):
            return 0

        def processEvents(self, *_args, **_kwargs):
            pass

    qtcore.QObject = QObject
    qtcore.QTimer = QTimer
    qtcore.QUrl = QUrl
    qtcore.QPoint = QPoint
    qtcore.QSize = QSize
    qtcore.QRect = QRect
    qtcore.QRectF = QRectF
    qtcore.QTime = QTime
    qtcore.QCoreApplication = QCoreApplication
    qtcore.pyqtSignal = _dummy_signal_factory  # type: ignore[attr-defined]
    qtcore.Signal = _dummy_signal_factory  # type: ignore[attr-defined]
    qtcore.pyqtSlot = lambda *_a, **_k: (lambda func: func)  # type: ignore[attr-defined]
    qtcore.Slot = lambda *_a, **_k: (lambda func: func)  # type: ignore[attr-defined]
    qtcore.pyqtProperty = property  # type: ignore[attr-defined]
    qtcore.Property = property  # type: ignore[attr-defined]

    def qInstallMessageHandler(handler):  # type: ignore
        qtcore._qt_message_handler = handler  # type: ignore[attr-defined]
        return handler

    qtcore.qInstallMessageHandler = qInstallMessageHandler  # type: ignore[attr-defined]

    Qt = types.SimpleNamespace()
    Qt.AlignmentFlag = _flag_namespace(
        AlignCenter=0x1,
        AlignHCenter=0x1,
        AlignLeft=0x2,
        AlignRight=0x4,
        AlignVCenter=0x8,
    )
    Qt.WindowType = _flag_namespace(
        Window=0x0,
        Dialog=0x10,
        FramelessWindowHint=0x20,
        WindowStaysOnTopHint=0x40,
        WindowContextHelpButtonHint=0x80,
        SplashScreen=0x100,
    )
    Qt.WindowState = _flag_namespace(WindowMinimized=0x1)
    Qt.WidgetAttribute = _flag_namespace(
        WA_NativeWindow=0x1,
        WA_DontCreateNativeAncestors=0x2,
        WA_DeleteOnClose=0x4,
        WA_TranslucentBackground=0x8,
        WA_TransparentForMouseEvents=0x10,
    )
    Qt.KeyboardModifier = _flag_namespace(ShiftModifier=0x1)
    Qt.MouseButton = _flag_namespace(LeftButton=0x1)
    Qt.FocusPolicy = _flag_namespace(StrongFocus=0x1)
    Qt.MatchFlag = _flag_namespace(MatchExactly=0x1)
    Qt.TransformationMode = _flag_namespace(SmoothTransformation=0x1)
    Qt.WindowModality = _flag_namespace(NonModal=0x0)

    Qt.AlignCenter = Qt.AlignmentFlag.AlignCenter
    Qt.AlignHCenter = Qt.AlignmentFlag.AlignHCenter
    Qt.AlignLeft = Qt.AlignmentFlag.AlignLeft
    Qt.AlignRight = Qt.AlignmentFlag.AlignRight
    Qt.AlignVCenter = Qt.AlignmentFlag.AlignVCenter
    Qt.Dialog = Qt.WindowType.Dialog
    Qt.Window = Qt.WindowType.Window
    Qt.FramelessWindowHint = Qt.WindowType.FramelessWindowHint
    Qt.WindowStaysOnTopHint = Qt.WindowType.WindowStaysOnTopHint
    Qt.WindowContextHelpButtonHint = Qt.WindowType.WindowContextHelpButtonHint
    Qt.SplashScreen = Qt.WindowType.SplashScreen
    Qt.WindowMinimized = Qt.WindowState.WindowMinimized
    Qt.WA_NativeWindow = Qt.WidgetAttribute.WA_NativeWindow
    Qt.WA_DontCreateNativeAncestors = Qt.WidgetAttribute.WA_DontCreateNativeAncestors
    Qt.WA_DeleteOnClose = Qt.WidgetAttribute.WA_DeleteOnClose
    Qt.WA_TranslucentBackground = Qt.WidgetAttribute.WA_TranslucentBackground
    Qt.WA_TransparentForMouseEvents = Qt.WidgetAttribute.WA_TransparentForMouseEvents
    Qt.ShiftModifier = Qt.KeyboardModifier.ShiftModifier
    Qt.LeftButton = Qt.MouseButton.LeftButton
    Qt.StrongFocus = Qt.FocusPolicy.StrongFocus
    Qt.MatchExactly = Qt.MatchFlag.MatchExactly
    Qt.SmoothTransformation = Qt.TransformationMode.SmoothTransformation
    Qt.NonModal = Qt.WindowModality.NonModal

    qtcore.Qt = Qt
    sys.modules["PyQt6.QtCore"] = qtcore
    return qtcore


def _install_qtgui_stub(qtcore):
    if "PyQt6.QtGui" in sys.modules:
        return sys.modules["PyQt6.QtGui"]

    qtgui = types.ModuleType("PyQt6.QtGui")
    qtgui.__package__ = "PyQt6"

    class QKeySequence:  # type: ignore
        def __init__(self, sequence: str = ""):
            self._sequence = sequence

        def toString(self, *_args, **_kwargs):
            return self._sequence

    class _Rect:  # type: ignore
        def __init__(self, w: int, h: int):
            self._w = w
            self._h = h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class QPixmap:  # type: ignore
        def __init__(self, path: str = ""):
            self._path = path

        def isNull(self):
            return not bool(self._path)

        def width(self):
            return 100

        def height(self):
            return 100

        def rect(self):
            return _Rect(self.width(), self.height())

        def transformed(self, *_args, **_kwargs):
            return self

    class QPainter:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

        def setRenderHint(self, *_args, **_kwargs):
            pass

        def drawPixmap(self, *_args, **_kwargs):
            pass

        def end(self):
            pass

    class QTransform:  # type: ignore
        def __init__(self):
            pass

        def rotate(self, *_args, **_kwargs):
            return self

    class QMovie:  # type: ignore
        def __init__(self, path: str = ""):
            self._path = path
            self._running = False

        def isValid(self):
            return bool(self._path)

        def start(self):
            self._running = True

        def stop(self):
            self._running = False

    class QTextCursor:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QWindow:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QGuiApplication:  # type: ignore
        _instance = None

        def __init__(self, *_args, **_kwargs):
            QGuiApplication._instance = self

        @staticmethod
        def instance():
            return QGuiApplication._instance

        @staticmethod
        def primaryScreen():
            class _Screen:
                def availableGeometry(self_inner):
                    class _Geom:
                        def center(self_geom):
                            return qtcore.QPoint(0, 0)

                    return _Geom()

            return _Screen()

        def processEvents(self, *_args, **_kwargs):
            pass

    qtgui.QKeySequence = QKeySequence
    qtgui.QPixmap = QPixmap
    qtgui.QPainter = QPainter
    qtgui.QTransform = QTransform
    qtgui.QMovie = QMovie
    qtgui.QTextCursor = QTextCursor
    qtgui.QWindow = QWindow
    qtgui.QGuiApplication = QGuiApplication

    sys.modules["PyQt6.QtGui"] = qtgui
    return qtgui


def _install_qtwidgets_stub(qtcore):
    if "PyQt6.QtWidgets" in sys.modules:
        return sys.modules["PyQt6.QtWidgets"]

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.__package__ = "PyQt6"

    class QWidget:  # type: ignore
        def __init__(self, parent=None):
            self._parent = parent
            self._layout = None

        def __getattr__(self, name):
            return _dummy_signal_factory()

        def setLayout(self, layout):
            self._layout = layout

        def layout(self):
            return self._layout

        def parentWidget(self):
            return self._parent

        def setContentsMargins(self, *_args, **_kwargs):
            pass

        def setSpacing(self, *_args, **_kwargs):
            pass

        def addWidget(self, *_args, **_kwargs):
            pass

        def addLayout(self, *_args, **_kwargs):
            pass

        def setObjectName(self, *_args, **_kwargs):
            pass

        def setStyleSheet(self, *_args, **_kwargs):
            pass

        def setAlignment(self, *_args, **_kwargs):
            pass

        def setVisible(self, *_args, **_kwargs):
            pass

        def show(self):
            pass

        def hide(self):
            pass

        def setMinimumSize(self, *_args, **_kwargs):
            pass

        def setFixedHeight(self, *_args, **_kwargs):
            pass

        def setFixedWidth(self, *_args, **_kwargs):
            pass

        def setWindowTitle(self, *_args, **_kwargs):
            pass

        def setModal(self, *_args, **_kwargs):
            pass

        def resize(self, *_args, **_kwargs):
            pass

        def move(self, *_args, **_kwargs):
            pass

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def setAttribute(self, *_args, **_kwargs):
            pass

        def setWindowFlag(self, *_args, **_kwargs):
            pass

        def setWindowModality(self, *_args, **_kwargs):
            pass

        def updateGeometry(self):
            pass

        def update(self):
            pass

        def geometry(self):
            return types.SimpleNamespace(bottomLeft=lambda: (0, 0))

        def mapToGlobal(self, *_args):
            return (0, 0)

        def deleteLater(self):
            pass

    class _Layout:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

        def addWidget(self, *_args, **_kwargs):
            pass

        def addLayout(self, *_args, **_kwargs):
            pass

        def addStretch(self, *_args, **_kwargs):
            pass

        def setContentsMargins(self, *_args, **_kwargs):
            pass

        def setSpacing(self, *_args, **_kwargs):
            pass

        def insertWidget(self, *_args, **_kwargs):
            pass

        def removeWidget(self, *_args, **_kwargs):
            pass

    class QApplication(QWidget):  # type: ignore
        _instance = None

        def __init__(self, *_args, **_kwargs):
            super().__init__()
            QApplication._instance = self

        @staticmethod
        def instance():
            return QApplication._instance

        def exec(self):
            return 0

    class QMainWindow(QWidget):  # type: ignore
        pass

    class QDialog(QWidget):  # type: ignore
        def exec(self):
            return 1

        def accept(self):
            pass

        def reject(self):
            pass

    class QLabel(QWidget):  # type: ignore
        def setText(self, *_args, **_kwargs):
            pass

        def setAlignment(self, *_args, **_kwargs):
            pass

    class QPushButton(QWidget):  # type: ignore
        pass

    class QToolButton(QWidget):  # type: ignore
        pass

    class QComboBox(QWidget):  # type: ignore
        def addItem(self, *_args, **_kwargs):
            pass

        def currentData(self):
            return None

        def findText(self, *_args, **_kwargs):
            return -1

        def setItemText(self, *_args, **_kwargs):
            pass

    class QCheckBox(QWidget):  # type: ignore
        def isChecked(self):
            return False

    class QLineEdit(QWidget):  # type: ignore
        def text(self):
            return ""

        def setText(self, *_args, **_kwargs):
            pass

        def setPlaceholderText(self, *_args, **_kwargs):
            pass

    class QFileDialog:  # type: ignore
        @staticmethod
        def getOpenFileName(*_args, **_kwargs):
            return "", ""

        @staticmethod
        def getExistingDirectory(*_args, **_kwargs):
            return ""

    class QScrollArea(QWidget):  # type: ignore
        pass

    class QMessageBox:  # type: ignore
        @staticmethod
        def information(*_args, **_kwargs):
            return 0

    class QSpinBox(QWidget):  # type: ignore
        def value(self):
            return 0

    class QGridLayout(_Layout):  # type: ignore
        pass

    class QVBoxLayout(_Layout):  # type: ignore
        pass

    class QHBoxLayout(_Layout):  # type: ignore
        pass

    class QStackedWidget(QWidget):  # type: ignore
        def addWidget(self, *_args, **_kwargs):
            pass

        def insertWidget(self, *_args, **_kwargs):
            pass

        def setCurrentIndex(self, *_args, **_kwargs):
            pass

        def widget(self, *_args, **_kwargs):
            return QWidget()

    class QStackedLayout(_Layout):  # type: ignore
        pass

    class QFormLayout(_Layout):  # type: ignore
        pass

    class QListWidget(QWidget):  # type: ignore
        def addItem(self, *_args, **_kwargs):
            pass

    class QListWidgetItem:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QPlainTextEdit(QWidget):  # type: ignore
        def setPlainText(self, *_args, **_kwargs):
            pass

    class QTextEdit(QWidget):  # type: ignore
        def setPlainText(self, *_args, **_kwargs):
            pass

    class QTableWidget(QWidget):  # type: ignore
        def setRowCount(self, *_args, **_kwargs):
            pass

        def rowCount(self):
            return 0

    class QTableWidgetItem:  # type: ignore
        def __init__(self, *_args, **_kwargs):
            pass

    class QGroupBox(QWidget):  # type: ignore
        pass

    class QTextBrowser(QWidget):  # type: ignore
        pass

    class QSizePolicy:  # type: ignore
        Expanding = 0
        MinimumExpanding = 0
        Fixed = 0

        def __init__(self, *_args, **_kwargs):
            pass

    class QTabWidget(QWidget):  # type: ignore
        pass

    class QTimeEdit(QWidget):  # type: ignore
        pass

    class QHeaderView:  # type: ignore
        ResizeToContents = 0
        Stretch = 0

        def setSectionResizeMode(self, *_args, **_kwargs):
            pass

    class QFrame(QWidget):  # type: ignore
        HLine = 0
        VLine = 1
        Sunken = 2

        def setFrameShape(self, *_args, **_kwargs):
            pass

        def setFrameShadow(self, *_args, **_kwargs):
            pass

    class QAbstractItemView:  # type: ignore
        NoEditTriggers = 0
        SingleSelection = 0
        SelectRows = 0

    class QMenu(QWidget):  # type: ignore
        def exec(self, *_args, **_kwargs):
            return None

    class QShortcut(QWidget):  # type: ignore
        pass

    qtwidgets.QWidget = QWidget
    qtwidgets.QApplication = QApplication
    qtwidgets.QMainWindow = QMainWindow
    qtwidgets.QDialog = QDialog
    qtwidgets.QLabel = QLabel
    qtwidgets.QPushButton = QPushButton
    qtwidgets.QToolButton = QToolButton
    qtwidgets.QComboBox = QComboBox
    qtwidgets.QCheckBox = QCheckBox
    qtwidgets.QLineEdit = QLineEdit
    qtwidgets.QFileDialog = QFileDialog
    qtwidgets.QScrollArea = QScrollArea
    qtwidgets.QMessageBox = QMessageBox
    qtwidgets.QSpinBox = QSpinBox
    qtwidgets.QGridLayout = QGridLayout
    qtwidgets.QVBoxLayout = QVBoxLayout
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QStackedWidget = QStackedWidget
    qtwidgets.QStackedLayout = QStackedLayout
    qtwidgets.QFormLayout = QFormLayout
    qtwidgets.QListWidget = QListWidget
    qtwidgets.QListWidgetItem = QListWidgetItem
    qtwidgets.QPlainTextEdit = QPlainTextEdit
    qtwidgets.QTextEdit = QTextEdit
    qtwidgets.QTableWidget = QTableWidget
    qtwidgets.QTableWidgetItem = QTableWidgetItem
    qtwidgets.QGroupBox = QGroupBox
    qtwidgets.QSizePolicy = QSizePolicy
    qtwidgets.QTabWidget = QTabWidget
    qtwidgets.QTimeEdit = QTimeEdit
    qtwidgets.QHeaderView = QHeaderView
    qtwidgets.QFrame = QFrame
    qtwidgets.QAbstractItemView = QAbstractItemView
    qtwidgets.QMenu = QMenu
    qtwidgets.QShortcut = QShortcut

    sys.modules["PyQt6.QtWidgets"] = qtwidgets
    return qtwidgets


def _install_qtwe_stub(qtcore):
    if "PyQt6.QtWebEngineWidgets" in sys.modules:
        return sys.modules["PyQt6.QtWebEngineWidgets"]

    qtwe = types.ModuleType("PyQt6.QtWebEngineWidgets")
    qtwe.__package__ = "PyQt6"

    class QWebEngineView:  # type: ignore
        def __init__(self):
            self.loadStarted = _dummy_signal_factory()
            self.loadFinished = _dummy_signal_factory()
            self._zoom = 1.0
            self._url = None

        def setZoomFactor(self, value):
            self._zoom = value

        def setUrl(self, url):
            self._url = url

        def reload(self):
            pass

    qtwe.QWebEngineView = QWebEngineView
    sys.modules["PyQt6.QtWebEngineWidgets"] = qtwe
    return qtwe


try:  # pragma: no cover - allow real Qt installs to be used when available
    import PyQt6  # type: ignore
except Exception:  # pragma: no cover - provide stub for headless CI
    qtcore = _install_qtcore_stub()
    qtgui = _install_qtgui_stub(qtcore)
    qtwidgets = _install_qtwidgets_stub(qtcore)
    qtwe = _install_qtwe_stub(qtcore)

    stub_pkg = types.ModuleType("PyQt6")
    stub_pkg.__path__ = []  # type: ignore[attr-defined]
    stub_pkg.__all__ = ["QtCore", "QtGui", "QtWidgets", "QtWebEngineWidgets"]
    stub_pkg.QtCore = qtcore
    stub_pkg.QtGui = qtgui
    stub_pkg.QtWidgets = qtwidgets
    stub_pkg.QtWebEngineWidgets = qtwe
    sys.modules["PyQt6"] = stub_pkg
else:  # pragma: no cover - ensure submodules exist even if incomplete
    from PyQt6 import QtCore as _QtCore  # type: ignore
    from PyQt6 import QtGui as _QtGui  # type: ignore
    from PyQt6 import QtWidgets as _QtWidgets  # type: ignore
    from PyQt6 import QtWebEngineWidgets as _QtWebEngineWidgets  # type: ignore

    if not hasattr(_QtCore, "pyqtSignal"):
        sys.modules["PyQt6.QtCore"] = _install_qtcore_stub()
    if not hasattr(_QtGui, "QGuiApplication"):
        sys.modules["PyQt6.QtGui"] = _install_qtgui_stub(_QtCore)
    if not hasattr(_QtWidgets, "QApplication"):
        sys.modules["PyQt6.QtWidgets"] = _install_qtwidgets_stub(_QtCore)
    if not hasattr(_QtWebEngineWidgets, "QWebEngineView"):
        sys.modules["PyQt6.QtWebEngineWidgets"] = _install_qtwe_stub(_QtCore)
