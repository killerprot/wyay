# wyay

Графический браузер пакетов [AUR](https://aur.archlinux.org/) для Arch Linux.

## Возможности

- поиск по имени и описанию через официальный AUR RPC API;
- просмотр версии, рейтинга и описания пакета;
- открытие страницы пакета на aur.archlinux.org;
- установка одной кнопкой через `yay` в терминале `foot`.

## Запуск из исходников

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python wyay.py
```

Нужны `yay` и `foot`. Для запуска без виртуального окружения в Arch Linux достаточно установить
`python-pyside6` и выполнить `python wyay.py`.

## Установка

```bash
make install PREFIX="$HOME/.local"
```

Также в репозитории есть `PKGBUILD`, который можно использовать для сборки пакета Arch Linux.
