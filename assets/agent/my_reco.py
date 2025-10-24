import json
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.custom_recognition import CustomRecognition
from maa.context import Context

from my_utils import is_new_period, get_logger

logger = get_logger(__name__)


@AgentServer.custom_recognition("CheckSupplyOfficeProduct")
class CheckSupplyOfficeProduct(CustomRecognition):

    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        # 讀取 minos_data.json
        try:
            with open("config/minos_data.json", encoding="utf-8") as f:
                record_data = json.load(f)
        except Exception:
            logger.exception("讀取 config/minos_data.json 失敗")
            return None
        # 找到 is_purchasing 為 True 的商品 key
        product_key = None
        for key, value in record_data.items():
            if value["is_purchasing"] is True:
                product_key = key
                break
        if not product_key:
            logger.error("找不到 is_purchasing 為 True 的商品")
            return None

        # 讀取 supplyoffice_products.json
        try:
            with open("agent/supplyoffice_products.json", encoding="utf-8") as f:
                SUPPLYOFFICE_PRODUCTS = json.load(f)
        except Exception:
            logger.exception("讀取 agent/supplyoffice_products.json 失敗")
            return None
        # 找到該商品的目標訊息
        expected = SUPPLYOFFICE_PRODUCTS[product_key]["expected"]
        is_discounted = SUPPLYOFFICE_PRODUCTS[product_key]["is_discounted"]

        # 商品辨識區域
        roi_list = [
            [330, 100, 280, 230],  # 左上
            [330, 365, 280, 230],  # 左下
            [650, 100, 280, 230],  # 中上
            [650, 365, 280, 230],  # 中下
            [980, 100, 280, 230],  # 右上
            [980, 365, 280, 230],  # 右下
        ]

        # 依序辨識六個區域
        for roi in roi_list:
            try:
                product_detail = context.run_recognition(
                    "MyCustomOCR",
                    argv.image,
                    pipeline_override={
                        "MyCustomOCR": {"roi": roi, "expected": expected}
                    },
                )
                if product_detail is not None:
                    # 若該商品有折扣，需同時辨識到折扣
                    if is_discounted:
                        discount_roi = [roi[0] - 100, roi[1], roi[2] - 50, roi[3]]
                        discount_detail = context.run_recognition(
                            "MyCustomOCR",
                            argv.image,
                            pipeline_override={
                                "MyCustomOCR": {"roi": discount_roi, "expected": "50"}
                            },
                        )
                        if discount_detail is not None:
                            return product_detail.box
                    else:
                        return product_detail.box
            except Exception:
                logger.exception(f"辨識區域 {roi} 發生錯誤")
                continue
        # 六個區域都沒辨識到
        return None


@AgentServer.custom_recognition("VerifyTime")
class VerifyTime(CustomRecognition):
    def analyze(
        self,
        context: Context,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult:

        param = json.loads(argv.custom_recognition_param)
        key = param.get("key")
        period_type = param.get("period_type")
        if not key or not period_type:
            logger.error("未提供 key 或 period_type 參數")
            return None

        # 新增 minos_data.json 檔案
        RECORD_PATH = Path("config/minos_data.json")
        if not RECORD_PATH.exists():
            try:
                RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(RECORD_PATH, "w", encoding="utf-8") as f:
                    json.dump({}, f, indent=4, ensure_ascii=False)
            except Exception:
                logger.exception(f"寫入 {RECORD_PATH} 失敗")
                return None

        # 讀取任務完成時間
        try:
            with open(RECORD_PATH, encoding="utf-8") as f:
                record_data = json.load(f)
            if key not in record_data:
                record_data.setdefault(key, {})
                record_data[key].setdefault("last_purchased_time", 0)
            with open(RECORD_PATH, "w", encoding="utf-8") as f:
                json.dump(record_data, f, indent=4, ensure_ascii=False)
        except Exception:
            logger.exception("讀取任務完成時間失敗")
            return None

        # 判斷完成時間是否在週期內
        last_time = record_data[key]["last_purchased_time"]
        if not is_new_period(last_time, period_type):
            logger.info(f"跳過任務流程：{key}")
            return [0, 0, 0, 0]

        return None
