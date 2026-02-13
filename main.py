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
            yield event.plain_result(str(msg_chain))
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

            prompt = (
                f"系统识别到图片数据：{json_data}。\n"
                f"请结合上下文，用自然且简洁的语言告诉用户这张图的角色和作品信息。"
            )

            provider = self.context.get_using_provider()

            if provider:
                try:
                    response = await provider.text_chat(prompt, session=event.session)

                    if response and response.completion_text:
                        yield event.plain_result(response.completion_text)
                except Exception as e:
                    self.context.logger.error(f"LLM Chat Error: {e}")
                    # 如果 AI 调用失败，退而求其次发送原始数据或友好提示
                    # yield event.plain_result(f"识别到角色：{json_data}")
        else:
            # 如果是明确触发了识别但没结果，可以给个提示
            yield event.plain_result("抱歉，我没能认出这张图片里的角色。")