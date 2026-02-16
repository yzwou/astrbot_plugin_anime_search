from astrbot.core.message.message_event_result import MessageChain
from .tools.search_anime import AnimeTraceTool

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Image, Reply, At
from astrbot.core.agent.tool import ToolSet
import json


@register(
    "astrbot_plugin_anime_search",
    "Yuwai",
    "AstrBot 辅助识别二次元图片",
    "1.1.0"
)
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(AnimeTraceTool())

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP, priority=500)
    async def on_aiocqhttp(self, event: AstrMessageEvent):
        should_reply = False
        try:
            if event.is_at_or_wake_command:
                should_reply = True
            elif event.message_obj.group_id is None:  # 私聊
                should_reply = True
            else:
                for seg in event.message_obj.message:
                    if seg.type == "At" and str(seg.qq) == "3753686289":  # 群聊At
                        should_reply = True
                        break

        except Exception as e:
            yield event.plain_result(f"Error Except:{e}")

        if not should_reply:
            return

        async def extract_image_source(ev: AstrMessageEvent):
            msg_chain = ev.message_obj.message
            url, text = None, None
            for seg in msg_chain:
                try:
                    url = seg.url
                    break
                except AttributeError:
                    try:
                        url = seg.chain[0].url
                        break
                    except AttributeError:
                        pass

            try:
                text = msg_chain[-1].text
            except (AttributeError, IndexError) as e2:
                pass

            return url, text

        image_source, question = await extract_image_source(event)

        if not image_source:
            return

        tool = AnimeTraceTool()
        result = await tool.run(event, image_source=image_source)

        if result and result.content:
            json_data = result.content[0].text
            prompt = (
                f"系统识别到图片：{image_source}。\n"
                f"图片人物、场景识别结果（不一定完整，仅作为辅助）：{json_data}\n"
                f"用自然且简洁的语言回答用户的问题：{question}"
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