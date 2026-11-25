// 菜单：macOS 要有应用菜单，复制粘贴、退出这些快捷键才能用；Windows 不要菜单栏（Ctrl+O 等由页面处理）

import { Menu } from "electron"
import { IS_MAC } from "./paths"
import { mainWindow } from "./window"

export function setupMenu() {
  if (!IS_MAC) { Menu.setApplicationMenu(null); return }
  const send = (cmd: string) => mainWindow()?.webContents.send("menu", cmd)
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: "音视频检测", submenu: [{ role: "about", label: "关于" }, { label: "设置…", accelerator: "Cmd+,", click: () => send("settings") }, { type: "separator" }, { role: "hide", label: "隐藏" }, { role: "quit", label: "退出" }] },
    { label: "文件", submenu: [{ label: "打开…", accelerator: "CmdOrCtrl+O", click: () => send("open") }, { role: "close", label: "关闭窗口" }] },
    { label: "编辑", submenu: [{ role: "copy", label: "拷贝" }, { role: "paste", label: "粘贴" }, { role: "selectAll", label: "全选" }] },
    { label: "窗口", submenu: [{ role: "minimize", label: "最小化" }, { role: "zoom", label: "缩放" }, { role: "togglefullscreen", label: "全屏" }] },
  ]))
}
