"""Пул локальных GGUF-моделей (llama.cpp, CPU). Держим в памяти столько, сколько влезает в бюджет."""
import os, time
from collections import OrderedDict
from llama_cpp import Llama
BUDGET = 1  # одна модель в памяти: лимит контейнера около 10 ГБ
_pool = OrderedDict()

def chat(cfg, system, user, max_tokens):
    path = cfg["gguf"]
    if path in _pool:
        _pool.move_to_end(path)
    else:
        size = os.path.getsize(path)
        while _pool and sum(os.path.getsize(p) for p in _pool) + size > BUDGET:
            _, old = _pool.popitem(last=False)
            old.close()
        _pool[path] = Llama(model_path=path, n_ctx=cfg.get("n_ctx", 12288), n_threads=4, n_batch=512, verbose=False)
    llm = _pool[path]
    msgs = [{"role": "user", "content": system + "\n\n" + user}] if cfg.get("no_system") else \
           [{"role": "system", "content": system}, {"role": "user", "content": user}]
    r = llm.create_chat_completion(messages=msgs, max_tokens=max_tokens, temperature=cfg.get("temperature", 0.8))
    return r["choices"][0]["message"].get("content") or ""
