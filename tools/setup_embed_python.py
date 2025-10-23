import os
import sys
import platform
import shutil
import subprocess
import urllib.request
import zipfile
import tarfile
import stat  # 用於在 macOS/Linux 上設定檔案權限

sys.stdout.reconfigure(encoding="utf-8")

# --- 配置 ---
PYTHON_VERSION_TARGET = "3.13.7"  # 目標 Python 版本
# python-build-standalone 的發佈標籤，需要與 PYTHON_VERSION_TARGET 相容
# 前往 https://github.com/indygreg/python-build-standalone/releases 查看最新標籤和可用版本
PYTHON_BUILD_STANDALONE_RELEASE_TAG = "20250828"
DEST_DIR = os.path.join("install", "python")  # Python 安裝的目標目錄


def download_file(url, dest_path):
    """下載檔案到指定路徑"""
    print(f"正在下載: {url}")
    print(f"儲存到: {dest_path}")
    # 確保目標目錄存在
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        print("下載完成")
    except urllib.error.HTTPError as e:
        print(f"HTTP 錯誤 {e.code}: {e.reason} (URL: {url})")
        raise
    except urllib.error.URLError as e:
        print(f"URL 錯誤: {e.reason} (URL: {url})")
        raise
    except Exception as e:
        print(f"下載過程中發生錯誤: {e}")
        raise


def extract_zip(zip_path, dest_dir):
    """解壓 ZIP 檔案"""
    print(f"正在解壓 ZIP: {zip_path} 到 {dest_dir}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(dest_dir)
    print("ZIP 解壓完成")


def extract_tar(tar_path, dest_dir):
    """解壓 TAR (tar.gz, tar.xz, tar.bz2) 檔案"""
    print(f"正在解壓 TAR: {tar_path} 到 {dest_dir}")
    try:
        # 'r:*' 會自動檢測壓縮格式
        with tarfile.open(tar_path, "r:*") as tar_ref:
            tar_ref.extractall(path=dest_dir)
        print("TAR 解壓完成")
    except tarfile.ReadError as e:
        print(f"Tarfile 讀取錯誤: {e}，檔案可能已損壞或不是有效的 TAR 封存檔")
        raise
    except Exception as e:
        print(f"TAR 解壓過程中發生錯誤: {e}")
        raise


def get_python_executable_path(base_dir, os_type):
    """取得已安裝 Python 環境中的可執行檔路徑"""
    if os_type == "Windows":
        return os.path.join(base_dir, "python.exe")
    elif os_type == "Darwin":  # macOS
        # python-build-standalone 通常包含 python 和 python3
        # 優先使用 python3 (通常 python 是指向 python3 的符號鏈結)
        py3_path = os.path.join(base_dir, "bin", "python3")
        py_path = os.path.join(base_dir, "bin", "python")
        if os.path.exists(py3_path):
            return py3_path
        elif os.path.exists(py_path):  # 做為備選
            return py_path
        else:
            return None  # 未找到
    return None


def ensure_pip(python_executable, python_install_dir):
    """安裝 pip"""
    if not python_executable or not os.path.exists(python_executable):
        print("錯誤: 找不到 Python 可執行檔，無法安裝 pip")
        return False

    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    # 將 get-pip.py 下載到 Python 安裝目錄下，執行後再刪除
    get_pip_script_path = os.path.join(python_install_dir, "get-pip.py")

    print(f"正在下載 get-pip.py 從 {get_pip_url}")
    try:
        download_file(get_pip_url, get_pip_script_path)
    except Exception as e:
        print(f"下載 get-pip.py 失敗: {e}")
        return False

    print("正在使用 get-pip.py 安裝 pip...")
    try:
        # 在 Python 安裝目錄下執行 get-pip.py
        subprocess.run([python_executable, get_pip_script_path], check=True)
        print("pip 安裝成功")
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"pip 安裝失敗: {e}")
        return False
    finally:
        if os.path.exists(get_pip_script_path):
            os.remove(get_pip_script_path)  # 清理下載的腳本


def main():
    os_type = platform.system()
    os_arch = platform.machine()

    print(f"操作系統: {os_type}, 架構: {os_arch}")
    print(f"目標 Python 版本: {PYTHON_VERSION_TARGET}")
    print(f"目標安裝目錄: {DEST_DIR}")

    # 檢查 Python 是否已經存在
    python_exe_check = get_python_executable_path(DEST_DIR, os_type)
    if python_exe_check and os.path.exists(python_exe_check):
        print(f"Python 似乎已存在於 {DEST_DIR} (找到: {python_exe_check})")
        if ensure_pip(python_exe_check, DEST_DIR):
            print("Python 和 pip 已設定，跳過安裝")
        else:
            print("Python 存在但 pip 設定失敗，請檢查")
        return

    if os.path.exists(DEST_DIR):
        print(f"目標目錄 {DEST_DIR} 已存在但 Python 未完全配置，將嘗試清理並重新安裝")
        try:
            shutil.rmtree(DEST_DIR)
        except OSError as e:
            print(f"清理目錄 {DEST_DIR} 失敗: {e}，請手動刪除後重試")
            return

    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"已建立目錄: {DEST_DIR}")

    python_executable_final_path = None

    if os_type == "Windows":
        # 在 Windows ARM64 環境中，platform.machine() 可能錯誤返回 AMD64
        # 需要檢查處理器識別來確定真實架構
        processor_identifier = os.environ.get("PROCESSOR_IDENTIFIER", "")

        # 檢查是否為 ARM64 處理器
        if "ARMv8" in processor_identifier or "ARM64" in processor_identifier:
            print(f"檢測到 ARM64 處理器: {processor_identifier}")
            os_arch = "ARM64"

        # 映射 platform.machine() 到 Python 官網的命名
        arch_mapping = {
            "AMD64": "amd64",
            "x86_64": "amd64",
            "ARM64": "arm64",
            "aarch64": "arm64",
        }
        win_arch_suffix = arch_mapping.get(os_arch, os_arch.lower())

        if win_arch_suffix not in ["amd64", "arm64"]:
            print(f"錯誤: 不支援的 Windows 架構: {os_arch} -> {win_arch_suffix}")
            return

        print(f"使用 Windows 架構: {os_arch} -> {win_arch_suffix}")

        download_url = f"https://www.python.org/ftp/python/{PYTHON_VERSION_TARGET}/python-{PYTHON_VERSION_TARGET}-embed-{win_arch_suffix}.zip"
        zip_filename = f"python-{PYTHON_VERSION_TARGET}-embed-{win_arch_suffix}.zip"
        zip_filepath = os.path.join(DEST_DIR, zip_filename)  # 下載到目標目錄內再解壓

        try:
            download_file(download_url, zip_filepath)
            extract_zip(zip_filepath, DEST_DIR)
        except Exception as e:
            print(f"Windows Python 下載或解壓失敗: {e}")
            return
        finally:
            if os.path.exists(zip_filepath):
                os.remove(zip_filepath)

        # 修改 ._pth 檔
        # pth 檔名格式如: python312._pth for Python 3.12.x
        version_nodots = PYTHON_VERSION_TARGET.replace(".", "")[:3]
        pth_filename_pattern = f"python{version_nodots}._pth"

        pth_file_path = os.path.join(DEST_DIR, pth_filename_pattern)
        if not os.path.exists(pth_file_path):
            # 有時 embeddable zip 中 pth 檔的命名可能不帶 minor version，如 python3._pth
            # 嘗試查找所有 python*._pth 檔
            found_pth_files = [
                f
                for f in os.listdir(DEST_DIR)
                if f.startswith("python") and f.endswith("._pth")
            ]
            if found_pth_files:
                pth_file_path = os.path.join(DEST_DIR, found_pth_files[0])
            else:
                print(f"錯誤: 未在 {DEST_DIR} 中找到 ._pth 檔")
                return

        print(f"正在修改 ._pth 檔: {pth_file_path}")
        try:
            with open(pth_file_path, "r+", encoding="utf-8") as f:
                content = f.read()
                # 取消註釋 import site
                content = content.replace("#import site", "import site")
                content = content.replace(
                    "# import site", "import site"
                )  # 處理可能的空格

                # 添加必要的相對路徑 (相對於 DEST_DIR)
                required_paths = [".", "Lib", "Lib\\site-packages", "DLLs"]
                for p_path in required_paths:
                    if p_path not in content.splitlines():  # 避免重複添加
                        content += f"\n{p_path}"
                f.seek(0)
                f.write(content)
                f.truncate()
            print("._pth 檔修改完成")
        except Exception as e:
            print(f"修改 ._pth 檔失敗: {e}")
            return
        python_executable_final_path = get_python_executable_path(DEST_DIR, os_type)

    elif os_type == "Darwin":  # macOS
        # 映射 platform.machine() 到 python-build-standalone 的架構名稱
        arch_mapping = {"x86_64": "x86_64", "arm64": "aarch64", "aarch64": "aarch64"}
        pbs_arch = arch_mapping.get(os_arch, os_arch)

        if pbs_arch not in ["x86_64", "aarch64"]:
            print(f"錯誤: 不支援的 macOS 架構: {os_arch} -> {pbs_arch}")
            return

        # 檔名格式: cpython-{PYTHON_VERSION}+{RELEASE_TAG_DATE}-{ARCH}-apple-darwin-install_only.tar.gz
        pbs_filename = f"cpython-{PYTHON_VERSION_TARGET}+{PYTHON_BUILD_STANDALONE_RELEASE_TAG}-{pbs_arch}-apple-darwin-install_only.tar.gz"
        download_url = f"https://github.com/indygreg/python-build-standalone/releases/download/{PYTHON_BUILD_STANDALONE_RELEASE_TAG}/{pbs_filename}"
        tar_filename = pbs_filename  # 使用原始檔名
        tar_filepath = os.path.join(DEST_DIR, tar_filename)  # 下載到目標目錄內

        try:
            download_file(download_url, tar_filepath)
            # python-build-standalone 的套件解壓后通常包含一个名為 'python' 的頂層目錄
            # 需要將這個 'python' 目錄的內容移動到 DEST_DIR
            temp_extract_dir = os.path.join(DEST_DIR, "_temp_extract")
            os.makedirs(temp_extract_dir, exist_ok=True)
            extract_tar(tar_filepath, temp_extract_dir)

            extracted_python_root = os.path.join(temp_extract_dir, "python")
            if os.path.isdir(extracted_python_root):
                print(f"正在移動 {extracted_python_root} 的內容到 {DEST_DIR}")
                for item_name in os.listdir(extracted_python_root):
                    s = os.path.join(extracted_python_root, item_name)
                    d = os.path.join(DEST_DIR, item_name)
                    shutil.move(s, d)
                shutil.rmtree(temp_extract_dir)  # 清理臨時解壓目錄
            else:
                print(f"錯誤: 解壓後未找到預期的 'python' 子目錄於 {temp_extract_dir}")
                shutil.rmtree(temp_extract_dir)
                return
        except Exception as e:
            print(f"macOS Python 下載或解壓失敗: {e}")
            if os.path.exists(temp_extract_dir):
                shutil.rmtree(temp_extract_dir)
            return
        finally:
            if os.path.exists(tar_filepath):
                os.remove(tar_filepath)

        # 為 bin 目錄下的可執行檔設定執行權限
        bin_dir = os.path.join(DEST_DIR, "bin")
        if os.path.isdir(bin_dir):
            print(f"正在為 {bin_dir} 中的檔案設定執行權限...")
            for item_name in os.listdir(bin_dir):
                item_path = os.path.join(bin_dir, item_name)
                if os.path.isfile(item_path) and not os.access(item_path, os.X_OK):
                    try:
                        current_mode = os.stat(item_path).st_mode
                        os.chmod(
                            item_path,
                            current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
                        )
                        print(f"已為 {item_name} 設定執行權限")
                    except Exception as e:
                        print(f"為 {item_name} 設定執行權限失敗: {e}")
        python_executable_final_path = get_python_executable_path(DEST_DIR, os_type)
    else:
        print(f"錯誤: 不支援的操作系統: {os_type}")
        return

    if not python_executable_final_path or not os.path.exists(
        python_executable_final_path
    ):
        print("錯誤: 安裝後未找到 Python 可執行檔")
        return

    print(f"Python 環境已初步設定於: {DEST_DIR}")
    print(f"Python 可執行檔: {python_executable_final_path}")

    # 安裝 pip
    if ensure_pip(python_executable_final_path, DEST_DIR):
        print("嵌入式 Python 環境安裝與 pip 設定完成")
    else:
        print("嵌入式 Python 環境安裝完成，但 pip 設定失敗")


if __name__ == "__main__":
    main()
