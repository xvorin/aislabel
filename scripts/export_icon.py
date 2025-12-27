from PyQt6.QtWidgets import QApplication
import qtawesome as qta
import sys


app = QApplication(sys.argv)

# 创建一个图标，例如 Font Awesome 的笑脸
icon = qta.icon('ei.livejournal')  #

pixmap = icon.pixmap(128, 128)  # 参数为 width, height

# 将 QPixmap 保存为图片文件
#    支持 PNG, JPG 等多种格式
pixmap.save('res/aislabel.ico')  # 保存为 PNG 格式
