import sys
import traceback

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from aidub.ui.studio_window import AIDubStudioWindow
    win = AIDubStudioWindow()
    win.resize(1600, 960)
    win.show()
    app.processEvents()
    win.chrome._select_timeline_studio()
    app.processEvents()
    if hasattr(win.studio, "workspace_splitter"):
        win.studio.workspace_splitter.setSizes([640, 240])
    if hasattr(win.studio, "upper_splitter"):
        win.studio.upper_splitter.setSizes([264, 820, 440])
    for _ in range(10):
        app.processEvents()
    pixmap = win.grab()
    pixmap.save('current_studio_timeline.png')
    print('Screenshot saved successfully!')
    win.close()
    sys.exit(0)
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
