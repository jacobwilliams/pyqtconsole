#! /usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from qtpy.QtWidgets import QApplication
from pyqtconsole.console import PythonConsole


def greet():
    print("hello world")


def change_pygments_style(style):
    """change the Pygments style of the console.
    Example styles include:
      'default', 'monokai', 'vim', 'friendly', 'colorful',
      'autumn', 'rainbow_dash', and 'paraiso-dark'."""
    console.setPygmentsStyle(style)


if __name__ == '__main__':
    app = QApplication([])

    console = PythonConsole(shell_cmd_prefix=True, pygments_style='monokai')
    console.push_local_ns('greet', greet)
    console.push_local_ns('style', change_pygments_style)
    console.interpreter.locals["clear"] = console.clear
    console.show()
    console.eval_in_thread()
    sys.exit(app.exec_())
