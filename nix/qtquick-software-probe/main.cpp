#include <QGuiApplication>
#include <QQuickView>
#include <QQmlError>
#include <QQuickItem>
#include <QUrl>
#include <QtGlobal>

#include <cstdio>
#include <cstring>

int main(int argc, char **argv) {
  bool negative = false;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--negative-effect") == 0) negative = true;
    else {
      std::fprintf(stderr, "usage: qtquick-software-probe [--negative-effect]\n");
      return 2;
    }
  }
  QGuiApplication app(argc, argv);
  std::fprintf(stderr, "qtquick-probe qt=%s platform=%s quick_backend=%s negative=%d\n",
               qVersion(), QGuiApplication::platformName().toUtf8().constData(),
               qgetenv("QT_QUICK_BACKEND").constData(), negative ? 1 : 0);
  QQuickView view;
  view.setResizeMode(QQuickView::SizeRootObjectToView);
  view.setSource(QUrl::fromLocalFile(
    QGuiApplication::applicationDirPath() + QStringLiteral("/../share/qtquick-software-probe/Probe.qml")));
  if (view.status() == QQuickView::Error || !view.rootObject()) {
    for (const QQmlError &error : view.errors())
      std::fprintf(stderr, "qml-error %s\n", error.toString().toUtf8().constData());
    return 3;
  }
  view.rootObject()->setProperty("negativeControl", negative);
  view.setWidth(568);
  view.setHeight(1232);
  view.show();
  return app.exec();
}
