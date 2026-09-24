# 姓名抽取器 2.0

原为自用工具，现选择开源（后面的介绍都是ds写的）
面向课堂点名 / 会议抽人的 Windows 桌面随机抽取工具。Python + Tkinter 编写，
**只用标准库**，界面走 ttk vista 主题 + 微软雅黑，贴近 Windows 8.1 / 10 原生观感。

## 功能特性

- **随机抽取**：从名单中抽 N 个人，同一轮内不重复；抽取数量上限即时校验。
- **随机数种子**：种子由当前时间戳派生（SHA-256 → 十进制 → 取前 10 位），按设定周期
  （默认 10 秒）刷新；刷新只重新播种，不会清空已有的降重状态。
- **降重模式**：被抽中过的姓名概率按“降重百分比”递减，且不低于“降重下限”。
  正常模式下不启用降重。
- **Special 功能**（可开关，两种模式都受其影响）：
  - `SpMode=0`：指定姓名不参与抽取；
  - `SpMode=1`：指定姓名的中签概率为正常概率的 `Spvalue`%；
  - `SpMode=2`：在 1 的基础上增加保底——累计未抽中达到 `Spvalue2` 次后
    必定抽中一次，计数持久化，重启后继承。
- **抽取统计**：记录每个姓名被抽中的次数，弹窗查看，可一键重置。
- **数据库配置页口令**：4 位数字口令，默认无口令；可选明文或 SHA-256 哈希存放。
- **输出框**：最新结果在最上方，历史内容保留，每行带 `[hh:mm:ss]` 时间戳。
- **配置可手改**：所有参数存于 `conf/conf.txt`，越界值自动收敛。

## 环境要求

| 用途 | 要求 |
| --- | --- |
| 源码运行 | Windows 7/8.1/10/11 + Python 3.8 以上（无第三方依赖） |
| 打包 exe | PyInstaller 6.x |

## 快速开始

```bat
python main.py
```

首次运行会自动创建 `db/` 与 `conf/`；若还没有名单，程序会直接弹出
“配置数据库”页面，按行输入姓名即可（每个姓名一行）。

## 数据目录

| 程序所在位置 | 数据目录 |
| --- | --- |
| 当前用户桌面，或桌面的直接子目录 | `%USERPROFILE%\NC2` |
| 其他位置（U 盘、D 盘目录等） | 程序所在目录（绿色免安装） |

首次启动会自检运行环境：缺少 `db/`、`conf/` 目录时，若不是管理员会提示
“请以管理员身份运行”并退出；以管理员身份启动则自动创建所需目录后继续。

## 数据文件

| 文件 | 格式 | 说明 |
| --- | --- | --- |
| `db/db` | 每行一个姓名的 **Base64**（UTF-8 字节） | 姓名数据库，无后缀；旧文件名 `db/db.txt` 首次读取自动迁移 |
| `db/count.db` | `姓名<TAB>次数` | 抽取统计，可在统计页重置 |
| `db/times.txt` | `姓名<TAB>未抽中次数` | SpMode=2 的保底计数，只记录 SpNum 选中的姓名 |
| `conf/conf.txt` | `键=值` | 全部设置项，可直接编辑 |
| `conf/pwd` | `mode=plain|hash` + `value=...` | 数据库配置页口令，缺省即无口令 |

所有写盘都使用“临时文件 + `os.replace`”的原子替换，避免中断产生半截文件。

## 打包

```bat
:: 单文件、不内置名单（推荐分发）
pyinstaller universal.spec --noconfirm --distpath dist_universal --workpath build_universal

:: 单文件、内置 db/db（适合自己或同一批名单的人直接用）
pyinstaller main.spec --noconfirm --distpath . --workpath build

:: 文件夹版：不需要在 %TEMP% 解包，启动更快，也不会遇到 onefile 的解包类报错
pyinstaller onedir.spec --noconfirm --distpath dist --workpath build_onedir
```

## 测试

```bat
python selftest.py   :: 逻辑自测（设置 / 种子 / 降重 / Special / 落盘 / 口令 / 环境）63 项
python guitest.py    :: 界面冒烟测试（真实建窗 + 程序化点击）54 项
```

两者都在系统临时目录中运行，不会改动 `db/` 与 `conf/`。打包后还可以用
`程序.exe --selftest` 直接验证冻结版逻辑。

## 隐私说明

`db/` 与 `conf/` 已在 `.gitignore` 中排除，名单、统计与口令不会被提交。
对外分发请使用 `universal.spec`（不内置名单），否则 exe 会把名单一起带走。

## 许可证

MIT，见 `LICENSE`。
