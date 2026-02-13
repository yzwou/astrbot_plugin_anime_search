from .tools.search_anime import AnimeTraceTool

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Image, Reply
from astrbot.core.agent.tool import ToolSet
import json


@register(
    "astrbot_plugin_anime_search",
    "Yuwai",
    "AstrBot 辅助识别二次元图片",
    "1.0.0"
)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(AnimeTraceTool())

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_aiocqhttp(self, event: AstrMessageEvent):
        # ===== 1️⃣ 触发条件检查 (解决越位问题) =====

        # 检查是否是私聊
        is_private = event.message_obj.group_id is None

        # 检查是否被 @ (群聊环境)
        is_at_me = event.is_at_or_wake_command

        # 如果既不是私聊，也没有被 @，则直接退出，交给其他插件（如 Heartflow）
        if not (is_private or is_at_me):
            return

        # ===== 2️⃣ 提取图片 (只有满足触发条件才执行) =====
        async def extract_image_source(ev: AstrMessageEvent):
            msg_chain = ev.message_obj.message
            for seg in msg_chain:
                # 检查普通图片
                if seg.type == "image":
                    return seg.url
                # 检查回复中的图片
                if hasattr(seg, "chain"):
                    for sub in seg.chain:
                        if sub.type == "image":
                            return sub.url
            return None

        image_source = await extract_image_source(event)

        # 如果没有找到图片，直接退出，不报错也不提示
        # 这样 AI 就会按照正常的聊天逻辑回复你（比如回答“你好”）
        if not image_source:
            return

        # ===== 3️⃣ 调用工具与 AI 交互 (仅在有图片时执行) =====
        # ... 后续逻辑同前 ...
        tool = AnimeTraceTool()
        result = await tool.run(event, image_source=image_source)

        if result and result.content:
            json_data = result.content[0].text
            # 这里建议增加一个日志，方便调试
            # self.context.logger.info(f"AnimeTrace Result: {json_data}")

            prompt = f"系统识别到图片数据：{json_data}。请结合上下文简洁地告诉用户这是谁。"
            provider = self.context.get_using_provider()

            if provider:
                final_response = ""
                async for response in provider.text_chat(prompt, session=event.session):
                    if response.completion_text:
                        final_response = response.completion_text

                if final_response:
                    yield event.plain_result(final_response)