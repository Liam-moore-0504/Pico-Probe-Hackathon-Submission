class PluginRegistry:
    def __init__(self):
        self._p, self._enabled = {}, {}

    def register(self, plugin):
        self._p[plugin.manifest.plugin_id] = plugin
        self._enabled[plugin.manifest.plugin_id] = True

    def get(self, key):
        if key not in self._p or not self._enabled.get(key):
            raise KeyError(key)
        return self._p[key]

    def list(self):
        return sorted(key for key in self._p if self._enabled.get(key))

    def by_capability(self, capability):
        return [p for key, p in self._p.items() if self._enabled.get(key) and capability in p.manifest.capabilities]

    def set_enabled(self, key, enabled):
        if key not in self._p:
            raise KeyError(key)
        self._enabled[key] = enabled
