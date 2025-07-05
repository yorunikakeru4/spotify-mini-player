#!/usr/bin/env python3
"""
Spotify Mini Player с эквалайзером для Linux и Windows
Тема: Деревяно-розовая японская эстетика
PySide версия для универсальной кроссплатформенности
"""

import sys
import os
import platform
import subprocess
import json
import urllib.request
import urllib.parse
import threading
import time
import random
import math
from pathlib import Path
from io import BytesIO

# PySide6 импорты
try:
    from PySide6.QtWidgets import *
    from PySide6.QtCore import *
    from PySide6.QtGui import *
    PYSIDE_VERSION = 6
except ImportError:
    try:
        from PySide2.QtWidgets import *
        from PySide2.QtCore import *
        from PySide2.QtGui import *
        PYSIDE_VERSION = 2
    except ImportError:
        print("❌ PySide не найден! Установите: pip install PySide6")
        sys.exit(1)

# Определение операционной системы
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Импорты для Linux (MPRIS)
if IS_LINUX:
    try:
        import pydbus
        MPRIS_AVAILABLE = True
    except ImportError:
        MPRIS_AVAILABLE = False
        print("⚠️  pydbus не найден, установите: pip install pydbus")
else:
    MPRIS_AVAILABLE = False

# Импорты для Windows
if IS_WINDOWS:
    try:
        import winsdk.windows.media.control as wmc
        import winsdk.windows.storage.streams as wss
        import asyncio
        import winrt.windows.media.control as wmc_winrt
        WINDOWS_MEDIA_AVAILABLE = True
    except ImportError:
        try:
            # Альтернативный способ через COM
            import win32com.client
            WINDOWS_COM_AVAILABLE = True
            WINDOWS_MEDIA_AVAILABLE = False
        except ImportError:
            print("⚠️  Для Windows установите: pip install winrt winsdkfb")
            print("⚠️  Или альтернативно: pip install pywin32")
            WINDOWS_MEDIA_AVAILABLE = False
            WINDOWS_COM_AVAILABLE = False
else:
    WINDOWS_MEDIA_AVAILABLE = False
    WINDOWS_COM_AVAILABLE = False

class MediaController:
    """Универсальный контроллер медиа для Linux и Windows"""
    
    def __init__(self):
        self.is_playing = False
        self.current_track = {}
        self.volume = 0.5
        
        if IS_LINUX and MPRIS_AVAILABLE:
            self.controller = LinuxMPRISController()
        elif IS_WINDOWS and WINDOWS_MEDIA_AVAILABLE:
            self.controller = WindowsMediaController()
        elif IS_WINDOWS and WINDOWS_COM_AVAILABLE:
            self.controller = WindowsCOMController()
        else:
            self.controller = DummyController()
    
    def get_track_info(self):
        return self.controller.get_track_info()
    
    def play_pause(self):
        self.controller.play_pause()
    
    def next_track(self):
        self.controller.next_track()
    
    def previous_track(self):
        self.controller.previous_track()
    
    def set_volume(self, volume):
        self.controller.set_volume(volume)
    
    def get_volume(self):
        return self.controller.get_volume()

class LinuxMPRISController:
    """Контроллер для Linux через MPRIS"""
    
    def __init__(self):
        self.mpris = None
        self.connect_to_spotify()
    
    def connect_to_spotify(self):
        try:
            bus = pydbus.SessionBus()
            self.mpris = bus.get("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2")
            print("✅ Подключён к Spotify через MPRIS")
        except Exception as e:
            print(f"❌ Не удалось подключиться к Spotify: {e}")
            self.mpris = None
    
    def get_track_info(self):
        if not self.mpris:
            return {
                'title': 'Waiting for music...',
                'artist': 'Connect your player ♫',
                'status': 'Not connected',
                'is_playing': False,
                'album_art': None
            }
        
        try:
            metadata = self.mpris.Metadata
            playback_status = self.mpris.PlaybackStatus
            
            return {
                'title': metadata.get('xesam:title', 'Unknown'),
                'artist': metadata.get('xesam:artist', ['Unknown'])[0] if metadata.get('xesam:artist') else 'Unknown',
                'status': 'Playing' if playback_status == "Playing" else 'Paused',
                'is_playing': playback_status == "Playing",
                'album_art': metadata.get('mpris:artUrl', None)
            }
        except Exception as e:
            print(f"Ошибка получения данных MPRIS: {e}")
            return {
                'title': 'Error',
                'artist': 'Connection lost',
                'status': 'Error',
                'is_playing': False,
                'album_art': None
            }
    
    def play_pause(self):
        if self.mpris:
            try:
                self.mpris.PlayPause()
            except Exception as e:
                print(f"Ошибка play/pause: {e}")
    
    def next_track(self):
        if self.mpris:
            try:
                self.mpris.Next()
            except Exception as e:
                print(f"Ошибка next: {e}")
    
    def previous_track(self):
        if self.mpris:
            try:
                self.mpris.Previous()
            except Exception as e:
                print(f"Ошибка previous: {e}")
    
    def set_volume(self, volume):
        if self.mpris:
            try:
                self.mpris.Volume = volume
            except Exception as e:
                print(f"Ошибка установки громкости: {e}")
    
    def get_volume(self):
        if self.mpris:
            try:
                return self.mpris.Volume
            except Exception:
                return 0.5
        return 0.5

class WindowsMediaController:
    """Контроллер для Windows через Windows Media API"""
    
    def __init__(self):
        self.session_manager = None
        self.current_session = None
        self.setup_windows_media()
    
    def setup_windows_media(self):
        try:
            # Создание event loop для async операций
            if not hasattr(self, 'loop'):
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
            
            # Получение менеджера сессий
            self.session_manager = wmc_winrt.GlobalSystemMediaTransportControlsSessionManager.request_async().get()
            self.find_spotify_session()
            print("✅ Подключён к Windows Media API")
        except Exception as e:
            print(f"❌ Ошибка инициализации Windows Media: {e}")
    
    def find_spotify_session(self):
        try:
            sessions = self.session_manager.get_sessions()
            for session in sessions:
                if "spotify" in session.source_app_user_model_id.lower():
                    self.current_session = session
                    return
        except Exception as e:
            print(f"Ошибка поиска Spotify сессии: {e}")
    
    def get_track_info(self):
        if not self.current_session:
            self.find_spotify_session()
        
        if not self.current_session:
            return {
                'title': 'Waiting for music...',
                'artist': 'Connect your player ♫',
                'status': 'Not connected',
                'is_playing': False,
                'album_art': None
            }
        
        try:
            media_info = self.current_session.try_get_media_properties_async().get()
            playback_info = self.current_session.get_playback_info()
            
            return {
                'title': media_info.title or 'Unknown',
                'artist': media_info.artist or 'Unknown',
                'status': 'Playing' if playback_info.playback_status == 4 else 'Paused',
                'is_playing': playback_info.playback_status == 4,
                'album_art': None  # Требует дополнительной обработки
            }
        except Exception as e:
            print(f"Ошибка получения данных Windows Media: {e}")
            return {
                'title': 'Error',
                'artist': 'Connection lost',
                'status': 'Error',
                'is_playing': False,
                'album_art': None
            }
    
    def play_pause(self):
        if self.current_session:
            try:
                self.current_session.try_play_pause_async()
            except Exception as e:
                print(f"Ошибка play/pause: {e}")
    
    def next_track(self):
        if self.current_session:
            try:
                self.current_session.try_skip_next_async()
            except Exception as e:
                print(f"Ошибка next: {e}")
    
    def previous_track(self):
        if self.current_session:
            try:
                self.current_session.try_skip_previous_async()
            except Exception as e:
                print(f"Ошибка previous: {e}")
    
    def set_volume(self, volume):
        # Windows Media API не поддерживает установку громкости
        pass
    
    def get_volume(self):
        return 0.5

class WindowsCOMController:
    """Альтернативный контроллер для Windows через COM"""
    
    def __init__(self):
        self.spotify_process = None
        self.find_spotify_process()
    
    def find_spotify_process(self):
        try:
            # Поиск процесса Spotify
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Spotify.exe'], 
                                  capture_output=True, text=True)
            if 'Spotify.exe' in result.stdout:
                print("✅ Найден процесс Spotify")
                return True
        except Exception as e:
            print(f"Ошибка поиска Spotify: {e}")
        return False
    
    def get_track_info(self):
        if not self.find_spotify_process():
            return {
                'title': 'Waiting for music...',
                'artist': 'Connect your player ♫',
                'status': 'Not connected',
                'is_playing': False,
                'album_art': None
            }
        
        # Упрощённая версия - получение информации через заголовок окна
        try:
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Spotify.exe', '/V'], 
                                  capture_output=True, text=True)
            
            # Парсинг заголовка окна Spotify
            lines = result.stdout.split('\n')
            for line in lines:
                if 'Spotify.exe' in line and ' - ' in line:
                    # Извлечение информации о треке из заголовка
                    parts = line.split(' - ')
                    if len(parts) >= 2:
                        title_part = parts[-1].strip()
                        artist_part = parts[-2].strip()
                        
                        return {
                            'title': title_part,
                            'artist': artist_part,
                            'status': 'Playing',
                            'is_playing': True,
                            'album_art': None
                        }
        except Exception as e:
            print(f"Ошибка получения данных COM: {e}")
        
        return {
            'title': 'Unknown',
            'artist': 'Unknown',
            'status': 'Unknown',
            'is_playing': False,
            'album_art': None
        }
    
    def play_pause(self):
        self.send_media_key('play_pause')
    
    def next_track(self):
        self.send_media_key('next_track')
    
    def previous_track(self):
        self.send_media_key('previous_track')
    
    def send_media_key(self, key):
        try:
            if IS_WINDOWS:
                # Отправка медиа-клавиш через VK коды
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                
                # VK коды для медиа-клавиш
                VK_MEDIA_PLAY_PAUSE = 0xB3
                VK_MEDIA_NEXT_TRACK = 0xB0
                VK_MEDIA_PREV_TRACK = 0xB1
                
                key_map = {
                    'play_pause': VK_MEDIA_PLAY_PAUSE,
                    'next_track': VK_MEDIA_NEXT_TRACK,
                    'previous_track': VK_MEDIA_PREV_TRACK
                }
                
                if key in key_map:
                    vk_code = key_map[key]
                    user32.keybd_event(vk_code, 0, 0, 0)
                    user32.keybd_event(vk_code, 0, 2, 0)
        except Exception as e:
            print(f"Ошибка отправки медиа-клавиши: {e}")
    
    def set_volume(self, volume):
        # COM контроллер не поддерживает установку громкости
        pass
    
    def get_volume(self):
        return 0.5

class DummyController:
    """Заглушка для случаев, когда нет доступных контроллеров"""
    
    def get_track_info(self):
        return {
            'title': 'Media API не доступен',
            'artist': 'Установите необходимые зависимости',
            'status': 'Offline',
            'is_playing': False,
            'album_art': None
        }
    
    def play_pause(self):
        print("⚠️  Управление недоступно")
    
    def next_track(self):
        print("⚠️  Управление недоступно")
    
    def previous_track(self):
        print("⚠️  Управление недоступно")
    
    def set_volume(self, volume):
        pass
    
    def get_volume(self):
        return 0.5

class EqualizerWidget(QWidget):
    """Анимированный эквалайзер в японском стиле"""
    
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 60)
        
        # Параметры эквалайзера
        self.bars = 16
        self.bar_heights = [0.1 + random.random() * 0.9 for _ in range(self.bars)]
        self.bar_speeds = [0.02 + random.random() * 0.06 for _ in range(self.bars)]
        self.bar_directions = [1 if random.random() > 0.5 else -1 for _ in range(self.bars)]
        
        # Цвета градиента (деревяно-розовая гамма)
        self.colors = [
            QColor(102, 51, 25),     # Тёмный древесный
            QColor(153, 102, 51),    # Нежный коричневый
            QColor(255, 153, 102),   # Яркий персиково-розовый
            QColor(255, 204, 179),   # Светло-персиковый
        ]
        
        # Запуск анимации
        self.is_playing = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_equalizer)
        self.timer.start(50)
    
    def set_playing(self, playing):
        """Установить состояние воспроизведения"""
        self.is_playing = playing
    
    def update_equalizer(self):
        """Обновление анимации эквалайзера"""
        if self.is_playing:
            for i in range(self.bars):
                self.bar_heights[i] += self.bar_speeds[i] * self.bar_directions[i]
                
                # Отскок от границ
                if self.bar_heights[i] >= 1.0:
                    self.bar_heights[i] = 1.0
                    self.bar_directions[i] = -1
                elif self.bar_heights[i] <= 0.1:
                    self.bar_heights[i] = 0.1
                    self.bar_directions[i] = 1
                
                # Случайное изменение направления
                if random.random() < 0.05:
                    self.bar_directions[i] *= -1
        else:
            # Плавное затухание при остановке
            for i in range(self.bars):
                self.bar_heights[i] *= 0.95
                if self.bar_heights[i] < 0.1:
                    self.bar_heights[i] = 0.1
        
        self.update()
    
    def paintEvent(self, event):
        """Отрисовка эквалайзера"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Фон с градиентом
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(51, 25, 12, 204))  # rgba(51, 25, 12, 0.8)
        gradient.setColorAt(1, QColor(25, 12, 5, 229))   # rgba(25, 12, 5, 0.9)
        painter.fillRect(self.rect(), gradient)
        
        # Рисование полосок эквалайзера
        bar_width = self.width() / self.bars
        
        for i in range(self.bars):
            x = i * bar_width
            bar_height = self.bar_heights[i] * (self.height() - 10)
            y = self.height() - bar_height - 5
            
            # Выбор цвета в зависимости от высоты
            color_index = min(int(self.bar_heights[i] * len(self.colors)), len(self.colors) - 1)
            color = self.colors[color_index]
            
            # Градиент для каждой полоски
            bar_gradient = QLinearGradient(x, y + bar_height, x, y)
            bar_gradient.setColorAt(0, color.darker(140))
            bar_gradient.setColorAt(0.5, color)
            bar_gradient.setColorAt(1, color.lighter(120))
            
            # Рисование полоски с закруглёнными краями
            rect = QRectF(x + 2, y, bar_width - 4, bar_height)
            painter.setBrush(bar_gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 3, 3)

class SpotifyMiniPlayer(QMainWindow):
    """Главное окно мини-плеера"""
    
    def __init__(self):
        super().__init__()
        
        # Настройка окна
        self.setWindowTitle(f"🌸 Spotify Mini - {platform.system()}")
        self.setFixedSize(340, 280)
        
        # Всегда поверх других окон
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Переменные для управления
        self.current_volume = 0.5
        self.current_opacity = 0.8
        
        # Универсальный медиа-контроллер
        self.media_controller = MediaController()
        
        # Создание интерфейса
        self.create_ui()
        
        # Применение стилей
        self.apply_styles()
        
        # Обновление данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_track_info)
        self.update_timer.start(1000)
        
        # Добавление информации о системе в статус
        self.show_system_info()
    
    def show_system_info(self):
        """Показать информацию о системе в консоли"""
        print(f"🖥️  Система: {platform.system()} {platform.release()}")
        print(f"🎨 PySide версия: {PYSIDE_VERSION}")
        if IS_LINUX:
            print("🐧 Используется MPRIS для управления")
        elif IS_WINDOWS:
            if WINDOWS_MEDIA_AVAILABLE:
                print("🪟 Используется Windows Media API")
            elif WINDOWS_COM_AVAILABLE:
                print("🪟 Используется COM + медиа-клавиши")
            else:
                print("🪟 Медиа API недоступен")
    
    def create_ui(self):
        """Создание пользовательского интерфейса"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный контейнер
        main_layout = QVBoxLayout()
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Информация о треке с обложкой
        track_layout = QHBoxLayout()
        track_layout.setSpacing(10)
        
        # Обложка альбома
        self.album_cover = QLabel()
        self.album_cover.setFixedSize(60, 60)
        self.album_cover.setAlignment(Qt.AlignCenter)
        self.album_cover.setStyleSheet("border: 3px solid #8b4513; border-radius: 12px; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #6b3e2a, stop:1 #4a2c1a);")
        track_layout.addWidget(self.album_cover)
        
        # Информация о треке
        track_info_layout = QVBoxLayout()
        track_info_layout.setSpacing(4)
        
        self.track_title = QLabel("♪ Waiting for music...")
        self.track_title.setObjectName("track_title")
        track_info_layout.addWidget(self.track_title)
        
        self.track_artist = QLabel("Connect your player ♫")
        self.track_artist.setObjectName("track_artist")
        track_info_layout.addWidget(self.track_artist)
        
        # Статус воспроизведения + система
        system_icon = "🐧" if IS_LINUX else "🪟"
        self.status_label = QLabel(f"{system_icon} Ready")
        self.status_label.setObjectName("status_label")
        track_info_layout.addWidget(self.status_label)
        
        track_layout.addLayout(track_info_layout)
        main_layout.addLayout(track_layout)
        
        # Эквалайзер
        self.equalizer = EqualizerWidget()
        self.equalizer.setObjectName("equalizer")
        main_layout.addWidget(self.equalizer)
        
        # Кнопки управления
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(12)
        
        # Кнопка "Предыдущий"
        prev_button = QPushButton("⏮")
        prev_button.setObjectName("nav_button")
        prev_button.clicked.connect(self.on_previous_clicked)
        controls_layout.addWidget(prev_button)
        
        # Кнопка "Воспроизведение/Пауза"
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("play_button")
        self.play_button.clicked.connect(self.on_play_clicked)
        controls_layout.addWidget(self.play_button)
        
        # Кнопка "Следующий"
        next_button = QPushButton("⏭")
        next_button.setObjectName("nav_button")
        next_button.clicked.connect(self.on_next_clicked)
        controls_layout.addWidget(next_button)
        
        main_layout.addLayout(controls_layout)
        
        # Регулятор громкости
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(8)
        
        volume_label = QLabel("🔊")
        volume_label.setObjectName("volume_label")
        volume_layout.addWidget(volume_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.current_volume * 100))
        self.volume_slider.setObjectName("volume_slider")
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        volume_layout.addWidget(self.volume_slider)
        
        self.volume_percent_label = QLabel("50%")
        self.volume_percent_label.setObjectName("volume_percent")
        volume_layout.addWidget(self.volume_percent_label)
        
        main_layout.addLayout(volume_layout)
        
        # Регулятор прозрачности
        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(8)
        
        opacity_label = QLabel("✨")
        opacity_label.setObjectName("opacity_label")
        opacity_layout.addWidget(opacity_label)
        
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(70, 100)
        self.opacity_slider.setValue(int(self.current_opacity * 100))
        self.opacity_slider.setObjectName("opacity_slider")
        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)
        
        self.opacity_percent_label = QLabel("80%")
        self.opacity_percent_label.setObjectName("opacity_percent")
        opacity_layout.addWidget(self.opacity_percent_label)
        
        main_layout.addLayout(opacity_layout)
        
        central_widget.setLayout(main_layout)
    
    def apply_styles(self):
        """Применение стилей"""
        style = """
        QMainWindow {
            background: qradialgradient(cx:0.3, cy:0.2, radius:0.7, fx:0.3, fy:0.2, stop:0 #4a2c1a, stop:1 #2d1810);
            border: 3px solid #8b4513;
            border-radius: 20px;
        }
        
        #track_title {
            color: #ffd4a3;
            font-size: 13px;
            font-weight: bold;
            padding: 2px;
        }
        
        #track_artist {
            color: #d4a574;
            font-size: 11px;
            font-style: italic;
            padding: 2px;
        }
        
        #status_label {
            color: #ff9999;
            font-size: 10px;
            font-weight: bold;
            padding: 2px;
        }
        
        #equalizer {
            border: 2px solid #8b4513;
            border-radius: 15px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(45, 24, 16, 230), stop:1 rgba(74, 44, 26, 204));
            margin: 4px 0px;
        }
        
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b4513, stop:1 #a0522d);
            color: #ffd4a3;
            border: 2px solid #654321;
            border-radius: 20px;
            padding: 6px 12px;
            font-size: 14px;
            font-weight: bold;
            min-width: 30px;
            min-height: 30px;
        }
        
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a0522d, stop:1 #cd853f);
        }
        
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #654321, stop:1 #8b4513);
        }
        
        #play_button {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff6b6b, stop:1 #ff9999);
            color: #2d1810;
            border-color: #ff4757;
        }
        
        #play_button:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff9999, stop:1 #ffb3b3);
        }
        
        #nav_button {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6b3e2a, stop:1 #8b4513);
            padding: 6px 10px;
        }
        
        #nav_button:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4a2c1a, stop:1 #8b4513);
        }

        #volume_label, #opacity_label {
            color: #ffd4a3;
            font-size: 15px;
            font-weight: bold;
        }
        #volume_slider, #opacity_slider {
            min-width: 80px;
        }
        #volume_percent, #opacity_percent {
            color: #ffd4a3;
            font-size: 11px;
            font-weight: bold;
        }
        """
        self.setStyleSheet(style)

    def update_track_info(self):
        """Обновление информации о текущем треке и UI"""
        info = self.media_controller.get_track_info()
        self.track_title.setText(info.get('title', 'Unknown'))
        self.track_artist.setText(info.get('artist', 'Unknown'))
        self.status_label.setText(info.get('status', 'Unknown'))
        is_playing = info.get('is_playing', False)
        self.equalizer.set_playing(is_playing)
        self.play_button.setText("⏸" if is_playing else "▶")

        # Обновление обложки, если есть ссылка
        cover_url = info.get('album_art')
        if cover_url:
            try:
                data = urllib.request.urlopen(cover_url).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                self.album_cover.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            except Exception:
                self.album_cover.setPixmap(QPixmap())
        else:
            self.album_cover.setPixmap(QPixmap())

    def on_previous_clicked(self):
        self.media_controller.previous_track()
        self.update_track_info()

    def on_play_clicked(self):
        self.media_controller.play_pause()
        self.update_track_info()

    def on_next_clicked(self):
        self.media_controller.next_track()
        self.update_track_info()

    def on_volume_changed(self, value):
        self.current_volume = value / 100.0
        self.volume_percent_label.setText(f"{value}%")
        self.media_controller.set_volume(self.current_volume)

    def on_opacity_changed(self, value):
        self.current_opacity = value / 100.0
        self.opacity_percent_label.setText(f"{value}%")
        self.setWindowOpacity(self.current_opacity)

def main():
    app = QApplication(sys.argv)
    player = SpotifyMiniPlayer()
    player.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
