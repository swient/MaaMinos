import json
import time
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.context import Context

from my_utils import is_new_period, get_logger

logger = get_logger(__name__)


@AgentServer.custom_action("BuySupplyOfficeProduct")
class BuySupplyOfficeProduct(CustomAction):

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> bool:

        try:
            with open("agent/supplyoffice_products.json", encoding="utf-8") as f:
                SUPPLYOFFICE_PRODUCTS = json.load(f)
        except Exception:
            logger.exception(f"讀取 agent/supplyoffice_products.json 失敗")
            return False

        # 讀取採購選項
        supply_options = {}
        config_sources = [
            (Path("config/config.json"), "TaskItems", "index"),
            (Path("config/maa_pi_config.json"), "task", "value"),
        ]
        for config_path, task_key, option_key in config_sources:
            if not config_path.exists():
                continue
            try:
                with open(config_path, encoding="utf-8") as f:
                    config = json.load(f)
                    for task in config[task_key]:
                        if task["name"] == "採購部":
                            for item in task["option"]:
                                supply_options[item["name"]] = item[option_key]
                            break
                if supply_options:
                    break
            except Exception:
                logger.exception(f"讀取 {config_path} 失敗")
                return False
        if not supply_options:
            logger.error("讀取 maa config 檔案失敗")
            return False

        # 新增 minos_data.json 檔案
        RECORD_PATH = Path("config/minos_data.json")
        if not RECORD_PATH.exists():
            RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(RECORD_PATH, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=4, ensure_ascii=False)

        # 確保所有商品都已初始化
        with open(RECORD_PATH, encoding="utf-8") as f:
            record_data = json.load(f)
        for key in SUPPLYOFFICE_PRODUCTS.keys():
            record_data.setdefault(key, {})
            record_data[key].setdefault("last_purchased_time", 0)
            record_data[key]["is_purchasing"] = False
        with open(RECORD_PATH, "w", encoding="utf-8") as f:
            json.dump(record_data, f, indent=4, ensure_ascii=False)

        # 執行採購流程
        for key, override in SUPPLYOFFICE_PRODUCTS.items():
            last_time = record_data[key]["last_purchased_time"]
            period_type = override["period_type"]
            if not (supply_options[key] == "Yes" or supply_options[key] == 0):
                continue
            if not is_new_period(last_time, period_type):
                logger.info(f"跳過採購材料：{key}")
                continue
            record_data[key]["is_purchasing"] = True
            logger.info(f"正在採購材料：{key}")
            with open(RECORD_PATH, "w", encoding="utf-8") as f:
                json.dump(record_data, f, indent=4, ensure_ascii=False)
            context.override_pipeline(override)
            result = context.run_task("SupplyOfficeTemplate")
            # 驗證是否執行到 CompletedSupplyOffice 節點
            if (
                result.nodes
                and result.nodes[-1].name == "CompletedSupplyOffice"
                and result.nodes[-1].completed
            ):
                purchase_success = True
            else:
                purchase_success = False
            # 紀錄採購時間
            if purchase_success:
                record_data[key]["last_purchased_time"] = int(time.time() * 1000)
                record_data[key]["is_purchasing"] = False
                with open(RECORD_PATH, "w", encoding="utf-8") as f:
                    json.dump(record_data, f, indent=4, ensure_ascii=False)
        return True
