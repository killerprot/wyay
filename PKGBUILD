pkgname=wyay
pkgver=1.0.0
pkgrel=1
pkgdesc='A graphical AUR package browser and installer'
arch=('any')
url='https://github.com/killerprot/wyay'
license=('MIT')
depends=('python' 'python-pyside6' 'foot' 'yay')
source=("$pkgname-$pkgver.tar.gz::https://github.com/killerprot/wyay/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  cd "$srcdir/$pkgname-$pkgver"
  install -Dm755 wyay.py "$pkgdir/usr/lib/$pkgname/wyay.py"
  install -Dm644 wyay.desktop "$pkgdir/usr/share/applications/wyay.desktop"
  install -d "$pkgdir/usr/bin"
  ln -s /usr/lib/$pkgname/wyay.py "$pkgdir/usr/bin/wyay"
}
