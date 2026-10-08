PREFIX ?= /usr/local

install:
	install -Dm755 wyay.sh $(DESTDIR)$(PREFIX)/bin/wyay

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/wyay
