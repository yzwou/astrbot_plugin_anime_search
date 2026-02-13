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
        # ===== 提取图片 (只有满足触发条件才执行) =====
        async def extract_image_source(ev: AstrMessageEvent):
            msg_chain = ev.message_obj.message
            for seg in msg_chain:
                try:
                    return seg.url
                except AttributeError:
                    try:
                        return seg.chain[0].url
                    except AttributeError:
                        pass

                return None

        image_source = await extract_image_source(event)

        if not image_source:
            return

        tool = AnimeTraceTool()
        result = await tool.run(event, image_source=image_source)

        if result and result.content:
            json_data = result.content[0].text

            prompt = f"系统识别到图片数据：{json_data}。请结合上下文简洁地告诉用户这是谁。"
            provider = self.context.get_using_provider()

            if provider:
                final_response = ""
                async for response in provider.text_chat(prompt, session=event.session):
                    if response.completion_text:
                        final_response = response.completion_text

                if final_response:
                    yield event.plain_result(final_response)
