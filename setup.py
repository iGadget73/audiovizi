from setuptools import setup

APP = ['script-vizi-1.py']

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'resources': ['icon.icns'],
    'frameworks': [],
    'qt_plugins': ['platforms'],
    'excludes': [
        'doctest', 'unittest', 'test', 'tkinter', 'numpy.core.tests'
    ],
    'includes': [
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'pyqtgraph',
        'numpy'
    ],
    'packages': [
        'PyQt5',
        'pyqtgraph',
        'numpy'
    ],
    'plist': {
        'CFBundleName': 'AudiVizi',
        'CFBundleDisplayName': 'AudiVizi',
        'CFBundleIdentifier': 'com.guenthergadget.audiovisualizer',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleGetInfoString': 'AudiVizi © 2025 by Günther Gadget',
        'CFBundleIconFile': 'icon.icns',
        'LSMinimumSystemVersion': '10.13',
        'NSHumanReadableCopyright': '© 2025 Günther Gadget',
    },
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
)
