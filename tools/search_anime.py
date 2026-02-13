from mcp.types import CallToolResult, TextContent
from dataclasses import dataclass, field
from astrbot.api import FunctionTool
from astrbot.api.event import AstrMessageEvent

import httpx
import json
import os

# =========================
# AnimeTrace Tool（修复版：处理 I/O 问题，通过读取 bytes 内容）
# =========================
@dataclass
class AnimeTraceTool(FunctionTool):
    name: str = "trace_anime"
    description: str = (
        "识别二次元图片中的角色和作品，使用 AnimeTrace API 返回角色、作品信息。"
        "调用时必须提供 image_source 参数（图片的 URL、本地路径或 Base64 字符串（data:image/...;base64,...），）。"
        "当用户发送图片并询问出处/角色时，使用此工具。"
    )
    parameters: dict = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "image_source": {
                    "type": "string",
                    "description": "图片的 URL（http/https）、本地路径或 Base64 字符串（data:image/...;base64,...）"
                }
            },
            "required": ["image_source"]
        }
    )

    async def run(self, event: AstrMessageEvent, image_source: str) -> CallToolResult:
        if not image_source:
            return CallToolResult(
                content=[TextContent(type="text", text="NO_IMAGE")]
            )

        api_url = "https://api.animetrace.com/v1/search"

        # 公共参数（根据文档，model 和 ai_detect 必填）
        data = {
            "is_multi": 1,
            "ai_detect": 1
        }

        files = None

        try:
            if os.path.exists(image_source):  # 本地路径：读取 bytes 内容
                with open(image_source, "rb") as f:
                    content = f.read()
                files = {"file": ("image.jpg", content, "image/jpeg")}

            elif image_source.startswith("data:"):  # Base64：提取纯 base64 字符串
                # 提取 base64 部分（忽略 data:image/...;base64, 前缀）
                if "," in image_source:
                    base64_data = image_source.split(",", 1)[1]
                else:
                    base64_data = image_source
                data["base64"] = base64_data
            else:  # 假设为 URL
                data["url"] = image_source

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(api_url, data=data, files=files)
                resp.raise_for_status()
                response_data = resp.json()

            code = response_data.get("code")
            if code != 0:
                msg = response_data.get("msg", "未知错误")
                return CallToolResult(
                    content=[TextContent(type="text", text=f"API_ERROR: Code {code} - {msg}")]
                )

            # 提取结果
            results = response_data.get("data", [])
            if not results:
                return CallToolResult(
                    content=[TextContent(type="text", text="NO_RESULT")]
                )

            # 取 top 结果
            top = results[0].get("character")[0]
            char = top.get("character", "未知角色")
            anime = top.get("work", "未知作品")

            result = {
                "character": char,
                "anime": anime,
            }

            # 如果有多结果，附加前 2 个
            if len(results) > 1:
                result["others"] = [
                    {
                        "character": r.get("char", "未知"),
                        "anime": r.get("anime", "未知"),
                    } for r in results[1:3]
                ]

            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
            )

        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"API_ERROR:{str(e)}")]
            )