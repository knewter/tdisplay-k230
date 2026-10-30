#include <QElapsedTimer>
#include <QEvent>
#include <QGuiApplication>
#include <QKeyEvent>
#include <QMouseEvent>
#include <QObject>
#include <QPointerEvent>
#include <QQuickItem>
#include <QQuickView>
#include <QQmlError>
#include <QTimer>
#include <QUrl>
#include <QtGlobal>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

namespace {
unsigned long long nowMs() {
  timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return static_cast<unsigned long long>(t.tv_sec) * 1000ull + t.tv_nsec / 1000000ull;
}
unsigned logged = 0;
void logEvent(const char *name, const char *extra = nullptr) {
  if (logged++ >= 40000) return;
  std::printf("{\"e\":\"%s\",\"t\":%llu%s%s}\n", name, nowMs(), extra ? "," : "", extra ? extra : "");
}

/* Shared fixed-schema boundaries with the SHM baseline: `input` is client
 * receipt, `commit` is the end of a scene-graph frame (the software backend's
 * backing-store flush); neither is presentation or optical timing. */
class Observer : public QObject {
 public:
  bool eventFilter(QObject *, QEvent *e) override {
    const char *kind = nullptr;
    int px = -1, py = -1;
    if (e->isPointerEvent()) {
      const auto *pe = static_cast<QPointerEvent *>(e);
      if (!pe->points().isEmpty()) {
        px = static_cast<int>(pe->points().first().position().x());
        py = static_cast<int>(pe->points().first().position().y());
      }
    }
    switch (e->type()) {
      case QEvent::TouchBegin: kind = "press"; break;
      case QEvent::TouchUpdate: kind = "move"; break;
      case QEvent::TouchEnd: kind = "release"; break;
      case QEvent::MouseButtonPress:
        if (static_cast<QMouseEvent *>(e)->source() == Qt::MouseEventNotSynthesized) kind = "press";
        break;
      case QEvent::MouseMove:
        if (static_cast<QMouseEvent *>(e)->source() == Qt::MouseEventNotSynthesized &&
            static_cast<QMouseEvent *>(e)->buttons() != Qt::NoButton) kind = "move";
        break;
      case QEvent::MouseButtonRelease:
        if (static_cast<QMouseEvent *>(e)->source() == Qt::MouseEventNotSynthesized) kind = "release";
        break;
      case QEvent::KeyPress: kind = "key"; break;
      default: break;
    }
    if (kind) {
      char extra[80];
      if (px >= 0) std::snprintf(extra, sizeof extra, "\"k\":\"%s\",\"x\":%d,\"y\":%d", kind, px, py);
      else std::snprintf(extra, sizeof extra, "\"k\":\"%s\"", kind);
      logEvent("input", extra);
    }
    return false;
  }
};
}  // namespace

int main(int argc, char **argv) {
  bool negative = false;
  unsigned exitAfterMs = 0;
  for (int i = 1; i < argc; ++i) {
    if (std::strcmp(argv[i], "--negative-effect") == 0) negative = true;
    else if (std::strcmp(argv[i], "--exit-after-ms") == 0 && i + 1 < argc) {
      exitAfterMs = static_cast<unsigned>(std::strtoul(argv[++i], nullptr, 10));
    } else {
      std::fprintf(stderr, "usage: qtquick-software-probe [--negative-effect] [--exit-after-ms N]\n");
      return 2;
    }
  }
  std::setvbuf(stdout, nullptr, _IOFBF, 1 << 16);
  const unsigned long long startMs = nowMs();
  QGuiApplication app(argc, argv);
  // The wrapper renames the binary (.qtquick-software-probe-wrapped); pin the Wayland app_id.
  QGuiApplication::setDesktopFileName(QStringLiteral("qtquick-software-probe"));
  std::fprintf(stderr, "qtquick-probe qt=%s platform=%s quick_backend=%s negative=%d\n",
               qVersion(), QGuiApplication::platformName().toUtf8().constData(),
               qgetenv("QT_QUICK_BACKEND").constData(), negative ? 1 : 0);
  std::printf("{\"e\":\"start\",\"t\":%llu,\"client\":\"qtquick-software-probe\",\"qt\":\"%s\","
              "\"platform\":\"%s\",\"quick_backend\":\"%s\",\"boundary\":\"client_commit\"}\n",
              startMs, qVersion(), QGuiApplication::platformName().toUtf8().constData(),
              qgetenv("QT_QUICK_BACKEND").constData());
  QQuickView view;
  Observer observer;
  view.installEventFilter(&observer);
  view.setResizeMode(QQuickView::SizeRootObjectToView);
  view.setSource(QUrl::fromLocalFile(
    QGuiApplication::applicationDirPath() + QStringLiteral("/../share/qtquick-software-probe/Probe.qml")));
  if (view.status() == QQuickView::Error || !view.rootObject()) {
    for (const QQmlError &error : view.errors())
      std::fprintf(stderr, "qml-error %s\n", error.toString().toUtf8().constData());
    return 3;
  }
  view.rootObject()->setProperty("negativeControl", negative);
  view.setWidth(1232);
  view.setHeight(568);
  bool first = true;
  QObject::connect(&view, &QQuickWindow::frameSwapped, &view, [&]() {
    logEvent("commit");
    if (first) {
      first = false;
      char extra[64];
      std::snprintf(extra, sizeof extra, "\"w\":%d,\"h\":%d", view.width(), view.height());
      logEvent("first_frame", extra);
    }
  });
  QTimer flusher;
  flusher.setInterval(2000);
  QObject::connect(&flusher, &QTimer::timeout, [] { std::fflush(stdout); });
  flusher.start();
  if (exitAfterMs) QTimer::singleShot(static_cast<int>(exitAfterMs), &app, &QCoreApplication::quit);
  view.show();
  const int rc = app.exec();
  logEvent("exit");
  std::fflush(stdout);
  return rc;
}
