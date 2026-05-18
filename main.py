import os
import shutil
from pathlib import Path
import asyncio
import jmcomic
from jmcomic import download_album, Feature
from jmcomic import JmOption
import random
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import astrbot.api.message_components as Comp
from astrbot.api import logger
import json
@register("jmutil", "meixu0", "0.0.1", "description")
class JmUtilPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)  
        self.plugin_dir = "data/plugins/astrbot_plugin_jmutil"
        self.download_dir = "data/plugins/astrbot_plugin_jmutil/downloads"
        self.option_dir = "data/plugins/astrbot_plugin_jmutil/option.yml"
    @filter.command_group("jm")
    def jm():
        pass
        
    @jm.command("id")
    async def download_comic_with_given_id(self, event: AstrMessageEvent, givenID: int):
        option = jmcomic.create_option_by_file(self.option_dir)
        download_folder = os.path.join(str(self.download_dir), str(givenID))
        comic_filename = os.path.join(str(self.download_dir), f"{givenID}.pdf")

        def sync_download():
            jmcomic.download_album(
                str(givenID), 
                option, 
                extra=Feature.export_pdf(filename_rule="Aid")
            )
        try:
            await asyncio.to_thread(sync_download)
        except Exception as e:
            yield event.chain_result([Comp.Plain(f"下载失败: {e}")])
            return

        wait_time = 0
        last_size = -1
        stable_count = 0

        while wait_time < 600:
            if os.path.exists(comic_filename):
                current_size = os.path.getsize(comic_filename)
                if current_size == last_size and current_size > 0:
                    stable_count += 1
                    if stable_count >= 3:
                        break
                else:
                    last_size = current_size
                    stable_count = 0
                    
            await asyncio.sleep(1) 
            wait_time += 1

        if not os.path.exists(comic_filename) or stable_count < 3:
            yield event.chain_result([Comp.Text("PDF 文件生成失败")])
            return

        comic_path = Path(comic_filename).resolve()
        logger.info(f"Preparing to send file {comic_path}, exists={comic_path.exists()}, size={comic_path.stat().st_size if comic_path.exists() else 0}")
        try:
            with open(comic_path, "rb") as f:
                f.read(1)
        except Exception as e:
            logger.error(f"Failed to open PDF for sending: {e}")
            yield event.chain_result([Comp.Plain(f"无法读取 PDF 文件: {e}")])
            return

        chain = [
            Comp.File(file=str(comic_path), name=f"{givenID}.pdf")
        ]
        try:
            yield event.chain_result(chain)
        except Exception as e:
            logger.error(f"Failed to send message with file: {e}")
            yield event.chain_result([Comp.Plain(f"发送消息失败: {e}")])
            return

        async def cleanup_after_delay():
            await asyncio.sleep(600)
            try:
                if comic_path.exists() and comic_path.name == f"{givenID}.pdf":
                    comic_path.unlink()
                    logger.info(f"Deleted temp PDF: {comic_path}")
            except Exception as e:
                logger.error(f"Failed to delete temp PDF {comic_path}: {e}")
            try:
                download_folder_path = Path(download_folder).resolve()
                if download_folder_path.is_dir() and download_folder_path.parent == Path(self.download_dir).resolve() and download_folder_path.name == str(givenID):
                    shutil.rmtree(download_folder_path)
                    logger.info(f"Deleted temp download folder: {download_folder_path}")
            except Exception as e:
                logger.error(f"Failed to delete temp folder {download_folder}: {e}")

        asyncio.create_task(cleanup_after_delay())

    async def terminate(self):
        pass