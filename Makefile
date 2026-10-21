PREFIX ?= /usr/local
DESTDIR ?=

install:
	install -Dm755 wyay.py $(DESTDIR)$(PREFIX)/lib/wyay/wyay.py
	install -Dm644 wyay.desktop $(DESTDIR)$(PREFIX)/share/applications/wyay.desktop
	install -d $(DESTDIR)$(PREFIX)/bin
	ln -sf ../lib/wyay/wyay.py $(DESTDIR)$(PREFIX)/bin/wyay

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/wyay
	rm -rf $(DESTDIR)$(PREFIX)/lib/wyay
	rm -f $(DESTDIR)$(PREFIX)/share/applications/wyay.desktop

run:
	python wyay.py
