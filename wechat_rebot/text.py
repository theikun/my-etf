from pywinauto.application import Application
import time
import sys
# 启动应用程序
#app = Application('uia').start("C:\\Program Files\\Tencent\\Weixin\\WeChat.exe")
# 连接应用程序
app = Application('uia').connect("C:\\P0rogram Files\\Tencent\\Weixin\\WeChat.exe")
sys.exit(0)
# 查找并返回标题为“微信”的窗口
dlg = app.window(title_re="微信")
# 打印登录界面窗口结构
# dlg.print_control_identifiers()

# 查找并返回标题为“进入微信”的按钮并点击
but = dlg.child_window(title="进入微信", control_type="Button")
but.click_input()

# 等待登录加载
time.sleep(5)
# 打印微信消息界面窗口结构
# dlg.print_control_identifiers()

# 查找并返回标题为“文件传输助手”的联系人并点击
but = dlg.child_window(title="文件传输助手", control_type="Button")
but.click_input()
# 查找并返回标题为“文件传输助手”的输入窗口并点击输入内容
edit = dlg.child_window(title="文件传输助手", control_type="Edit")
edit.click_input()
edit.type_keys("Hello World")
# 查找并返回标题为“发送(S)”的按钮并点击
but = dlg.child_window(title="发送(S)", control_type="Button")
but.click_input()