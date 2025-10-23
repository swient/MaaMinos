import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone


def is_new_period(last_ts: int, period_type: str) -> bool:
    """
    :param last_ts: ms timestamp
    :param period_type: "day" | "week" | "month"
    :return: 是否為新的 period
    """

    if last_ts == 0:
        return True

    now = datetime.now(timezone(timedelta(hours=8)))
    last = datetime.fromtimestamp(last_ts / 1000, tz=now.tzinfo)

    if period_type == "day":
        # 今日5點
        today_start = now.replace(hour=5, minute=0, second=0, microsecond=0)
        if now.hour < 5:
            today_start -= timedelta(days=1)
        return last < today_start
    elif period_type == "week":
        # 本週週一0點
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        return last < week_start
    elif period_type == "month":
        # 本月1日0點
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return last < month_start
    else:
        raise ValueError(f"未知的 period_type: {period_type}")


def get_interface_mode() -> str:
    script_root = Path.cwd()
    interface_path = script_root / "interface.json"

    if not interface_path.exists():
        raise FileNotFoundError("找不到 interface.json")

    if script_root.name == "assets":
        return "DEBUG"
    else:
        return "INFO"


def get_logger(name: str, level: int = None) -> logging.Logger:
    """
    :param name: logger 名稱
    :param level: stderr handler 的 logging 等級
    :return: logging.Logger 實例
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 清除舊 handler，避免重複
    if logger.hasHandlers():
        logger.handlers.clear()

    # 設定 stderr handler 的等級
    if level is None:
        # 取得 interface_mode
        interface_mode = get_interface_mode()

        if interface_mode == "INFO":
            stream_level = logging.INFO
        elif interface_mode == "DEBUG":
            stream_level = logging.DEBUG
        else:
            raise ValueError(f"未知的 interface_mode: {interface_mode}")
    else:
        stream_level = level

    # stderr handler，只顯示 [level] 訊息
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(stream_level)
    stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

    # file handler，完整 log 輸出
    log_dir = Path("debug/custom")
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_path = log_dir / f"{date_str}.log"
    file_handler = logging.FileHandler(file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    return logger
