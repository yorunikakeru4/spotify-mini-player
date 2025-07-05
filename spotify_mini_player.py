#!/usr/bin/env python3
"""
Spotify Mini Player с эквалайзером для GNOME 46 Wayland
Тема: Деревяно-розовая японская эстетика
Добавлены: регулятор громкости и прозрачности
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
from pathlib import Path
import json
import urllib.request
import urllib.parse
from io import BytesIO

try:
    import pydbus
    MPRIS_AVAILABLE = True
except ImportError:
    MPRIS_AVAILABLE = False
    print("⚠️  pydbus не найден, MPRIS отключен")

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
        self.set_title("🌸 Spotify Mini")
        self.set_default_size(340, 280)  # Увеличили высоту для новых элементов
        self.set_resizable(False)
        
        # Всегда поверх других окон
        self.set_decorated(True)
        self.set_opacity(0.8)
        
        # Переменные для управления
        self.current_volume = 0.5
        self.current_opacity = 0.8
        
        # MPRIS подключение
        self.mpris = None
        self.current_track = {}
        self.is_playing = False
        self.connect_to_spotify()
        
        # Создание интерфейса
        self.create_ui()
        
        # Применение стилей
        self.apply_styles()
        
        # Обновление данных
        GLib.timeout_add(1000, self.update_track_info)
    
    def connect_to_spotify(self):
        """Подключение к Spotify через MPRIS"""
        if not MPRIS_AVAILABLE:
            return
        
        try:
            bus = pydbus.SessionBus()
            self.mpris = bus.get("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2")
            print("✅ Подключён к Spotify")
        except Exception as e:
            print(f"❌ Не удалось подключиться к Spotify: {e}")
            self.mpris = None
    
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
        
        # Обложка альбома с анимешным дизайном
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
        
        # Статус воспроизведения с анимешными эмодзи
        self.status_label = Gtk.Label(label="◉ Ready")
        self.status_label.set_css_classes(["status-label"])
        self.status_label.set_halign(Gtk.Align.START)
        track_info_box.append(self.status_label)
        
        track_box.append(track_info_box)
        main_box.append(track_box)
        
        # Эквалайзер
        self.equalizer = EqualizerWidget()
        self.equalizer.set_css_classes(["equalizer"])
        main_box.append(self.equalizer)
        
        # Кнопки управления в анимешном стиле
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)
        
        # Кнопка "Предыдущий"
        prev_button = Gtk.Button(label="⏮")
        prev_button.set_css_classes(["control-button", "nav-button"])
        prev_button.connect("clicked", self.on_previous_clicked)
        controls_box.append(prev_button)
        
        # Кнопка "Воспроизведение/Пауза" - главная кнопка
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
        """Применение CSS стилей в анимешном стиле"""
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
        """Обработка изменения громкости"""
        self.current_volume = scale.get_value()
        volume_percent = int(self.current_volume * 100)
        self.volume_percent_label.set_text(f"{volume_percent}%")
        
        # Установка громкости через MPRIS
        if self.mpris:
            try:
                self.mpris.Volume = self.current_volume
            except Exception as e:
                print(f"Ошибка установки громкости: {e}")
    
    def on_opacity_changed(self, scale):
        """Обработка изменения прозрачности"""
        self.current_opacity = scale.get_value()
        opacity_percent = int(self.current_opacity * 100)
        self.opacity_percent_label.set_text(f"{opacity_percent}%")
        
        # Установка прозрачности окна
        self.set_opacity(self.current_opacity)
    
    def update_track_info(self):
        """Обновление информации о треке"""
        if not self.mpris:
            return True
        
        try:
            # Получение метаданных
            metadata = self.mpris.Metadata
            playback_status = self.mpris.PlaybackStatus
            
            # Обновление информации о треке
            if 'xesam:title' in metadata:
                title = metadata['xesam:title']
                self.track_title.set_text(f"♪ {title[:25]}..." if len(title) > 25 else f"♪ {title}")
            
            if 'xesam:artist' in metadata:
                artist = metadata['xesam:artist'][0] if metadata['xesam:artist'] else "Unknown"
                self.track_artist.set_text(f"by {artist[:20]}..." if len(artist) > 20 else f"by {artist}")
            
            # Обновление состояния воспроизведения с анимешными эмодзи
            self.is_playing = playback_status == "Playing"
            if self.is_playing:
                self.play_button.set_label("⏸")
                self.status_label.set_text("♫ Playing")
            else:
                self.play_button.set_label("▶")
                self.status_label.set_text("◉ Paused")
            
            self.equalizer.set_playing(self.is_playing)
            
            # Обновление громкости из плеера
            try:
                current_volume = self.mpris.Volume
                if abs(current_volume - self.current_volume) > 0.01:
                    self.current_volume = current_volume
                    self.volume_scale.set_value(self.current_volume)
                    volume_percent = int(self.current_volume * 100)
                    self.volume_percent_label.set_text(f"{volume_percent}%")
            except Exception:
                pass  # Не все плееры поддерживают Volume
            
            # Загрузка обложки альбома
            if 'mpris:artUrl' in metadata:
                self.load_album_cover(metadata['mpris:artUrl'])
            
        except Exception as e:
            print(f"Ошибка обновления: {e}")
            self.track_title.set_text("♪ Waiting for music...")
            self.track_artist.set_text("Connect your player ♫")
            self.status_label.set_text("◉ Not connected")
            self.is_playing = False
            self.equalizer.set_playing(False)
        
        return True
    
    def load_album_cover(self, url):
        """Загрузка обложки альбома"""
        def load_cover():
            try:
                response = urllib.request.urlopen(url, timeout=5)
                image_data = response.read()
                
                GLib.idle_add(self.set_album_cover, image_data)
            except Exception as e:
                print(f"Ошибка загрузки обложки: {e}")
        
        threading.Thread(target=load_cover, daemon=True).start()
    
    def set_album_cover(self, image_data):
        """Установка обложки альбома"""
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
        """Обработка нажатия кнопки воспроизведения"""
        if not self.mpris:
            return
        
        try:
            self.mpris.PlayPause()
        except Exception as e:
            print(f"Ошибка воспроизведения: {e}")
    
    def on_previous_clicked(self, button):
        """Обработка нажатия кнопки "Предыдущий трек"""
        if not self.mpris:
            return
        
        try:
            self.mpris.Previous()
        except Exception as e:
            print(f"Ошибка переключения: {e}")
    
    def on_next_clicked(self, button):
        """Обработка нажатия кнопки "Следующий трек"""
        if not self.mpris:
            return
        
        try:
            self.mpris.Next()
        except Exception as e:
            print(f"Ошибка переключения: {e}")

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
    """Главная функция"""
    print("🌸 Запуск Spotify Mini Player...")
    
    if not MPRIS_AVAILABLE:
        print("⚠️  Для полной функциональности установите pydbus:")
        print("    pip install pydbus")
    
    app = SpotifyMiniApp()
    app.run()

if __name__ == "__main__":
    main()
