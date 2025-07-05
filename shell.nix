{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = [
    pkgs.python3
    pkgs.python3Packages.pip
    pkgs.python3Packages.pyside6
    pkgs.python3Packages.pydbus
  ];

  shellHook = ''
    export QT_QPA_PLATFORMTHEME=qt5ct
    echo "Для запуска используйте: python3 spotify_mini_player.py"
  '';
}
