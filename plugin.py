from appdirs import *
import codecs
import json
import asyncio
import socketio
from seletrans.api import *
import pyperclip
import sys
from functools import partial
import tempfile
from datetime import datetime
import traceback


APP_NAME = "electron-spirit"
MANIFEST = "manifest.json"
PLUGIN_SETTING = "plugin.setting.json"
DEFAULT_CONFIG = {
    "api": "bing",
    "hooks": {
        "t": ["auto-detect", "zh-Hans"],
        "te": ["en", "zh-Hans"],
        "tz": ["zh-Hans", "en"],
        "ts": ["auto-detect", "zh-Hans", {"tts": True}],
        "tse": ["en", "zh-Hans", {"tts": True}],
        "tsz": ["zh-Hans", "en", {"tts": True}],
        "tc": ["auto-detect", "zh-Hans", {"copy": True}],
        "tce": ["en", "zh-Hans", {"copy": True}],
        "tcz": ["zh-Hans", "en", {"copy": True}],
        "tcs": ["auto-detect", "zh-Hans", {"copy": True, "tts": True}],
        "tcse": ["en", "zh-Hans", {"copy": True, "tts": True}],
        "tcsz": ["zh-Hans", "en", {"copy": True, "tts": True}],
    },
}

o_print = print


def print_flush(*args, **kwargs):
    o_print(*args, **kwargs)
    sys.stdout.flush()


print = print_flush


class PluginApi(socketio.AsyncClientNamespace):
    def __init__(self, parent):
        super().__init__()
        self.elem_count = 0
        self.parent = parent
        self.connected = False

    async def on_connect(self):
        print("Connected")
        if self.connected:
            print("Disconnect because already connected")
            asyncio.get_running_loop().stop()
            return
        await self.parent.setup_connect()
        self.connected = True

    def on_disconnect(self):
        print("Disconnected")
        asyncio.get_running_loop().stop()

    def on_echo(self, data):
        print("Echo:", data)

    def on_echo(self, data):
        print("Echo:", data)

    def on_addInputHook(self, data):
        print("Add input hook:", data)

    def on_delInputHook(self, data):
        print("Del input hook:", data)

    def on_insertCSS(self, data):
        print("Insert css:", data)

    def on_removeCSS(self, data):
        print("Remove css:", data)

    def on_addElem(self, data):
        print("Add elem:", data)
        self.elem_count += 1

    def on_delElem(self, data):
        print("Remove elem:", data)
        self.elem_count -= 1

    def on_showElem(self, data):
        print("Show view:", data)

    def on_hideElem(self, data):
        print("Hide view:", data)

    def on_setBound(self, data):
        print("Set bound:", data)

    def on_setContent(self, data):
        print("Set content:", data)

    def on_setOpacity(self, data):
        print("Set opacity:", data)

    def on_execJSInElem(self, data):
        print("Exec js in elem:", data)

    def on_notify(self, data):
        print("Notify:", data)

    def on_updateOpacity(self, key, opacity):
        print("Update opacity:", key, opacity)

    def on_updateBound(self, key, bound):
        print("Update bound:", key, bound)

    async def on_processContent(self, content):
        print("Process content:", content)
        hook = content.split(" ")[0]
        await self.parent.hooks[hook](content[len(hook) + 1 :])

    def on_modeFlag(self, flags):
        print("Mode flag:", flags)

    def on_elemRemove(self, key):
        print("Elem remove:", key)
        # prevent remove elem
        return True

    def on_elemRefresh(self, key):
        print("Elem refresh:", key)
        # prevent refresh elem
        return True


class Plugin(object):
    def __init__(self) -> None:
        self.load_config()
        self.trans_api = Seletrans(self.cfg["api"])()
        self.trans_api.prepare()
        self.api = PluginApi(self)
        self.hooks = {}
        for k, v in self.cfg["hooks"].items():
            kwargs = {}
            if len(v) > 2:
                kwargs = v[2]
            self.hooks[k] = partial(self.trans, source=v[0], target=v[1], **kwargs)

    async def trans(self, content, source, target, copy=False, tts=False):
        res = ""
        ts = self.trans_api
        await sio.emit(
            "notify",
            data=(
                {
                    "text": f"{source}->{target} 查询{content}",
                    "title": self.manifest["name"],
                },
            ),
        )
        try:
            ts.instant_query(content, source, target)
            res = "<br>".join(ts.result)
            await sio.emit(
                "notify",
                data=(
                    {
                        "text": res,
                        "title": self.manifest["name"],
                        "duration": min(max(3000, len(res) * 200), 10000),
                    },
                ),
            )
            if copy:
                pyperclip.copy(res)
            if tts:
                ts.play_sound()
            print(res)
        except:
            traceback.print_exc()
            now = datetime.now()
            time = now.strftime("%H%M%S")
            tmp_dir = tempfile.mkdtemp(prefix=f"esp_trans_{time}")
            with open(f"{tmp_dir}/error_log.txt", "w") as f:
                traceback.print_exc(file=f)
            ts.driver.save_screenshot(f"{tmp_dir}/screenshot.png")
            await sio.emit(
                "notify",
                data=(
                    {
                        "text": f"error log saved to {tmp_dir}",
                        "title": self.manifest["name"],
                    },
                ),
            )
        self.trans_api.prepare()

    def load_config(self):
        path = user_config_dir(APP_NAME, False, roaming=True)
        with codecs.open(path + "/api.json") as f:
            config = json.load(f)
        self.port = config["apiPort"]
        try:
            with codecs.open(PLUGIN_SETTING) as f:
                self.cfg = json.load(f)
            for k in DEFAULT_CONFIG:
                if k not in self.cfg or type(self.cfg[k]) != type(DEFAULT_CONFIG[k]):
                    self.cfg[k] = DEFAULT_CONFIG[k]
        except:
            self.cfg = DEFAULT_CONFIG
        self.save_cfg()
        with codecs.open(MANIFEST) as f:
            self.manifest = json.load(f)

    def save_cfg(self):
        with codecs.open(PLUGIN_SETTING, "w") as f:
            json.dump(self.cfg, f)

    async def setup_connect(self):
        print("Setup connect")
        for hook in self.hooks.keys():
            await sio.emit("addInputHook", data=(hook))
        await sio.emit(
            "notify",
            data=(
                {
                    "text": "翻译已启动. 翻译结果将通过通知形式显示, 也可以复制到剪贴板中.",
                    "title": self.manifest["name"],
                },
            ),
        )
        print("Setup connect done")

    async def loop(self):
        print("Run loop")
        await sio.connect(f"http://127.0.0.1:{self.port}")
        print("Sio Connected")
        await sio.wait()
        print("Loop end")

    def close(self):
        self.trans_api.close()


if __name__ == "__main__":
    while True:
        try:
            # asyncio
            sio = socketio.AsyncClient()
            p = Plugin()
            sio.register_namespace(p.api)
            asyncio.run(p.loop())
        except RuntimeError:
            import traceback

            print(traceback.format_exc())
            p.close()
        except socketio.exceptions.ConnectionError:
            import traceback

            print(traceback.format_exc())
            p.close()
        except:
            import traceback

            print(traceback.format_exc())
            p.close()
            break
