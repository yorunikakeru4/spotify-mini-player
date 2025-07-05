{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    # Python и основные пакеты
    python3
    python3Packages.pip
    python3Packages.setuptools
    python3Packages.wheel
    
    # GTK4 и связанные библиотеки
    gtk4
    gobject-introspection
    python3Packages.pygobject3
    python3Packages.pycairo
    
    # Для работы с MPRIS
    python3Packages.pydbus
    python3Packages.dbus-python
    
    # Дополнительные инструменты
    glib
    pkg-config
    wrapGAppsHook
    
    # Для работы с изображениями
    python3Packages.pillow
    
    # Отладка
    python3Packages.ipython
  ];
  
  shellHook = ''
    echo "🌸 Среда разработки для Spotify Mini Player готова!"
    echo "📦 Доступные инструменты:"
    echo "  - Python"
    echo "  - GTK4 "
    echo "  - PyGObject3"
    echo "  - D-Bus интеграция"
    echo ""
    echo "🚀 Для запуска: python3 spotify_mini_player.py"
    
    export GI_TYPELIB_PATH="$GI_TYPELIB_PATH:${pkgs.gobject-introspection}/lib/girepository-1.0"
    export LD_LIBRARY_PATH="$LD_LIBRARY_PATH:${pkgs.gtk4}/lib"
    export PKG_CONFIG_PATH="$PKG_CONFIG_PATH:${pkgs.gtk4}/lib/pkgconfig:${pkgs.gobject-introspection}/lib/pkgconfig"
  '';
}
