from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QMovie
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget

from modules.utils.i18n import tr
from modules.utils.logger import get_logger

try:  # pragma: no cover - optional dependency during tests
    from PySide6.QtLottie import QLottieAnimation  # type: ignore
    _HAS_QT_LOTTIE = True
except Exception:  # pragma: no cover - optional dependency
    QLottieAnimation = None  # type: ignore[assignment]
    _HAS_QT_LOTTIE = False


class SplashScreen(QDialog):
    """Simple splash dialog that can display a GIF animation or fallback text."""

    def __init__(
        self,
        json_path: Optional[Path | str] = None,
        gif_path: Optional[Path | str] = None,
        message: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        flags = Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        super().__init__(parent, flags)
        self.setObjectName("SplashScreen")
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(False)

        self._log = get_logger(__name__)
        self._movie: Optional[QMovie] = None
        self._lottie_widget: Optional[QWidget] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget(self)
        container.setObjectName("SplashContainer")
        outer.addWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(12)

        self._animation_placeholder = QLabel(container)
        self._animation_placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._animation_placeholder, 1)

        self._message_label = QLabel(message or tr("Loading..."), container)
        self._message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._message_label)

        self.setStyleSheet(
            """
            #SplashContainer {
                background-color: rgba(18, 18, 18, 215);
                border-radius: 16px;
            }
            #SplashContainer QLabel {
                color: white;
                font-size: 16px;
            }
            """
        )

        animation_loaded = self._try_load_lottie(json_path)
        if not animation_loaded:
            self._use_gif_animation(gif_path)

        self.adjustSize()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        QTimer.singleShot(0, self._center_on_screen)

    def finish(self, window: Optional[QWidget] = None) -> None:
        if self._movie:
            try:
                self._movie.stop()
            except Exception:
                pass
        self.close()
        if window:
            try:
                window.raise_()
                window.activateWindow()
            except Exception:
                pass

    # ----- Helpers -----
    def _center_on_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        rect = self.frameGeometry()
        rect.moveCenter(screen.availableGeometry().center())
        self.move(rect.topLeft())

    def _try_load_lottie(self, json_path: Optional[Path | str]) -> bool:
        if not json_path:
            return False
        if not _HAS_QT_LOTTIE:
            self._log.warning(
                "QtLottie module unavailable; falling back to GIF animation.",
                extra={"source": "ui"},
            )
            return False
        path = Path(json_path)
        if not path.exists():
            return False
        try:
            animation = QLottieAnimation(self)  # type: ignore[operator]
            animation.setResizeMode(QLottieAnimation.Stretch)
            animation.setSource(QUrl.fromLocalFile(str(path)))
            animation.setLoops(-1)
            animation.play()

            self._lottie_widget = animation
            parent_layout = self._animation_placeholder.parentWidget().layout()
            if parent_layout:
                parent_layout.removeWidget(self._animation_placeholder)
                self._animation_placeholder.hide()
                parent_layout.insertWidget(0, animation, 1)
            return True
        except Exception as ex:
            self._log.warning(
                "Lottie animation unavailable, falling back to GIF: %s",
                ex,
                extra={"source": "ui"},
            )
            return False

    def _use_gif_animation(self, gif_path: Optional[Path | str]) -> None:
        path = Path(gif_path) if gif_path else None
        if path and path.exists():
            try:
                movie = QMovie(str(path))
                if movie.isValid():
                    self._animation_placeholder.setMovie(movie)
                    movie.start()
                    self._movie = movie
                    return
            except Exception as ex:
                self._log.warning(
                    "Failed to load splash GIF '%s': %s",
                    path,
                    ex,
                    extra={"source": "ui"},
                )
        self._animation_placeholder.setText(tr("Loading..."))
