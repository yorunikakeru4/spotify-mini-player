#!/usr/bin/env python3
"""
Spotify Mini Player с эквалайзером для Linux и Windows
Тема: Деревяно-розовая японская эстетика
Универсальная версия с поддержкой MPRIS (Linux) и Windows Media API
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')

from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio
import cairo
import math
import random
import threading
import time
import platform
import subprocess
import json
import urllib.request
import urllib.parse
from pathlib import Path
from io import BytesIO

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

class EqualizerWidget(Gtk.DrawingArea):
    """Анимированный эквалайзер в японском стиле"""
    
    def __init__(self):
        super().__init__()
        self.set_size_request(200, 60)
        self.set_draw_func(self.draw_equalizer)
        
        # Параметры эквалайзера
        self.bars = 16
        self.bar_heights = [0.1 + random.random() * 0.9 for _ in range(self.bars)]
        self.bar_speeds = [0.02 + random.random() * 0.06 for _ in range(self.bars)]
        self.bar_directions = [1 if random.random() > 0.5 else -1 for _ in range(self.bars)]
        
        # Цвета градиента (деревяно-розовая гамма)
        self.colors = [
            (0.4, 0.2, 0.1),    # Тёмный древесный
            (0.6, 0.4, 0.2),    # Нежный коричневый
            (1.0, 0.6, 0.4),    # Яркий персиково-розовый
            (1.0, 0.8, 0.7),    # Светло-персиковый
        ]
        
        # Запуск анимации
        self.is_playing = False
        GLib.timeout_add(50, self.update_equalizer)
    
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
        
        self.queue_draw()
        return True
    
    def draw_equalizer(self, area, cr, width, height, user_data=None):
        """Отрисовка эквалайзера"""
        # Фон с градиентом
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgba(0, 0.2, 0.1, 0.05, 0.8)
        gradient.add_color_stop_rgba(1, 0.1, 0.05, 0.02, 0.9)
        cr.set_source(gradient)
        cr.paint()
        
        # Рисование полосок эквалайзера
        bar_width = width / self.bars
        
        for i in range(self.bars):
            x = i * bar_width
            bar_height = self.bar_heights[i] * (height - 10)
            y = height - bar_height - 5
            
            # Градиент для каждой полоски
            bar_gradient = cairo.LinearGradient(x, y + bar_height, x, y)
            
            # Выбор цвета в зависимости от высоты
            color_index = min(int(self.bar_heights[i] * len(self.colors)), len(self.colors) - 1)
            r, g, b = self.colors[color_index]
            
            bar_gradient.add_color_stop_rgba(0, r * 0.6, g * 0.6, b * 0.6, 0.8)
            bar_gradient.add_color_stop_rgba(0.5, r, g, b, 0.9)
            bar_gradient.add_color_stop_rgba(1, r * 1.2, g * 1.2, b * 1.2, 1.0)
            
            cr.set_source(bar_gradient)
            
            # Рисование полоски с закруглёнными краями
            cr.new_path()
            cr.move_to(x + 2, y + 3)
            cr.line_to(x + bar_width - 4, y + 3)
            cr.arc(x + bar_width - 4, y + 3, 3, -math.pi/2, 0)
            cr.line_to(x + bar_width - 1, y + bar_height - 3)
            cr.arc(x + bar_width - 4, y + bar_height - 3, 3, 0, math.pi/2)
            cr.line_to(x + 2, y + bar_height)
            cr.arc(x + 2, y + bar_height - 3, 3, math.pi/2, math.pi)
            cr.line_to(x - 1, y + 3)
            cr.arc(x + 2, y + 3, 3, math.pi, 3*math.pi/2)
            cr.close_path()
            cr.fill()

class SpotifyMiniPlayer(Gtk.ApplicationWindow):
    """Главное окно мини-плеера"""
    
    def __init__(self, app):
        super().__init__(application=app)
        
        # Настройка окна
        self.set_title(f"🌸 Spotify Mini - {platform.system()}")
        self.set_default_size(340, 280)
        self.set_resizable(False)
        
        # Всегда поверх других окон
        self.set_decorated(True)
        self.set_opacity(0.8)
        
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
        GLib.timeout_add(1000, self.update_track_info)
        
        # Добавление информации о системе в статус
        self.show_system_info()
    
    def show_system_info(self):
        """Показать информацию о системе в консоли"""
        print(f"🖥️  Система: {platform.system()} {platform.release()}")
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
        # Главный контейнер
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(8)
        main_box.set_margin_end(8)
        
        # Информация о треке с обложкой
        track_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        # Обложка альбома
        self.album_cover = Gtk.Image()
        self.album_cover.set_size_request(60, 60)
        self.album_cover.set_css_classes(["album-cover"])
        track_box.append(self.album_cover)
        
        # Информация о треке
        track_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        track_info_box.set_valign(Gtk.Align.CENTER)
        
        self.track_title = Gtk.Label(label="♪ Waiting for music...")
        self.track_title.set_css_classes(["track-title"])
        self.track_title.set_halign(Gtk.Align.START)
        self.track_title.set_ellipsize(3)
        track_info_box.append(self.track_title)
        
        self.track_artist = Gtk.Label(label="Connect your player ♫")
        self.track_artist.set_css_classes(["track-artist"])
        self.track_artist.set_halign(Gtk.Align.START)
        self.track_artist.set_ellipsize(3)
        track_info_box.append(self.track_artist)
        
        # Статус воспроизведения + система
        system_icon = "🐧" if IS_LINUX else "🪟"
        self.status_label = Gtk.Label(label=f"{system_icon} Ready")
        self.status_label.set_css_classes(["status-label"])
        self.status_label.set_halign(Gtk.Align.START)
        track_info_box.append(self.status_label)
        
        track_box.append(track_info_box)
        main_box.append(track_box)
        
        # Эквалайзер
        self.equalizer = EqualizerWidget()
        self.equalizer.set_css_classes(["equalizer"])
        main_box.append(self.equalizer)
        
        # Кнопки управления
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)
        
        # Кнопка "Предыдущий"
        prev_button = Gtk.Button(label="⏮")
        prev_button.set_css_classes(["control-button", "nav-button"])
        prev_button.connect("clicked", self.on_previous_clicked)
        controls_box.append(prev_button)
        
        # Кнопка "Воспроизведение/Пауза"
        self.play_button = Gtk.Button(label="▶")
        self.play_button.set_css_classes(["control-button", "play-button"])
        self.play_button.connect("clicked", self.on_play_clicked)
        controls_box.append(self.play_button)
        
        # Кнопка "Следующий"
        next_button = Gtk.Button(label="⏭")
        next_button.set_css_classes(["control-button", "nav-button"])
        next_button.connect("clicked", self.on_next_clicked)
        controls_box.append(next_button)
        
        main_box.append(controls_box)
        
        # Регулятор громкости
        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_box.set_halign(Gtk.Align.CENTER)
        
        volume_label = Gtk.Label(label="🔊")
        volume_label.set_css_classes(["volume-label"])
        volume_box.append(volume_label)
        
        self.volume_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.volume_scale.set_range(0.0, 1.0)
        self.volume_scale.set_value(self.current_volume)
        self.volume_scale.set_size_request(120, -1)
        self.volume_scale.set_css_classes(["volume-scale"])
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        volume_box.append(self.volume_scale)
        
        self.volume_percent_label = Gtk.Label(label="50%")
        self.volume_percent_label.set_css_classes(["volume-percent"])
        volume_box.append(self.volume_percent_label)
        
        main_box.append(volume_box)
        
        # Регулятор прозрачности
        opacity_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        opacity_box.set_halign(Gtk.Align.CENTER)
        
        opacity_label = Gtk.Label(label="✨")
        opacity_label.set_css_classes(["opacity-label"])
        opacity_box.append(opacity_label)
        
        self.opacity_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self.opacity_scale.set_range(0.7, 1.0)
        self.opacity_scale.set_value(self.current_opacity)
        self.opacity_scale.set_size_request(120, -1)
        self.opacity_scale.set_css_classes(["opacity-scale"])
        self.opacity_scale.connect("value-changed", self.on_opacity_changed)
        opacity_box.append(self.opacity_scale)
        
        self.opacity_percent_label = Gtk.Label(label="80%")
        self.opacity_percent_label.set_css_classes(["opacity-percent"])
        opacity_box.append(self.opacity_percent_label)
        
        main_box.append(opacity_box)
        
        self.set_child(main_box)
    
    def apply_styles(self):
        """Применение CSS стилей"""
        css = """
        window {
            background: radial-gradient(circle at 30% 20%, #4a2c1a 0%, #2d1810 70%);
            border: 3px solid #8b4513;
            border-radius: 20px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4), 
                        inset 0 2px 8px rgba(255, 153, 153, 0.1);
        }
        
        .track-title {
            color: #ffd4a3;
            font-size: 13px;
            font-weight: bold;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.6);
            margin: 0;
        }
        
        .track-artist {
            color: #d4a574;
            font-size: 11px;
            font-style: italic;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
            margin: 0;
        }
        
        .status-label {
            color: #ff9999;
            font-size: 10px;
            font-weight: bold;
            text-shadow: 1px 1px 3px rgba(0, 0, 0, 0.7);
            margin: 0;
        }
        
        .album-cover {
            border: 3px solid #8b4513;
            border-radius: 12px;
            background: radial-gradient(circle, #6b3e2a, #4a2c1a);
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3),
                        inset 0 2px 4px rgba(255, 153, 153, 0.2);
        }

        .equalizer {
            border: 2px solid #8b4513;
            border-radius: 15px;
            background: linear-gradient(135deg, rgba(45, 24, 16, 0.9), rgba(74, 44, 26, 0.8));
            margin: 4px 0;
            box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.4),
                        0 2px 6px rgba(255, 153, 153, 0.1);
        }

        .control-button {
            background: linear-gradient(135deg, #8b4513, #a0522d);
            color: #ffd4a3;
            border: 2px solid #654321;
            border-radius: 20px;
            padding: 6px 12px;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.3),
                        inset 0 1px 2px rgba(255, 212, 163, 0.2);
        }

        .control-button:hover {
            background: linear-gradient(135deg, #a0522d, #cd853f);
            transform: translateY(-1px) scale(1.05);
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4),
                        inset 0 2px 4px rgba(255, 212, 163, 0.3);
        }

        .control-button:active {
            transform: translateY(0px) scale(0.95);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4),
                        inset 0 2px 8px rgba(0, 0, 0, 0.3);
        }

        .play-button {
            background: linear-gradient(135deg, #ff6b6b, #ff9999);
            color: #2d1810;
            border-color: #ff4757;
            box-shadow: 0 4px 12px rgba(255, 107, 107, 0.4),
                        inset 0 2px 4px rgba(255, 255, 255, 0.3);
        }

        .play-button:hover {
            background: linear-gradient(135deg, #ff9999, #ffb3b3);
            box-shadow: 0 8px 20px rgba(255, 107, 107, 0.6),
                        inset 0 2px 6px rgba(255, 255, 255, 0.4);
        }

        .nav-button {
            background: linear-gradient(135deg, #6b3e2a, #8b4513);
            padding: 6px 10px;
        }

        .nav-button:hover {
            background: linear-gradient(135deg, #8b4513, #a0522d);
        }

        .volume-scale, .opacity-scale {
            background: linear-gradient(135deg, #4a2c1a, #6b3e2a);
            border: 2px solid #8b4513;
            border-radius: 12px;
            padding: 2px;
        }

        .volume-scale slider, .opacity-scale slider {
            background: linear-gradient(135deg, #ff9999, #ff6b6b);
            border: 2px solid #ff4757;
            border-radius: 50%;
            min-width: 16px;
            min-height: 16px;
            box-shadow: 0 2px 6px rgba(255, 107, 107, 0.5);
        }

        .volume-scale slider:hover, .opacity-scale slider:hover {
            background: linear-gradient(135deg, #ffb3b3, #ff9999);
            box-shadow: 0 4px 10px rgba(255, 107, 107, 0.7);
        }

        .volume-scale trough, .opacity-scale trough {
            background: linear-gradient(135deg, #2d1810, #4a2c1a);
            border-radius: 6px;
            border: 1px solid #654321;
            min-height: 8px;
        }

        .volume-label, .opacity-label {
            color: #ffd4a3;
            font-size: 14px;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
        }

        .volume-percent, .opacity-percent {
            color: #d4a574;
            font-size: 10px;
            font-weight: bold;
            text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
            min-width: 25px;
        }
        """
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css.encode())
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_volume_changed(self, scale):
        self.current_volume = scale.get_value()
        volume_percent = int(self.current_volume * 100)
        self.volume_percent_label.set_text(f"{volume_percent}%")
        self.media_controller.set_volume(self.current_volume)

    def on_opacity_changed(self, scale):
        self.current_opacity = scale.get_value()
        opacity_percent = int(self.current_opacity * 100)
        self.opacity_percent_label.set_text(f"{opacity_percent}%")
        self.set_opacity(self.current_opacity)

    def update_track_info(self):
        info = self.media_controller.get_track_info()
        self.track_title.set_text(f"♪ {info['title']}")
        self.track_artist.set_text(f"by {info['artist']}")
        self.status_label.set_text(f"{'🐧' if IS_LINUX else '🪟'} {info['status']}")
        self.equalizer.set_playing(info['is_playing'])
        # Загрузка обложки (если есть URL)
        if info['album_art']:
            self.load_album_cover(info['album_art'])
        return True

    def load_album_cover(self, url):
        def load_cover():
            try:
                response = urllib.request.urlopen(url, timeout=5)
                image_data = response.read()
                GLib.idle_add(self.set_album_cover, image_data)
            except Exception as e:
                print(f"Ошибка загрузки обложки: {e}")
        threading.Thread(target=load_cover, daemon=True).start()

    def set_album_cover(self, image_data):
        try:
            loader = GdkPixbuf.PixbufLoader()
            loader.write(image_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            pixbuf = pixbuf.scale_simple(50, 50, GdkPixbuf.InterpType.BILINEAR)
            self.album_cover.set_from_pixbuf(pixbuf)
        except Exception as e:
            print(f"Ошибка установки обложки: {e}")

    def on_play_clicked(self, button):
        self.media_controller.play_pause()

    def on_previous_clicked(self, button):
        self.media_controller.previous_track()

    def on_next_clicked(self, button):
        self.media_controller.next_track()

class SpotifyMiniApp(Gtk.Application):
    """Главный класс приложения"""
    def __init__(self):
        super().__init__(application_id="com.example.spotifymini")
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = SpotifyMiniPlayer(self)
            self.window.present()

def main():
    print("🌸 Запуск Spotify Mini Player...")
    app = SpotifyMiniApp()
    app.run()

if __name__ == "__main__":
    main()
