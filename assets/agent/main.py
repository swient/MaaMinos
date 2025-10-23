import os
import sys
import json
import subprocess
from pathlib import Path

from my_utils import get_logger, get_interface_mode

logger = get_logger(__name__)

current_script_path = os.path.abspath(__file__)
current_script_dir = os.path.dirname(current_script_path)
script_root_dir = os.path.dirname(current_script_dir)

if os.getcwd() != script_root_dir:
    os.chdir(script_root_dir)

if current_script_dir not in sys.path:
    sys.path.insert(0, current_script_dir)

VENV_NAME = ".venv"  # 虛擬環境目錄的名稱
VENV_DIR = Path(script_root_dir) / VENV_NAME

### 虛擬環境相關 ###


def is_running_in_managed_venv():
    """檢查腳本是否在此腳本管理的特定 venv 中運行"""
    current_python = Path(sys.executable).resolve()

    logger.debug(f"當前 Python 解譯器: {current_python}")

    if sys.platform.startswith("win"):
        # Windows: 如果在虛擬環境中，Python 應該在 Scripts 目錄下
        if current_python.parent.name == "Scripts":
            return True
        else:
            logger.debug("當前不在目標虛擬環境中")
            return False
    else:
        # Linux/Unix: 如果在虛擬環境中，Python 應該在 bin 目錄下
        if current_python.parent.name == "bin":
            return True
        else:
            logger.debug("當前不在目標虛擬環境中")
            return False


def ensure_venv_and_relaunch_if_needed():
    """
    確保 venv 存在，並且如果尚未在腳本管理的 venv 中運行，
    則在其中重新啟動腳本，支持 Linux 和 Windows 系統
    """
    logger.info(f"檢測到系統: {sys.platform}，當前 Python 解譯器: {sys.executable}")

    if is_running_in_managed_venv():
        logger.info(f"已在目標虛擬環境 ({VENV_DIR}) 中運行")
        return

    if not VENV_DIR.exists():
        logger.info(f"正在 {VENV_DIR} 創建虛擬環境...")
        try:
            # 使用當前運行此腳本的 Python（系統/外部 Python）
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=True,
                capture_output=True,
            )
            logger.info(f"創建成功")
        except subprocess.CalledProcessError as e:
            logger.error(
                f"創建失敗: {e.stderr.decode(errors='ignore') if e.stderr else e.stdout.decode(errors='ignore')}"
            )
            logger.error("正在退出")
            sys.exit(1)
        except FileNotFoundError:
            logger.error(
                f"命令 '{sys.executable} -m venv' 未找到，請確保 'venv' 模組可用"
            )
            logger.error("無法在沒有虛擬環境的情況下繼續，正在退出")
            sys.exit(1)

    if sys.platform.startswith("win"):
        python_in_venv = VENV_DIR / "Scripts" / "python.exe"
    else:
        python3_path = VENV_DIR / "bin" / "python3"
        python_path = VENV_DIR / "bin" / "python"
        if python3_path.exists():
            python_in_venv = python3_path
        elif python_path.exists():
            python_in_venv = python_path
        else:
            python_in_venv = python3_path  # 默認使用 python3，讓後續錯誤處理捕獲

    if not python_in_venv.exists():
        logger.error(f"在虛擬環境 {python_in_venv} 中未找到 Python 解譯器")
        logger.error("虛擬環境創建可能失敗或虛擬環境結構異常")
        sys.exit(1)

    logger.info(f"正在使用虛擬環境 Python 重新啟動")

    try:
        cmd = [str(python_in_venv)] + sys.argv
        logger.info(f"執行命令: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            env=os.environ.copy(),
            check=False,  # 不在非零退出碼時拋出異常
        )
        # 退出時使用子進程的退出碼
        sys.exit(result.returncode)

    except Exception:
        logger.exception(f"在虛擬環境中重新啟動腳本失敗")
        sys.exit(1)


### 配置相關 ###


def read_pip_config() -> dict:
    config_dir = Path("./config")
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "pip_config.json"
    default_config = {
        "enable_pip_install": True,
        "mirror": "https://pypi.org/simple",
        "backup_mirror": "https://pypi.tuna.tsinghua.edu.cn/simple",
    }
    if not config_path.exists():
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("讀取 pip 配置失敗，使用默認配置")
        return default_config


### 依賴安裝相關 ###


def find_local_wheels_dir():
    """查找本地 deps 目錄中的 whl 檔案"""
    deps_dir = Path(script_root_dir) / "deps"

    if deps_dir.exists() and any(deps_dir.glob("*.whl")):
        whl_count = len(list(deps_dir.glob("*.whl")))
        logger.info(f"發現本地 deps 目錄包含 {whl_count} 個 whl 檔案")
        return deps_dir

    logger.debug("未找到 deps 目錄或目錄中無 whl 檔案")
    return None


def run_pip_command(cmd_args: list[str], operation_name: str) -> bool:
    try:
        logger.info(f"開始 {operation_name}")
        logger.debug(f"執行命令: {' '.join(cmd_args)}")

        # 使用 subprocess.Popen 進行即時輸出
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 將 stderr 重定向到 stdout
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # 行緩衝
            universal_newlines=True,
        )

        # 收集所有輸出用於日誌記錄
        all_output = []

        # 即時讀取並顯示輸出
        for line in iter(process.stdout.readline, ""):
            line = line.rstrip("\n\r")
            if line.strip():  # 只顯示非空行
                print(line)  # 即時顯示到終端
                all_output.append(line)  # 收集到列表中

        # 等待進程結束
        return_code = process.wait()

        # 記錄完整輸出到日誌
        if all_output:
            full_output = "\n".join(all_output)
            logger.debug(f"{operation_name} 輸出:\n{full_output}")

        if return_code == 0:
            logger.info(f"{operation_name} 完成")
            return True
        else:
            logger.error(f"{operation_name} 時出錯，返回碼: {return_code}")
            return False

    except Exception:
        logger.exception(f"{operation_name} 時發生未知異常")
        return False


def install_requirements(req_file="requirements.txt", pip_config=None) -> bool:
    req_path = Path(script_root_dir) / req_file  # 確保相對於項目根目錄
    if not req_path.exists():
        logger.error(f"{req_file} 檔案不存在於 {req_path.resolve()}")
        return False

    # 查找本地 deps 目錄
    deps_dir = find_local_wheels_dir()
    if deps_dir:
        logger.info(f"使用本地 whl 檔案安裝，目錄: {deps_dir}")

        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "-r",
            str(req_path),
            "--no-warn-script-location",
            "--break-system-packages",
            "--find-links",
            str(deps_dir),  # pip 會優先使用這裡的檔案
            "--no-index",  # 禁止線上索引
        ]

        if run_pip_command(cmd, f"從本地 deps 安裝依賴"):
            return True
        else:
            logger.warning("本地 deps 安裝失敗，回退到純線上安裝")

    # 回退到在線安装
    primary_mirror = pip_config.get("mirror", "")
    backup_mirror = pip_config.get("backup_mirror", "")

    if primary_mirror:
        # 使用主鏡像源，只添加一個備用源避免衝突
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "-r",
            str(req_path),
            "--no-warn-script-location",
            "--break-system-packages",
            "-i",
            primary_mirror,
        ]

        # 只添加一個備用源
        if backup_mirror:
            cmd.extend(["--extra-index-url", backup_mirror])
            logger.info(f"使用主源 {primary_mirror} 和備用源 {backup_mirror} 安裝依賴")
        else:
            logger.info(f"使用主源 {primary_mirror} 安裝依賴")

        if run_pip_command(cmd, f"從 {req_path.name} 安裝依賴"):
            return True
        else:
            logger.error("線上安裝失敗")
            return False
    else:
        # 如果沒有配置主鏡像源，使用 pip 的本地全局配置
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-U",
            "-r",
            str(req_path),
            "--no-warn-script-location",
            "--break-system-packages",
        ]

        if run_pip_command(cmd, f"從 {req_path.name} 安裝依賴 (本地全局配置)"):
            return True
        else:
            logger.error("使用 pip 本地全局配置安裝失敗")
            return False


def check_and_install_dependencies():
    """檢查並安裝項目依賴"""
    pip_config = read_pip_config()
    enable_pip_install = pip_config.get("enable_pip_install", True)

    logger.info(f"啟用 pip 安裝依賴: {enable_pip_install}")

    if enable_pip_install:
        logger.info("開始安裝/更新依賴")
        if install_requirements(pip_config=pip_config):
            logger.info("依賴檢查和安裝完成")
        else:
            logger.warning("依賴安裝失敗，程序可能無法正常運行")
    else:
        logger.info("Pip 依賴安裝已禁用，跳過依賴安裝")


def run_agent():
    try:
        from maa.agent.agent_server import AgentServer
        from maa.toolkit import Toolkit

        import my_action
        import my_reco

        Toolkit.init_option("./")

        if len(sys.argv) < 2:
            logger.error("Usage: python main.py <socket_id>")
            logger.error("socket_id is provided by AgentIdentifier.")
            sys.exit(1)

        socket_id = sys.argv[-1]

        AgentServer.start_up(socket_id)
        logger.info("AgentServer 啟動")
        AgentServer.join()
        AgentServer.shut_down()
        logger.info("AgentServer 關閉")
    except Exception:
        logger.exception(f"Agent 運行過程發生錯誤")
        sys.exit(1)


def main():
    if sys.platform.startswith("linux") or get_interface_mode() == "DEBUG":
        ensure_venv_and_relaunch_if_needed()

    check_and_install_dependencies()
    run_agent()


if __name__ == "__main__":
    main()
