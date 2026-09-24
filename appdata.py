# -*- coding: utf-8 -*-
"""磁盘数据访问层：路径解析、运行环境自检、数据与口令文件读写。

文件清单与读写规则：

* db/db          姓名数据库（无后缀）。每行一个姓名，内容是该姓名 UTF-8 字节的
                 Base64 文本；空行与解码失败的行忽略。旧版本文件名为 db/db.txt，
                 首次读取时自动迁移为 db/db（数据兼容，不丢名单）。
* db/count.db    抽取统计。每行 “姓名<TAB>次数”（UTF-8）。每次抽取后累加；
                 “抽取统计”页可整体重置。
* db/times.txt   SpMode=2 的保底计数，只记录 SpNum 所选姓名。每行
                 “姓名<TAB>累计未抽中次数”（UTF-8）。这是唯一跨启动继承的运行状态。
* conf/conf.txt  设置项。每行 “键=值”（UTF-8），语义见 appconfig.py。
* conf/pwd       数据库配置页口令（无后缀）。默认不存在 = 无口令，可直接进入配置页。
                 内容形如：
                     mode=plain|hash
                     value=<四位数字 或 SHA-256 十六进制>
                 plain 直接比对明文；hash 比对 SHA-256，磁盘上不落明文口令。

写盘策略：所有写入都走“临时文件 + os.replace”的原子替换，避免写入过程中崩溃
导致数据文件半截损坏；同时避免无谓的重复写入（由调用方按需触发）。

运行时目录（软件根目录）解析规则：
* exe（或源码工程）位于当前用户桌面      -> 数据放到 “用户目录\\NC2”；
* 其他位置（含源码运行）                -> 数据就放在 exe/工程所在目录；
* 自测可用 set_data_root() 临时覆盖，避免污染真实数据。
首次启动自检：environment_missing() 列出缺失的必需目录；非管理员时由调用方提示
“需要使用管理员身份运行”，管理员身份下调用 bootstrap() 自动创建目录与数据库文件。
内置只读资源（打包进 exe 的 db/db 模板）从 resource_root() 读取。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import sys

# 测试用的数据根目录覆盖（None 表示按 app_root() 正常解析）
_DATA_ROOT = None

DB_DIR_NAME = "db"
CONF_DIR_NAME = "conf"
DB_FILE_NAME = "db"                 # 无后缀数据库文件
LEGACY_DB_FILE_NAME = "db.txt"      # 旧版文件名，仅用于自动迁移
COUNT_FILE_NAME = "count.db"
TIMES_FILE_NAME = "times.txt"
CONF_FILE_NAME = "conf.txt"
PASSWORD_FILE_NAME = "pwd"          # 无后缀口令文件
USER_FOLDER_NAME = "NC2"            # 桌面场景下的用户目录数据文件夹

PASSWORD_MODE_PLAIN = "plain"
PASSWORD_MODE_HASH = "hash"

_HEADER_COUNT = "# 本文件由“姓名抽取器2.0”自动生成：姓名<TAB>次数（UTF-8）"
_HEADER_PASSWORD = (
    "# 姓名抽取器2.0 数据库配置页口令（UTF-8，无后缀文件）\n"
    "# mode=plain 直接比对明文；mode=hash 比对 SHA-256，磁盘上不保存明文口令\n"
)


# --------------------------------------------------------------------------
# 路径解析
# --------------------------------------------------------------------------
def set_data_root(path):
    """覆盖运行时数据根目录，仅用于自测；传 None 恢复默认解析。"""
    global _DATA_ROOT
    _DATA_ROOT = os.path.abspath(path) if path else None


def program_dir():
    """程序所在目录：打包后为 exe 所在目录，源码运行为工程目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def desktop_dir():
    """当前用户桌面目录（走 Windows Shell API，兼容 OneDrive 重定向）。"""
    try:
        import ctypes

        buffer = ctypes.create_unicode_buffer(260)
        # CSIDL_DESKTOPDIRECTORY = 0x0010
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buffer) == 0:
            value = buffer.value
            if value:
                return os.path.normcase(os.path.abspath(value))
    except Exception:
        pass
    return os.path.normcase(os.path.join(os.path.expanduser("~"), "Desktop"))


def is_on_desktop(path):
    """判断给定路径是否位于“桌面区域”。

    桌面区域 = 桌面目录本身，或桌面的直接子目录（文件夹版程序通常放在
    桌面上的一个文件夹里，同样不应该把运行数据写进桌面）。
    """
    try:
        target = os.path.normcase(os.path.abspath(path))
    except Exception:
        return False
    desktop = desktop_dir()
    if target == desktop:
        return True
    return os.path.normcase(os.path.dirname(target)) == desktop


def is_admin():
    """当前进程是否以管理员身份运行（用于首次启动的环境自检）。"""
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def app_root():
    """软件根目录（数据根）。

    桌面场景：数据统一放到 “用户目录\\NC2”，避免把运行文件写到桌面；
    其他场景：与程序同目录，绿色免安装。
    """
    if _DATA_ROOT is not None:
        return _DATA_ROOT
    directory = program_dir()
    if is_on_desktop(directory):
        return os.path.join(os.path.expanduser("~"), USER_FOLDER_NAME)
    return directory


def resource_root():
    """只读资源根目录：PyInstaller 解包目录（_MEIPASS）；源码运行时等于工程目录。"""
    return getattr(sys, "_MEIPASS", program_dir())


def db_dir():
    return os.path.join(app_root(), DB_DIR_NAME)


def conf_dir():
    return os.path.join(app_root(), CONF_DIR_NAME)


def db_path():
    """数据库文件：db/db（无后缀）。"""
    return os.path.join(db_dir(), DB_FILE_NAME)


def legacy_db_path():
    """旧版数据库文件：db/db.txt（仅用于自动迁移）。"""
    return os.path.join(db_dir(), LEGACY_DB_FILE_NAME)


def count_path():
    return os.path.join(db_dir(), COUNT_FILE_NAME)


def times_path():
    return os.path.join(db_dir(), TIMES_FILE_NAME)


def conf_path():
    return os.path.join(conf_dir(), CONF_FILE_NAME)


def password_path():
    """数据库配置页口令文件：conf/pwd（无后缀）。"""
    return os.path.join(conf_dir(), PASSWORD_FILE_NAME)


# --------------------------------------------------------------------------
# 运行环境自检与首次启动初始化
# --------------------------------------------------------------------------
def ensure_dirs():
    """确保 db/ 与 conf/ 目录存在。"""
    for directory in (db_dir(), conf_dir()):
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass


def environment_missing():
    """返回缺失的必需目录列表；返回空列表表示运行环境齐备。"""
    missing = []
    for directory in (db_dir(), conf_dir()):
        if not os.path.isdir(directory):
            missing.append(directory)
    return missing


def environment_ready():
    return not environment_missing()


def migrate_legacy_db():
    """数据兼容：把旧版的 db/db.txt 迁移成 db/db（仅在目标不存在时执行）。"""
    legacy = legacy_db_path()
    if os.path.exists(db_path()) or not os.path.exists(legacy):
        return False
    try:
        os.replace(legacy, db_path())
        return True
    except OSError:
        pass
    try:
        atomic_write_text(db_path(), read_text(legacy) or "")
        os.remove(legacy)
        return True
    except OSError:
        return False


def bootstrap():
    """首次以管理员身份启动时创建运行环境，返回本次创建的条目列表。"""
    created = []
    for directory in (app_root(), db_dir(), conf_dir()):
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
            created.append(directory)
    migrate_legacy_db()
    if not os.path.exists(db_path()):
        for name in (DB_FILE_NAME, LEGACY_DB_FILE_NAME):
            bundled = read_text(os.path.join(resource_root(), DB_DIR_NAME, name))
            if bundled is not None:
                atomic_write_text(db_path(), bundled)
                created.append(db_path())
                break
    return created


# --------------------------------------------------------------------------
# 通用文本读写
# --------------------------------------------------------------------------
def read_text(path):
    """读取 UTF-8 文本；文件不存在或解码失败返回 None。"""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def atomic_write_text(path, text):
    """原子写文本：先写同目录临时文件，再 os.replace 覆盖目标文件。"""
    directory = os.path.dirname(path)
    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


# --------------------------------------------------------------------------
# db/db：姓名数据库（Base64 逐行）
# --------------------------------------------------------------------------
def encode_name(name):
    """姓名 -> Base64 ASCII 文本（先按 UTF-8 编码，再 Base64）。"""
    return base64.b64encode(str(name).encode("utf-8")).decode("ascii")


def decode_name(token):
    """Base64 文本 -> 姓名；失败返回 None（该行按注释或脏数据忽略）。"""
    text = (token or "").strip()
    if not text:
        return None
    try:
        return base64.b64decode(text).decode("utf-8")
    except Exception:
        return None


def decode_names(text):
    """数据库文本 -> 姓名列表（保持文件中的原始顺序，跳过空行与坏行）。"""
    names = []
    for line in (text or "").splitlines():
        token = line.strip()
        if not token or token.startswith("#"):
            continue
        name = decode_name(token)
        if name:
            names.append(name)
    return names


def encode_names(names):
    """姓名列表 -> 数据库文本：逐个 Base64，按原顺序每行一个（末尾补换行）。"""
    return "".join(encode_name(name) + "\n" for name in names if str(name).strip())


def load_names():
    """读取数据库文件 db/db（旧名 db/db.txt 自动迁移）。"""
    migrate_legacy_db()
    path = db_path()
    text = read_text(path)
    if text is None:
        # 首次运行（例如打包版）时从内置资源释放一份，保证“解压即可用”
        bundled = None
        for name in (DB_FILE_NAME, LEGACY_DB_FILE_NAME):
            bundled = read_text(os.path.join(resource_root(), DB_DIR_NAME, name))
            if bundled is not None:
                break
        if bundled is not None:
            try:
                atomic_write_text(path, bundled)
            except OSError:
                pass
            text = bundled
    return decode_names(text or "")


def has_database():
    """数据库是否已有可用姓名（启动时决定是否直接弹出配置页）。"""
    return bool(load_names())


def save_names(names):
    """用给定姓名列表覆盖数据库文件（“配置数据库”功能使用）。

    规则：按用户输入顺序，逐个转 Base64，每行一个，整体覆盖。
    """
    ensure_dirs()
    atomic_write_text(db_path(), encode_names(names))


# --------------------------------------------------------------------------
# db/count.db 与 db/times.txt：“姓名<TAB>次数”格式
# --------------------------------------------------------------------------
def parse_pairs(text):
    """解析 “姓名<TAB>次数” 文本为字典；空行与 # 注释行忽略，坏行忽略。"""
    data = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("\t")
        name = name.strip()
        if not sep or not name:
            continue
        try:
            data[name] = int(value.strip())
        except ValueError:
            continue
    return data


def format_pairs(mapping):
    """字典 -> 稳定文本（按姓名排序，便于人工比对与版本管理）。"""
    lines = [_HEADER_COUNT]
    for name in sorted(mapping):
        lines.append("%s\t%d" % (name, int(mapping[name])))
    return "\n".join(lines) + "\n"


def load_pairs(path):
    return parse_pairs(read_text(path))


def save_pairs(path, mapping):
    ensure_dirs()
    atomic_write_text(path, format_pairs(mapping))


def load_counts():
    """读取 db/count.db（每个姓名被抽中过的累计次数）。"""
    return load_pairs(count_path())


def save_counts(mapping):
    """写 db/count.db。仅在抽取发生或重置统计后调用，避免无谓 I/O。"""
    save_pairs(count_path(), mapping)


def load_times():
    """读取 db/times.txt（SpMode=2 的保底计数），供下次启动继承。"""
    return load_pairs(times_path())


def save_times(mapping):
    """写 db/times.txt。仅在 SpNum 保底计数发生变化时调用。"""
    save_pairs(times_path(), mapping)


# --------------------------------------------------------------------------
# conf/conf.txt：设置项文本
# --------------------------------------------------------------------------
def load_conf_text():
    """读取 conf/conf.txt 原文；不存在返回 None（由 appconfig 使用默认值）。"""
    return read_text(conf_path())


def save_conf_text(text):
    """覆盖写 conf/conf.txt（设置页“保存/应用”触发）。"""
    ensure_dirs()
    atomic_write_text(conf_path(), text)


# --------------------------------------------------------------------------
# conf/pwd：数据库配置页口令
# --------------------------------------------------------------------------
def password_digest(text):
    """口令 -> SHA-256 十六进制（“加密存放”模式下落盘的内容）。"""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def load_password():
    """读取口令，返回 (mode, value)；未设置口令时返回 (None, None)。

    兼容极简写法：整个文件只有一行内容时按明文口令处理。
    """
    text = read_text(password_path())
    if text is None:
        return (None, None)
    data = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    value = data.get("value")
    if not value:
        stripped = text.strip()
        if stripped and "\n" not in stripped and "=" not in stripped:
            return (PASSWORD_MODE_PLAIN, stripped)
        return (None, None)
    mode = data.get("mode", PASSWORD_MODE_PLAIN)
    if mode not in (PASSWORD_MODE_PLAIN, PASSWORD_MODE_HASH):
        mode = PASSWORD_MODE_PLAIN
    return (mode, value)


def has_password():
    """是否已设置进入数据库配置页的口令（默认无口令）。"""
    return load_password()[0] is not None


def save_password(value, encrypted=True):
    """保存口令；encrypted=True 时只落盘 SHA-256 哈希值。"""
    ensure_dirs()
    mode = PASSWORD_MODE_HASH if encrypted else PASSWORD_MODE_PLAIN
    stored = password_digest(value) if encrypted else str(value)
    atomic_write_text(password_path(),
                      "%smode=%s\nvalue=%s\n" % (_HEADER_PASSWORD, mode, stored))


def clear_password():
    """清除口令（恢复“无口令可直接进入配置页”的默认状态）。"""
    try:
        os.remove(password_path())
    except OSError:
        pass


def verify_password(text):
    """校验口令：无口令时恒为 True；有口令时按保存方式比对（哈希或明文）。"""
    mode, value = load_password()
    if mode is None:
        return True
    candidate = password_digest(text) if mode == PASSWORD_MODE_HASH else str(text)
    return hmac.compare_digest(candidate, value)
