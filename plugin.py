from appdirs import *
import codecs
import json
import asyncio
import socketio
import uuid
from seletrans.api import *
import pyperclip
import sys

APP_NAME = "electron-spirit"
MANIFEST = "manifest.json"
PLUGIN_SETTING = "plugin.setting.json"
DEFAULT_CONFIG = {
    "api": "deepl",
    "hooks": {
        "t": ["auto", "zh"],
        "te": ["zh", "en-US"],
        "ts": ["auto", "zh", {"tts": True}],
        "tse": ["zh", "en-US", {"tts": True}],
        "tc": ["auto", "zh", {"copy": True}],
        "tce": ["zh", "en-US", {"copy": True}],
        "tcs": ["auto", "zh", {"copy": True, "tts": True}],
        "tcse": ["zh", "en-US", {"copy": True, "tts": True}],
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
        self.trans_api = Seletrans(self.cfg["api"])
        self.api = PluginApi(self)
        self.hooks = {}
        for k, v in self.cfg["hooks"].items():
            self.hooks[k] = lambda x: self.trans(x, v[0], v[1], **v[2])

    async def trans(self, content, source, target, copy=False, tts=False):
        with self.trans_api() as ts:
            res = ts.query(content, source, target)
            res = "\n".join(res.result)
            if tts:
                res.play_sound()
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
        print(res)

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
        except:
            import traceback

            print(traceback.format_exc())
            break
