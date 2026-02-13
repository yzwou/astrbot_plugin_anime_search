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
        # 注册 Tool
        self.context.add_llm_tools(AnimeTraceTool())

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_aiocqhttp(self, event: AstrMessageEvent):
        """
        处理流程：
        1. 提取图片 URL（包括直接发送和引用回复的图片）
        2. 将图片 URL 注入到 Prompt 中，让 AI 知道真实的链接
        3. 调用 tool_loop_agent，AI 会自动使用工具识别
        """

        # ===== 1️⃣ 改进的图片提取函数 =====
        async def extract_image_source(ev: AstrMessageEvent):
            msg_chain = ev.message_obj.message

            # 优先检查直接发送的图片
            for seg in msg_chain:
                if isinstance(seg, Image):
                    return seg.url

            # 检查引用回复中的图片
            for seg in msg_chain:
                if isinstance(seg, Reply):
                    # Reply 组件的 chain 属性包含被引用消息的所有组件
                    if hasattr(seg, 'chain') and seg.chain:
                        for reply_seg in seg.chain:
                            if isinstance(reply_seg, Image):
                                return reply_seg.url

            return None

        # ===== 2️⃣ 获取图片 URL =====
        image_url = await extract_image_source(event)

        # 获取用户的文本消息
        user_text = event.message_str

        # ===== 3️⃣ 构建注入了图片信息的 Prompt =====
        prompt_to_ai = user_text

        if image_url:
            # 关键步骤：将真实的图片 URL 显式告诉 AI
            # 这样 AI 在调用工具时就会使用这个真实 URL，而不是瞎编
            prompt_to_ai = (
                f"用户发送了一张图片或回复了图片，图片的真实链接是：{image_url}\n"
                f"用户附言：{user_text}\n"
                f"请识别这张图片。"
            )

        # ===== 4️⃣ 调用 Agent 处理 =====
        umo = event.unified_msg_origin
        prov_id = await self.context.get_current_chat_provider_id(umo)

        # 调用 tool_loop_agent，AI 会自动决定是否调用 AnimeTraceTool
        llm_resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=prov_id,
            prompt=prompt_to_ai,  # 使用注入了图片 URL 的 prompt
            tools=ToolSet([AnimeTraceTool()]),  # 确保工具可用
            max_steps=30,
        )

        # 返回结果
        yield event.plain_result(llm_resp.completion_text)
