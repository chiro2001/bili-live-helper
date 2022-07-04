import sys
from PyQt5 import QtCore, QtGui, QtWidgets

def main():
    app = QtWidgets.QApplication(sys.argv)

    hello_widget = QtWidgets.QWidget()
    hello_widget.resize(280, 150)                   # 设置窗体大小
    hello_widget.setWindowTitle("Hello PyQt5")      # 设置窗体标题

    hello_label = QtWidgets.QLabel(hello_widget)    # 添加一个标签
    hello_label.setText("hello wrold")              # 设置标签文字
    
    edit = QtWidgets.QLineEdit(hello_widget)

    hello_widget.show()                             # 显示窗体
    sys.exit(app.exec_())                           # 应用程序运行

if __name__ == '__main__':
    main()

