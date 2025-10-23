import os
import sys
import subprocess
import argparse
import platform
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def get_platform_tag():
    """自動檢測當前平台並返回對應的平台標籤"""
    os_type = platform.system()
    os_arch = platform.machine()

    print(f"檢測到操作系統: {os_type}, 架構: {os_arch}")

    if os_type == "Windows":
        # 在 Windows ARM64 環境中 platform.machine() 可能錯誤地回傳 AMD64
        # 需要檢查處理器識別碼以確定真實架構
        processor_identifier = os.environ.get("PROCESSOR_IDENTIFIER", "")

        # 檢查是否為 ARM64 處理器
        if "ARMv8" in processor_identifier or "ARM64" in processor_identifier:
            print(f"檢測到 ARM64 處理器: {processor_identifier}")
            os_arch = "ARM64"

        # 映射 platform.machine() 到 pip 的平台標籤
        arch_mapping = {
            "AMD64": "win_amd64",
            "x86_64": "win_amd64",
            "ARM64": "win_arm64",
            "aarch64": "win_arm64",
        }
        platform_tag = arch_mapping.get(os_arch, f"win_{os_arch.lower()}")

    elif os_type == "Darwin":  # macOS
        # 映射 platform.machine() 到 pip 的平台標籤
        arch_mapping = {
            "x86_64": "macosx_10_9_x86_64",
            "arm64": "macosx_11_0_arm64",
            "aarch64": "macosx_11_0_arm64",
        }
        platform_tag = arch_mapping.get(os_arch, f"macosx_10_9_{os_arch}")

    elif os_type == "Linux":
        # 映射 platform.machine() 到 pip 的平台標籤
        arch_mapping = {
            "x86_64": "linux_x86_64",
            "aarch64": "linux_aarch64",
            "arm64": "linux_aarch64",
        }
        platform_tag = arch_mapping.get(os_arch, f"linux_{os_arch}")

    else:
        raise ValueError(f"不支援的操作系統: {os_type}")

    print(f"使用平台標籤: {platform_tag}")
    return platform_tag


def download_dependencies(deps_dir, platform_tag):
    """下載依賴到指定目錄"""
    # 建立 deps 目錄
    deps_path = Path(deps_dir)
    deps_path.mkdir(parents=True, exist_ok=True)

    print(f"開始下載平台 {platform_tag} 的依賴到 {deps_dir}")

    # 從 requirements.txt 讀取依賴
    requirements_file = Path("assets/requirements.txt")
    if not requirements_file.exists():
        print("錯誤: requirements.txt 檔案不存在")
        return False

    # 首先嘗試下載平台專屬的 wheel 檔案
    try:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "-r",
            str(requirements_file),
            "-d",
            str(deps_path),
            "--platform",
            platform_tag,
            "--only-binary=:all:",
        ]

        print(f"執行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)

        if result.stderr:
            print("警告訊息:")
            print(result.stderr)

        # 列出下載的檔案
        whl_files = list(deps_path.glob("*.whl"))
        print(f"\n下載的 wheel 檔案 ({len(whl_files)} 個):")
        for whl_file in whl_files:
            print(f"  {whl_file.name}")

        print(f"依賴已下載到: {deps_path}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"平台專屬下載失敗: {e}")
        if e.stderr and (
            "Could not find a version" in e.stderr
            or "No matching distribution" in e.stderr
        ):
            print("某些套件可能不支援目前平台，嘗試通用下載策略...")

            # 回退到通用下載策略（不指定平台）
            try:
                cmd_fallback = [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    "-r",
                    str(requirements_file),
                    "-d",
                    str(deps_path),
                    "--only-binary=:all:",
                ]

                print(f"執行回退命令: {' '.join(cmd_fallback)}")
                result = subprocess.run(
                    cmd_fallback, check=True, capture_output=True, text=True
                )
                print(result.stdout)

                if result.stderr:
                    print("警告訊息:")
                    print(result.stderr)

                # 列出下載的檔案
                whl_files = list(deps_path.glob("*.whl"))
                print(f"\n下載的 wheel 檔案 ({len(whl_files)} 個):")
                for whl_file in whl_files:
                    print(f"  {whl_file.name}")

                print(f"通用策略已下載到: {deps_path}")
                return True

            except subprocess.CalledProcessError as e2:
                print(f"通用策略也失敗: {e2}")
                if e2.stdout:
                    print("stdout:", e2.stdout)
                if e2.stderr:
                    print("stderr:", e2.stderr)
                return False
        else:
            if e.stdout:
                print("stdout:", e.stdout)
            if e.stderr:
                print("stderr:", e.stderr)
            return False


def main():
    parser = argparse.ArgumentParser(description="下載 Python 依賴到 deps 目錄")
    parser.add_argument(
        "--deps-dir", default="assets/deps", help="依賴下載目錄 (預設:assets/deps)"
    )

    args = parser.parse_args()

    try:
        # 自動檢測平台
        platform_tag = get_platform_tag()

        # 下載依賴
        success = download_dependencies(args.deps_dir, platform_tag)

        if success:
            print("==== 依賴下載成功 ====")
            sys.exit(0)
        else:
            print("==== 依賴下載失敗 ====")
            sys.exit(1)

    except Exception as e:
        print(f"腳本執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
